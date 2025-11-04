# Chat Persistence, LLM Caching, and Usage Tracking Examples

This document provides examples of using the new chat persistence, LLM response caching, and token usage tracking features added to `SupabaseKnowledgeBase`.

## Table of Contents

- [Chat Session Management](#chat-session-management)
- [Chat Message Management](#chat-message-management)
- [LLM Response Caching](#llm-response-caching)
- [Token Usage Tracking](#token-usage-tracking)
- [Supabase Table Schemas](#supabase-table-schemas)

## Chat Session Management

### Creating a Chat Session

```python
from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase

# Initialize the knowledge base
kb = SupabaseKnowledgeBase()

# Create a new chat session
session = await kb.create_chat_session(
    user_id="user-123",
    title="BigQuery Analysis Session",
    metadata={"context": "analyzing sales data"}
)

# Returns:
# {
#     "id": "uuid-here",
#     "user_id": "user-123",
#     "title": "BigQuery Analysis Session",
#     "created_at": "2024-01-01T00:00:00Z",
#     "updated_at": "2024-01-01T00:00:00Z",
#     "metadata": {"context": "analyzing sales data"}
# }
```

### Retrieving Chat Sessions

```python
# Get a specific session
session = await kb.get_chat_session(
    session_id="uuid-here",
    user_id="user-123"  # Optional, for access control
)

# Get all sessions for a user (paginated)
sessions = await kb.get_user_chat_sessions(
    user_id="user-123",
    limit=50,
    offset=0
)

# Get recent chat history with messages
history = await kb.get_chat_history(
    user_id="user-123",
    limit_sessions=10
)
# Each session includes a 'messages' key with the latest messages
```

### Updating a Chat Session

```python
# Update title or metadata
success = await kb.update_chat_session(
    session_id="uuid-here",
    title="Updated Title",
    metadata={"context": "updated context", "tags": ["analytics"]}
)
```

## Chat Message Management

### Appending Messages

```python
# Add a user message
message = await kb.append_chat_message(
    session_id="session-uuid",
    user_id="user-123",
    role="user",
    content="What are the top 10 products by revenue?",
    metadata={"tokens": 12}
)

# Add an assistant response
response = await kb.append_chat_message(
    session_id="session-uuid",
    user_id="user-123",
    role="assistant",
    content="Here's the query to get top 10 products...",
    metadata={
        "tokens": 150,
        "model": "gpt-4",
        "finish_reason": "stop"
    }
)
```

### Retrieving Messages

```python
# Get all messages from a session
messages = await kb.get_chat_messages(
    session_id="session-uuid",
    user_id="user-123",  # Optional, for access control
    limit=100,
    offset=0
)

# Messages are returned in chronological order (oldest first)
for msg in messages:
    print(f"{msg['role']}: {msg['content']}")
```

## LLM Response Caching

### Caching LLM Responses

```python
# Cache a response
success = await kb.cache_llm_response(
    prompt="Explain BigQuery partitioning",
    provider="openai",
    model="gpt-4",
    response="BigQuery partitioning is a technique...",
    metadata={
        "tokens": 250,
        "finish_reason": "stop",
        "completion_tokens": 200,
        "prompt_tokens": 50
    },
    parameters={"temperature": 0.7, "max_tokens": 500},
    ttl_hours=168  # 7 days
)
```

### Retrieving Cached Responses

```python
# Try to get a cached response
cached = await kb.get_cached_llm_response(
    prompt="Explain BigQuery partitioning",
    provider="openai",
    model="gpt-4",
    parameters={"temperature": 0.7, "max_tokens": 500}
)

if cached:
    print(f"Cache hit! Response: {cached['response']}")
    print(f"Hit count: {cached['hit_count']}")
    print(f"Cached at: {cached['cached_at']}")
else:
    print("Cache miss - need to generate response")
    # ... call LLM API ...
    # Then cache the response
```

### Cache Management

```python
# Clean up expired cache entries
deleted_count = await kb.cleanup_expired_llm_cache()
print(f"Deleted {deleted_count} expired cache entries")
```

### Advanced: Caching with Embeddings

```python
# Cache a response with embedding for similarity search
success = await kb.cache_llm_response(
    prompt="Explain BigQuery partitioning",
    provider="openai",
    model="gpt-4",
    response="BigQuery partitioning is...",
    embedding=[0.1, 0.2, 0.3, ...],  # Vector embedding
    metadata={"tokens": 250}
)

# Find similar cached prompts (requires pgvector setup)
similar = await kb.get_similar_cached_prompts(
    embedding=[0.1, 0.2, 0.3, ...],
    limit=5,
    similarity_threshold=0.8
)
```

## Token Usage Tracking

### Recording Token Usage

```python
# Record tokens consumed by a request
success = await kb.record_token_usage(
    user_id="user-123",
    tokens_consumed=500,
    provider="openai",
    model="gpt-4",
    request_metadata={
        "endpoint": "chat/completions",
        "prompt_tokens": 100,
        "completion_tokens": 400
    }
)
```

### Retrieving Usage Statistics

```python
# Get usage stats for the last 30 days
usage = await kb.get_user_token_usage(
    user_id="user-123",
    days=30
)

print(f"Total tokens: {usage['total_tokens']}")
print(f"Total requests: {usage['total_requests']}")

# Provider breakdown
for provider, models in usage['provider_breakdown'].items():
    for model, stats in models.items():
        print(f"{provider}/{model}: {stats['tokens']} tokens, {stats['requests']} requests")

# Daily breakdown
for day in usage['daily_breakdown']:
    print(f"{day['period_start']}: {day['tokens_consumed']} tokens")
```

### Checking Quotas

```python
# Check daily quota
quota = await kb.check_user_quota(
    user_id="user-123",
    quota_period="daily"  # or "monthly"
)

if quota['is_over_quota']:
    print(f"User is over quota!")
    print(f"Used: {quota['tokens_used']} / {quota['quota_limit']}")
else:
    print(f"Remaining tokens: {quota['remaining']}")

# Example integration in request handler:
async def handle_llm_request(user_id: str, prompt: str):
    # Check quota before processing
    quota = await kb.check_user_quota(user_id, "daily")
    
    if quota['is_over_quota']:
        raise Exception("Daily quota exceeded")
    
    # Try to get cached response
    cached = await kb.get_cached_llm_response(
        prompt=prompt,
        provider="openai",
        model="gpt-4"
    )
    
    if cached:
        return cached['response']
    
    # Generate new response
    response = await call_llm_api(prompt)
    
    # Cache the response
    await kb.cache_llm_response(
        prompt=prompt,
        provider="openai",
        model="gpt-4",
        response=response,
        metadata={"tokens": calculate_tokens(response)}
    )
    
    # Record usage
    await kb.record_token_usage(
        user_id=user_id,
        tokens_consumed=calculate_tokens(response),
        provider="openai",
        model="gpt-4"
    )
    
    return response
```

## Supabase Table Schemas

### chat_sessions

```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES user_profiles(user_id),
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);
```

### chat_messages

```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    ordering INTEGER NOT NULL
);

CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_ordering ON chat_messages(session_id, ordering);
```

### llm_response_cache

```sql
CREATE TABLE llm_response_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_hash TEXT UNIQUE NOT NULL,
    prompt TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    response TEXT NOT NULL,
    metadata JSONB,
    embedding VECTOR(1536),  -- Optional: requires pgvector extension
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER DEFAULT 0
);

CREATE INDEX idx_llm_cache_prompt_hash ON llm_response_cache(prompt_hash);
CREATE INDEX idx_llm_cache_expires_at ON llm_response_cache(expires_at);
CREATE INDEX idx_llm_cache_provider_model ON llm_response_cache(provider, model);

-- Optional: For similarity search with pgvector
-- CREATE INDEX idx_llm_cache_embedding ON llm_response_cache USING ivfflat (embedding vector_cosine_ops);
```

### user_usage_stats

```sql
CREATE TABLE user_usage_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES user_profiles(user_id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    tokens_consumed BIGINT DEFAULT 0,
    requests_count INTEGER DEFAULT 0,
    quota_limit BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(user_id, period_start)
);

CREATE INDEX idx_usage_stats_user_id ON user_usage_stats(user_id);
CREATE INDEX idx_usage_stats_period_start ON user_usage_stats(period_start DESC);
```

## Error Handling

All methods gracefully handle missing tables and connection failures:

```python
# Connection not verified
kb._connection_verified = False
result = await kb.create_chat_session(user_id="user-123")
# Returns: None (doesn't crash)

# Table doesn't exist
try:
    result = await kb.create_chat_session(user_id="user-123")
except Exception as e:
    print(f"Table missing: {e}")
    # Log actionable error for operators
```

## Best Practices

1. **Always check connection**: Methods return `None` or empty lists when connection is not verified
2. **Cache aggressively**: Set appropriate TTLs for different types of queries
3. **Monitor quotas**: Check quotas before expensive operations
4. **Use metadata**: Store relevant context in metadata fields for debugging and analytics
5. **Cleanup regularly**: Run `cleanup_expired_llm_cache()` periodically (e.g., daily cron job)
6. **Set appropriate quotas**: Configure user preferences with `daily_token_quota` and `monthly_token_quota`

## Complete Integration Example

```python
from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase

class ChatAgent:
    def __init__(self):
        self.kb = SupabaseKnowledgeBase()
    
    async def start_conversation(self, user_id: str, title: str = "New Chat"):
        """Start a new chat session."""
        return await self.kb.create_chat_session(user_id, title)
    
    async def chat(self, session_id: str, user_id: str, message: str):
        """Process a chat message with caching and usage tracking."""
        # Check quota
        quota = await self.kb.check_user_quota(user_id, "daily")
        if quota['is_over_quota']:
            return {"error": "Daily quota exceeded", "quota": quota}
        
        # Save user message
        await self.kb.append_chat_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=message
        )
        
        # Try cache first
        cached = await self.kb.get_cached_llm_response(
            prompt=message,
            provider="openai",
            model="gpt-4"
        )
        
        if cached:
            response_text = cached['response']
            was_cached = True
        else:
            # Generate new response (pseudo-code)
            response_text = await self.generate_llm_response(message)
            was_cached = False
            
            # Cache the response
            await self.kb.cache_llm_response(
                prompt=message,
                provider="openai",
                model="gpt-4",
                response=response_text,
                metadata={"tokens": len(response_text.split())}
            )
            
            # Record usage
            await self.kb.record_token_usage(
                user_id=user_id,
                tokens_consumed=len(response_text.split()),
                provider="openai",
                model="gpt-4"
            )
        
        # Save assistant response
        await self.kb.append_chat_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            metadata={"cached": was_cached}
        )
        
        return {
            "response": response_text,
            "cached": was_cached,
            "remaining_quota": quota['remaining']
        }
    
    async def get_history(self, user_id: str):
        """Get recent chat history."""
        return await self.kb.get_chat_history(user_id, limit_sessions=10)
```
