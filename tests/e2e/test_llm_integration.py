"""E2E tests for LLM provider integration.

Tests:
- OpenAI provider selection and execution
- Anthropic provider selection and execution
- Provider switching
- Token counting accuracy
- Error handling for missing/invalid API keys
"""

import pytest
import asyncio
from mcp_bigquery.llm import create_provider, Message, LLMConfigurationError


pytestmark = pytest.mark.e2e


class TestLLMProviderSelection:
    """Test LLM provider selection and initialization."""
    
    @pytest.mark.asyncio
    async def test_openai_provider_creation(self, test_config, test_report_generator, performance_monitor):
        """Test OpenAI provider can be created and used."""
        ctx = performance_monitor.start_operation("openai_provider_creation")
        
        try:
            if not test_config.get("openai_api_key"):
                pytest.skip("OpenAI API key not configured")
            
            provider = create_provider(
                provider_type="openai",
                api_key=test_config["openai_api_key"],
                model="gpt-4o-mini"  # Use cheaper model for testing
            )
            
            assert provider is not None, "Provider should be created"
            assert provider.provider_name == "openai", "Provider type should be openai"
            
            metric = performance_monitor.end_operation(ctx, success=True)
            test_report_generator.add_test_result(
                "test_openai_provider_creation",
                True,
                metric["duration_seconds"]
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_openai_provider_creation",
                False,
                0,
                {"error": str(e)}
            )
            raise
    
    @pytest.mark.asyncio
    async def test_anthropic_provider_creation(self, test_config, test_report_generator, performance_monitor):
        """Test Anthropic provider can be created and used."""
        ctx = performance_monitor.start_operation("anthropic_provider_creation")
        
        try:
            if not test_config.get("anthropic_api_key"):
                pytest.skip("Anthropic API key not configured")
            
            provider = create_provider(
                provider_type="anthropic",
                api_key=test_config["anthropic_api_key"],
                model="claude-3-haiku-20240307"  # Use cheaper model for testing
            )
            
            assert provider is not None, "Provider should be created"
            assert provider.provider_name == "anthropic", "Provider type should be anthropic"
            
            metric = performance_monitor.end_operation(ctx, success=True)
            test_report_generator.add_test_result(
                "test_anthropic_provider_creation",
                True,
                metric["duration_seconds"]
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_anthropic_provider_creation",
                False,
                0,
                {"error": str(e)}
            )
            raise
    
    @pytest.mark.asyncio
    async def test_invalid_provider_type(self, test_config, test_report_generator, performance_monitor):
        """Test that invalid provider type raises error."""
        ctx = performance_monitor.start_operation("invalid_provider_type")
        
        try:
            with pytest.raises(LLMConfigurationError):
                create_provider(
                    provider_type="invalid_provider",
                    api_key="fake-key"
                )
            
            metric = performance_monitor.end_operation(ctx, success=True)
            test_report_generator.add_test_result(
                "test_invalid_provider_type",
                True,
                metric["duration_seconds"]
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_invalid_provider_type",
                False,
                0,
                {"error": str(e)}
            )
            raise


class TestLLMQueryExecution:
    """Test LLM query execution."""
    
    @pytest.mark.asyncio
    async def test_openai_simple_query(self, test_config, test_report_generator, performance_monitor):
        """Test simple query with OpenAI."""
        ctx = performance_monitor.start_operation("openai_simple_query")
        
        try:
            if not test_config.get("openai_api_key"):
                pytest.skip("OpenAI API key not configured")
            
            provider = create_provider(
                provider_type="openai",
                api_key=test_config["openai_api_key"],
                model="gpt-4o-mini"
            )
            
            # Simple test query
            messages = [
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content="Say 'test successful' and nothing else.")
            ]
            
            response = await provider.generate(messages, max_tokens=100)
            
            assert response is not None, "Response should not be None"
            assert response.content is not None, "Response should have content"
            assert len(response.content) > 0, "Response content should not be empty"
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                response_length=len(response.content),
                tokens_used=response.usage
            )
            test_report_generator.add_test_result(
                "test_openai_simple_query",
                True,
                metric["duration_seconds"],
                {"response": response}
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_openai_simple_query",
                False,
                0,
                {"error": str(e)}
            )
            if "API key" in str(e) or "authentication" in str(e).lower():
                test_report_generator.add_issue(
                    "high",
                    "OpenAI API authentication failed",
                    f"Failed to authenticate with OpenAI API: {str(e)}"
                )
            raise
    
    @pytest.mark.asyncio
    async def test_anthropic_simple_query(self, test_config, test_report_generator, performance_monitor):
        """Test simple query with Anthropic."""
        ctx = performance_monitor.start_operation("anthropic_simple_query")
        
        try:
            if not test_config.get("anthropic_api_key"):
                pytest.skip("Anthropic API key not configured")
            
            provider = create_provider(
                provider_type="anthropic",
                api_key=test_config["anthropic_api_key"],
                model="claude-3-haiku-20240307"
            )
            
            # Simple test query
            messages = [
                Message(role="user", content="Say 'test successful' and nothing else.")
            ]
            
            response = await provider.generate(messages, max_tokens=100)
            
            assert response is not None, "Response should not be None"
            assert response.content is not None, "Response should have content"
            assert len(response.content) > 0, "Response content should not be empty"
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                response_length=len(response.content),
                tokens_used=response.usage
            )
            test_report_generator.add_test_result(
                "test_anthropic_simple_query",
                True,
                metric["duration_seconds"],
                {"response": response}
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_anthropic_simple_query",
                False,
                0,
                {"error": str(e)}
            )
            if "API key" in str(e) or "authentication" in str(e).lower():
                test_report_generator.add_issue(
                    "high",
                    "Anthropic API authentication failed",
                    f"Failed to authenticate with Anthropic API: {str(e)}"
                )
            raise


