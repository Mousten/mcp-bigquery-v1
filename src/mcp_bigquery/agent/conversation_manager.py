"""Conversation manager for orchestrating LLM-powered BigQuery insights.

This module provides the core conversational agent that glues together:
- LLM provider selection and management
- MCP client operations
- Response caching
- Context management with smart summarization
- Rate limiting and token tracking
- Message sanitization
"""

import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from pydantic import ValidationError

from ..llm.factory import create_provider, create_provider_from_env, ProviderType
from ..llm.providers import (
    LLMProvider,
    Message,
    GenerationResponse,
    LLMGenerationError,
)
from ..client import MCPClient
from ..client.exceptions import AuthorizationError, AuthenticationError
from ..core.supabase_client import SupabaseKnowledgeBase
from ..core.auth import UserContext
from .models import (
    AgentRequest,
    AgentResponse,
    ConversationContext,
)
from .conversation import InsightsAgent
from .summarizer import ResultSummarizer, DataSummary

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when user exceeds their rate limit."""
    pass


class ConversationManager:
    """Orchestrates conversational agent with rate limiting, caching, and context management.
    
    This manager provides a high-level interface for processing user questions with:
    - Automatic rate limit enforcement based on token quotas
    - Token usage tracking per turn
    - Message sanitization to prevent injection attacks
    - Smart context management with automatic summarization of older turns
    - LLM provider selection via factory
    - Result pre-processing with summarizer utilities
    - Response caching for cost reduction
    
    Example:
        ```python
        manager = ConversationManager(
            mcp_client=client,
            kb=supabase_kb,
            project_id="my-project",
            provider_type="openai"
        )
        
        request = AgentRequest(
            question="What are the top products?",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"sales"}
        )
        
        response = await manager.process_conversation(request)
        print(f"Tokens used: {response.metadata.get('tokens_used')}")
        ```
    """
    
    def __init__(
        self,
        mcp_client: MCPClient,
        kb: SupabaseKnowledgeBase,
        project_id: str,
        provider_type: Optional[ProviderType] = None,
        provider: Optional[LLMProvider] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        enable_caching: bool = True,
        enable_rate_limiting: bool = True,
        default_quota_period: str = "daily",
        max_context_turns: int = 5,
        context_summarization_threshold: int = 10,
        max_result_rows: int = 100
    ):
        """Initialize the conversation manager.
        
        Args:
            mcp_client: MCP client for BigQuery operations
            kb: Supabase knowledge base for persistence
            project_id: Google Cloud project ID
            provider_type: LLM provider type ("openai", "anthropic")
            provider: Pre-configured LLM provider (overrides provider_type)
            api_key: API key for LLM provider
            model: Model name to use
            enable_caching: Whether to cache LLM responses
            enable_rate_limiting: Whether to enforce rate limits
            default_quota_period: Default quota period ("daily" or "monthly")
            max_context_turns: Maximum conversation turns to include in context
            context_summarization_threshold: Summarize context if turns exceed this
            max_result_rows: Maximum result rows to include in summaries
        """
        self.mcp_client = mcp_client
        self.kb = kb
        self.project_id = project_id
        self.enable_caching = enable_caching
        self.enable_rate_limiting = enable_rate_limiting
        self.default_quota_period = default_quota_period
        self.max_context_turns = max_context_turns
        self.context_summarization_threshold = context_summarization_threshold
        
        # Initialize LLM provider
        if provider:
            self.provider = provider
        elif provider_type:
            self.provider = create_provider(
                provider_type=provider_type,
                api_key=api_key,
                model=model
            )
        else:
            # Default: create from environment
            self.provider = create_provider_from_env()
        
        # Initialize insights agent
        self.agent = InsightsAgent(
            llm_provider=self.provider,
            mcp_client=mcp_client,
            kb=kb,
            project_id=project_id,
            enable_caching=enable_caching
        )
        
        # Initialize result summarizer
        self.summarizer = ResultSummarizer(max_rows=max_result_rows)
        
        logger.info(
            f"ConversationManager initialized with provider={self.provider.provider_name}, "
            f"model={self.provider.config.model}, caching={enable_caching}, "
            f"rate_limiting={enable_rate_limiting}"
        )
    
    async def process_conversation(
        self,
        request: AgentRequest,
        quota_period: Optional[str] = None
    ) -> AgentResponse:
        """Process a conversation turn with full orchestration.
        
        This method:
        1. Sanitizes the user's question
        2. Checks and enforces rate limits
        3. Manages conversation context smartly
        4. Delegates to insights agent for processing
        5. Tracks token usage
        6. Updates metadata with metrics
        
        Args:
            request: Agent request with question and context
            quota_period: Quota period to check ("daily" or "monthly")
            
        Returns:
            Agent response with answer and metadata
            
        Raises:
            RateLimitExceeded: If user has exceeded their token quota
        """
        start_time = datetime.now(timezone.utc)
        tokens_used = 0
        
        try:
            # Step 1: Sanitize the question
            sanitized_question = self._sanitize_message(request.question)
            request.question = sanitized_question
            
            # Step 2: Check rate limits
            if self.enable_rate_limiting:
                quota_check = await self._check_rate_limit(
                    user_id=request.user_id,
                    quota_period=quota_period or self.default_quota_period
                )
                
                if quota_check["is_over_quota"]:
                    return self._create_rate_limit_response(quota_check)
            
            # Step 3: Smart context management
            await self._manage_context(
                session_id=request.session_id,
                user_id=request.user_id
            )
            
            # Step 4: Count input tokens
            input_tokens = await self._count_request_tokens(request)
            tokens_used += input_tokens
            
            # Step 5: Process through insights agent
            response = await self.agent.process_question(request)
            
            # Step 6: Count output tokens (if available in response)
            if response.metadata and "llm_usage" in response.metadata:
                llm_usage = response.metadata["llm_usage"]
                tokens_used = llm_usage.get("total_tokens", tokens_used)
            
            # Step 7: Record token usage
            await self._record_token_usage(
                user_id=request.user_id,
                tokens_consumed=tokens_used,
                request_metadata={
                    "session_id": request.session_id,
                    "question_length": len(sanitized_question),
                    "success": response.success
                }
            )
            
            # Step 8: Enhance response metadata
            response.metadata.update({
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "provider": self.provider.provider_name,
                "model": self.provider.config.model,
                "processing_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                "rate_limiting_enabled": self.enable_rate_limiting,
                "caching_enabled": self.enable_caching,
            })
            
            return response
            
        except RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded for user {request.user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing conversation: {e}", exc_info=True)
            
            # Try to record failed attempt
            try:
                await self._record_token_usage(
                    user_id=request.user_id,
                    tokens_consumed=tokens_used,
                    request_metadata={
                        "session_id": request.session_id,
                        "success": False,
                        "error": str(e)
                    }
                )
            except Exception:
                pass
            
            return AgentResponse(
                success=False,
                error=f"Failed to process conversation: {str(e)}",
                error_type="unknown",
                metadata={
                    "tokens_used": tokens_used,
                    "provider": self.provider.provider_name,
                    "model": self.provider.config.model,
                }
            )
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize user message to prevent injection attacks.
        
        This removes or escapes potentially dangerous patterns:
        - SQL injection attempts
        - Prompt injection attempts
        - Excessive whitespace
        - Control characters
        
        Args:
            message: Raw user message
            
        Returns:
            Sanitized message
        """
        if not message:
            return ""
        
        # Remove control characters (except newlines and tabs)
        sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', message)
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        # Trim to reasonable length (prevent token exhaustion)
        max_length = 2000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
            logger.warning(f"Message truncated from {len(message)} to {max_length} characters")
        
        # Remove common prompt injection patterns
        injection_patterns = [
            r'ignore\s+previous\s+instructions',
            r'disregard\s+.*\s+above',
            r'you\s+are\s+now\s+a',
            r'system\s*:\s*',
            r'<\s*system\s*>',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Potential prompt injection detected: {pattern}")
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized.strip()
    
    async def _check_rate_limit(
        self,
        user_id: str,
        quota_period: str
    ) -> Dict[str, Any]:
        """Check if user has exceeded their rate limit.
        
        Args:
            user_id: User ID
            quota_period: Quota period to check
            
        Returns:
            Dict with quota information
            
        Raises:
            RateLimitExceeded: If user is over quota
        """
        try:
            quota_check = await self.kb.check_user_quota(
                user_id=user_id,
                quota_period=quota_period
            )
            
            if quota_check["is_over_quota"]:
                logger.warning(
                    f"User {user_id} exceeded {quota_period} quota: "
                    f"{quota_check['tokens_used']}/{quota_check['quota_limit']}"
                )
            
            return quota_check
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # On error, allow the request (fail open)
            return {
                "quota_limit": None,
                "tokens_used": 0,
                "remaining": None,
                "is_over_quota": False
            }
    
    def _create_rate_limit_response(self, quota_check: Dict[str, Any]) -> AgentResponse:
        """Create a response for rate limit exceeded.
        
        Args:
            quota_check: Quota check result
            
        Returns:
            Agent response with rate limit error
        """
        quota_limit = quota_check.get("quota_limit", 0)
        tokens_used = quota_check.get("tokens_used", 0)
        quota_period = quota_check.get("quota_period", "daily")
        
        error_message = (
            f"You have exceeded your {quota_period} token quota. "
            f"Used: {tokens_used:,} / Limit: {quota_limit:,} tokens. "
            f"Please try again later or contact support to increase your quota."
        )
        
        return AgentResponse(
            success=False,
            error=error_message,
            error_type="rate_limit",
            metadata={
                "quota_limit": quota_limit,
                "tokens_used": tokens_used,
                "remaining": 0,
                "quota_period": quota_period
            }
        )
    
    async def _manage_context(
        self,
        session_id: str,
        user_id: str
    ) -> None:
        """Manage conversation context with smart summarization.
        
        If the conversation has many turns, summarize older ones to reduce token usage.
        
        Args:
            session_id: Session ID
            user_id: User ID
        """
        try:
            # Get all messages in the session
            messages = await self.kb.get_chat_messages(
                session_id=session_id,
                user_id=user_id,
                limit=100  # Get more to check if summarization needed
            )
            
            logger.info(f"Context management: {len(messages)} messages in session {session_id}")
            
            # Estimate token count
            total_tokens = sum(len(msg.get("content", "")) // 4 for msg in messages)
            logger.info(f"Estimated total tokens in context: {total_tokens}")
            
            # If we have many messages, summarize older ones
            if len(messages) > self.context_summarization_threshold:
                logger.info(f"Triggering summarization (threshold: {self.context_summarization_threshold})")
                await self._summarize_old_context(
                    session_id=session_id,
                    user_id=user_id,
                    messages=messages
                )
                
        except Exception as e:
            logger.error(f"Error managing context: {e}")
            # Don't fail the request if context management fails
    
    async def _summarize_old_context(
        self,
        session_id: str,
        user_id: str,
        messages: List[Dict[str, Any]]
    ) -> None:
        """Summarize older conversation turns to reduce token usage.
        
        Args:
            session_id: Session ID
            user_id: User ID
            messages: List of all messages
        """
        try:
            # Keep recent messages, summarize older ones
            recent_messages = messages[:self.max_context_turns * 2]
            old_messages = messages[self.max_context_turns * 2:]
            
            if not old_messages:
                return
            
            # Filter out existing summary messages from old_messages to avoid nested summaries
            old_messages_no_summaries = [
                msg for msg in old_messages 
                if not (
                    msg.get("role") == "system" and 
                    msg.get("content", "").startswith("Previous conversation summary:")
                )
            ]
            
            if not old_messages_no_summaries:
                logger.info("No new messages to summarize (all are existing summaries)")
                return
            
            # Create a summary of old messages (excluding existing summaries)
            summary_parts = []
            for msg in old_messages_no_summaries[-10:]:  # Summarize last 10 old messages
                role = msg.get("role", "")
                content = msg.get("content", "")
                
                # Truncate at word boundary to avoid cutting mid-word
                max_length = 200
                if len(content) > max_length:
                    # Find last space before max_length
                    truncate_at = content[:max_length].rfind(' ')
                    if truncate_at > 0:
                        content = content[:truncate_at] + "..."
                    else:
                        content = content[:max_length] + "..."
                
                summary_parts.append(f"{role}: {content}")
            
            summary_text = "Previous conversation summary:\n" + "\n".join(summary_parts)
            
            # Store summary as a system message (not shown to user but used for context)
            await self.kb.append_chat_message(
                session_id=session_id,
                user_id=user_id,
                role="system",
                content=summary_text,
                metadata={"summary": True, "summarized_messages": len(old_messages_no_summaries)}
            )
            
            logger.info(
                f"Summarized {len(old_messages_no_summaries)} old messages for session {session_id}"
            )
            
        except Exception as e:
            logger.error(f"Error summarizing old context: {e}")
    
    async def _count_request_tokens(self, request: AgentRequest) -> int:
        """Count tokens in the request.
        
        Args:
            request: Agent request
            
        Returns:
            Estimated token count
        """
        try:
            # Count tokens in the question
            question_tokens = self.provider.count_tokens(request.question)
            
            # Estimate tokens for context (if we loaded history)
            context_tokens = request.context_turns * 200  # Rough estimate
            
            return question_tokens + context_tokens
            
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Return a rough estimate based on character count
            return len(request.question) // 4
    
    async def _record_token_usage(
        self,
        user_id: str,
        tokens_consumed: int,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record token usage for tracking and rate limiting.
        
        Args:
            user_id: User ID
            tokens_consumed: Number of tokens consumed
            request_metadata: Optional metadata about the request
        """
        try:
            await self.kb.record_token_usage(
                user_id=user_id,
                tokens_consumed=tokens_consumed,
                provider=self.provider.provider_name,
                model=self.provider.config.model,
                request_metadata=request_metadata
            )
        except Exception as e:
            logger.error(f"Error recording token usage: {e}")
            # Don't fail the request if recording fails
    
    async def get_user_stats(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get token usage statistics for a user.
        
        Args:
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            Dict with usage statistics
        """
        try:
            return await self.kb.get_user_token_usage(user_id=user_id, days=days)
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                "total_tokens": 0,
                "total_requests": 0,
                "daily_breakdown": [],
                "provider_breakdown": {}
            }
    
    def summarize_results(
        self,
        results: Dict[str, Any],
        include_stats: bool = True
    ) -> DataSummary:
        """Summarize query results for compact LLM consumption.
        
        Args:
            results: Query results from MCP client
            include_stats: Whether to include statistics
            
        Returns:
            Data summary with statistics and insights
        """
        try:
            rows = results.get("rows", [])
            return self.summarizer.summarize(rows)
        except Exception as e:
            logger.error(f"Error summarizing results: {e}")
            return DataSummary(
                total_rows=0,
                total_columns=0,
                sampled_rows=0,
                key_insights=[f"Error summarizing: {str(e)}"]
            )
    
    def format_summary_for_llm(self, summary: DataSummary) -> str:
        """Format a data summary for LLM consumption.
        
        Args:
            summary: Data summary
            
        Returns:
            Formatted text suitable for LLM prompts
        """
        return self.summarizer.format_summary_text(summary)