class TestTokenCounting:
    """Test token counting accuracy."""
    
    def test_openai_token_counting(self, test_config, test_report_generator, performance_monitor):
        """Test OpenAI token counting."""
        ctx = performance_monitor.start_operation("openai_token_counting")
        
        try:
            if not test_config.get("openai_api_key"):
                pytest.skip("OpenAI API key not configured")
            
            provider = create_provider(
                provider_type="openai",
                api_key=test_config["openai_api_key"],
                model="gpt-4o"
            )
            
            test_text = "Hello, how are you today?"
            tokens = provider.count_tokens(test_text)
            
            # Should return a reasonable number
            assert tokens > 0, "Token count should be positive"
            assert tokens < 100, "Token count should be reasonable for short text"
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                text_length=len(test_text),
                token_count=tokens
            )
            test_report_generator.add_test_result(
                "test_openai_token_counting",
                True,
                metric["duration_seconds"],
                {"tokens": tokens, "text_length": len(test_text)}
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_openai_token_counting",
                False,
                0,
                {"error": str(e)}
            )
            raise
    
    def test_anthropic_token_counting(self, test_config, test_report_generator, performance_monitor):
        """Test Anthropic token counting."""
        ctx = performance_monitor.start_operation("anthropic_token_counting")
        
        try:
            if not test_config.get("anthropic_api_key"):
                pytest.skip("Anthropic API key not configured")
            
            provider = create_provider(
                provider_type="anthropic",
                api_key=test_config["anthropic_api_key"],
                model="claude-3-opus-20240229"
            )
            
            test_text = "Hello, how are you today?"
            tokens = provider.count_tokens(test_text)
            
            # Should return a reasonable number
            assert tokens > 0, "Token count should be positive"
            assert tokens < 100, "Token count should be reasonable for short text"
            
            metric = performance_monitor.end_operation(
                ctx,
                success=True,
                text_length=len(test_text),
                token_count=tokens
            )
            test_report_generator.add_test_result(
                "test_anthropic_token_counting",
                True,
                metric["duration_seconds"],
                {"tokens": tokens, "text_length": len(test_text)}
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_anthropic_token_counting",
                False,
                0,
                {"error": str(e)}
            )
            raise
    
    def test_token_counting_consistency(self, test_config, test_report_generator, performance_monitor):
        """Test that token counting is consistent."""
        ctx = performance_monitor.start_operation("token_counting_consistency")
        
        try:
            if not test_config.get("openai_api_key"):
                pytest.skip("OpenAI API key not configured")
            
            provider = create_provider(
                provider_type="openai",
                api_key=test_config["openai_api_key"],
                model="gpt-4o"
            )
            
            test_text = "This is a test message for token counting consistency."
            
            # Count tokens multiple times
            counts = [provider.count_tokens(test_text) for _ in range(5)]
            
            # All counts should be the same
            assert len(set(counts)) == 1, "Token counts should be consistent"
            
            metric = performance_monitor.end_operation(ctx, success=True, token_count=counts[0])
            test_report_generator.add_test_result(
                "test_token_counting_consistency",
                True,
                metric["duration_seconds"],
                {"counts": counts}
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_token_counting_consistency",
                False,
                0,
                {"error": str(e)}
            )
            raise


class TestErrorHandling:
    """Test error handling for LLM providers."""
    
    @pytest.mark.asyncio
    async def test_invalid_api_key(self, test_config, test_report_generator, performance_monitor):
        """Test handling of invalid API key."""
        ctx = performance_monitor.start_operation("invalid_api_key")
        
        try:
            provider = create_provider(
                provider_type="openai",
                api_key="invalid-key-12345",
                model="gpt-4o-mini"
            )
            
            messages = [{"role": "user", "content": "Test"}]
            
            with pytest.raises(Exception) as exc_info:
                await provider.generate(messages)
            
            # Should get authentication error
            error_msg = str(exc_info.value).lower()
            assert "auth" in error_msg or "key" in error_msg or "401" in error_msg, \
                "Should get authentication error"
            
            metric = performance_monitor.end_operation(ctx, success=True)
            test_report_generator.add_test_result(
                "test_invalid_api_key",
                True,
                metric["duration_seconds"]
            )
            
        except AssertionError as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_invalid_api_key",
                False,
                0,
                {"error": str(e)}
            )
            test_report_generator.add_issue(
                "high",
                "Invalid API key not properly handled",
                "System did not properly handle invalid LLM provider API key"
            )
            raise
    
    @pytest.mark.asyncio
    async def test_missing_api_key(self, test_config, test_report_generator, performance_monitor):
        """Test handling of missing API key."""
        ctx = performance_monitor.start_operation("missing_api_key")
        
        try:
            with pytest.raises((LLMConfigurationError, ValueError, TypeError)):
                create_provider(
                    provider_type="openai",
                    api_key=None
                )
            
            metric = performance_monitor.end_operation(ctx, success=True)
            test_report_generator.add_test_result(
                "test_missing_api_key",
                True,
                metric["duration_seconds"]
            )
            
        except Exception as e:
            performance_monitor.end_operation(ctx, success=False, error=str(e))
            test_report_generator.add_test_result(
                "test_missing_api_key",
                False,
                0,
                {"error": str(e)}
            )
            raise
