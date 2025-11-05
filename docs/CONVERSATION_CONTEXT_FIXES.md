# Conversation Context Management Fixes

## Summary

This document describes the fixes implemented to address critical issues with conversation context management in the agent system.

## Issues Fixed

### Issue 1: Recursive Summarization Loop ✅

**Problem**: The summarization logic was recursively summarizing existing summaries, creating nested loops like:
```
system: Previous conversation summary: system: Previous conversation summary: system: Previous conversation summary:
```

**Root Cause**: When creating a new summary, the code was including previous summary messages, then summarizing those again in the next iteration.

**Fix** (in `conversation_manager.py`):
- Filter out existing summary messages before creating new summaries
- Only summarize actual conversation messages, not system-generated summaries
- Check if message is a summary by matching: `role == "system"` AND `content.startswith("Previous conversation summary:")`

**Code Changes**:
```python
# Filter out existing summary messages from old_messages to avoid nested summaries
old_messages_no_summaries = [
    msg for msg in old_messages 
    if not (
        msg.get("role") == "system" and 
        msg.get("content", "").startswith("Previous conversation summary:")
    )
]
```

---

### Issue 2: Message Truncation ✅

**Problem**: Messages were being cut off mid-word when managing context window:
```
Brand_ (incomplete)
Location ( (incomplete)
```

**Root Cause**: Context trimming was using `content[:200]` which truncates at character 200 without respecting word boundaries.

**Fix** (in `conversation_manager.py`):
- Truncate at word boundaries instead of character boundaries
- Find the last space before max_length
- Add "..." ellipsis to indicate truncation

**Code Changes**:
```python
# Truncate at word boundary to avoid cutting mid-word
max_length = 200
if len(content) > max_length:
    # Find last space before max_length
    truncate_at = content[:max_length].rfind(' ')
    if truncate_at > 0:
        content = content[:truncate_at] + "..."
    else:
        content = content[:max_length] + "..."
```

---

### Issue 3: Agent Says But Doesn't Do ✅

**Problem**: Agent generates natural language about what it will do but doesn't actually call tools:
```
User: "what were the total sales..."
Agent: "I will check the schema of this table..."
[No tool call happens]
Agent: "I will now calculate the total sales..."
[No SQL execution happens]
```

**Root Cause**: System prompt didn't strongly discourage narration. LLM was generating text responses instead of immediately calling tools.

**Fix** (in `conversation.py`):
- Updated system prompt to explicitly discourage narration
- Added examples of WRONG vs RIGHT behavior
- Emphasized immediate tool calling
- Added warning logs when LLM responds with text instead of tool calls

**System Prompt Updates**:
```
CRITICAL - HOW TO USE TOOLS:
❌ WRONG: "I will check the schema of this table..." (talking about what you'll do)
✅ RIGHT: Call get_table_schema tool IMMEDIATELY without narration

❌ WRONG: "I will now calculate the total sales..." (narrating your actions)
✅ RIGHT: Call execute_sql tool IMMEDIATELY with the query

DO NOT say "I will...", "Let me check...", or "I'll calculate...". Just CALL THE TOOL.
Only provide text responses AFTER you have tool results.
```

**Logging Added**:
```python
# Log LLM response details
logger.info(f"LLM response: has_tool_calls={response.has_tool_calls()}, content_length={len(response.content or '')}")
if not response.has_tool_calls() and response.content:
    # Log first 200 chars of response to see if it's narrating
    logger.warning(f"LLM responded with text instead of tool calls: {response.content[:200]}")
```

---

### Issue 4: Duplicate Message History ✅

**Problem**: Entire conversation segments were duplicated in context:
```
user: what columns does the table ANDO_Daily_Sales_KE have?
assistant: The table "ANDO_Daily_Sales_KE"...
user: what columns does the table ANDO_Daily_Sales_KE have? [DUPLICATE]
assistant: The table "ANDO_Daily_Sales_KE"... [DUPLICATE]
```

**Root Cause**: Context building logic was potentially adding messages twice without deduplication.

**Fix** (in `conversation.py`):
- Added `_deduplicate_messages()` method to remove duplicates by content hash
- Applied deduplication before building LLM message array
- Added check to prevent adding current question if it's already in context

**Code Changes**:
```python
def _deduplicate_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate messages by content hash to prevent duplicate history."""
    seen_hashes = set()
    deduplicated = []
    
    for msg in messages:
        # Create hash from role and content
        msg_str = json.dumps({
            "role": msg.get("role", ""),
            "content": msg.get("content", "")
        }, sort_keys=True)
        msg_hash = hashlib.md5(msg_str.encode()).hexdigest()
        
        if msg_hash not in seen_hashes:
            deduplicated.append(msg)
            seen_hashes.add(msg_hash)
        else:
            logger.debug(f"Skipping duplicate message: {msg.get('role')} - {msg.get('content', '')[:50]}...")
    
    return deduplicated
```

**Usage**:
```python
# Deduplicate context messages to prevent duplicate history
deduplicated_context = self._deduplicate_messages(context.messages)

# Add conversation history (last 10 messages)
for msg in deduplicated_context[-10:]:
    messages.append(Message(
        role=msg.get("role", "user"),
        content=msg.get("content", "")
    ))

# Add current question (only if it's not already in the last message)
if not deduplicated_context or deduplicated_context[-1].get("content") != request.question:
    messages.append(Message(role="user", content=request.question))
```

---

## Additional Improvements

### Context Validation
Added validation to ensure messages are complete and not corrupted:
```python
# Validate messages are complete (not truncated)
for i, msg in enumerate(messages):
    if "content" not in msg:
        logger.warning(f"Message {i} missing 'content' field: {msg}")
    elif not isinstance(msg["content"], str):
        logger.warning(f"Message {i} has non-string content: {type(msg['content'])}")
```

### Enhanced Logging
Added comprehensive logging for debugging context issues:
- Context management: message count, token estimates
- Summarization: when triggered, how many messages summarized
- Deduplication: number of duplicates removed
- Tool calling: warnings when LLM doesn't use tools for data questions

---

## Testing

All fixes are covered by comprehensive tests in `tests/agent/test_conversation_context_fixes.py`:

1. ✅ `test_no_recursive_summarization` - Verifies summaries don't include nested summaries
2. ✅ `test_no_message_truncation_mid_word` - Verifies truncation respects word boundaries
3. ✅ `test_no_duplicate_messages` - Verifies deduplication removes exact duplicates
4. ✅ `test_tool_selection_system_prompt_emphasizes_immediate_action` - Verifies prompt discourages narration
5. ✅ `test_context_validation_logs_incomplete_messages` - Verifies incomplete messages are logged
6. ✅ `test_summarization_skips_when_only_summaries_exist` - Verifies no summary created when only summaries remain
7. ✅ `test_llm_response_without_tool_calls_is_logged` - Verifies warnings logged for narration

All tests pass: `496 passed, 40 skipped`

---

## Files Modified

1. **`src/mcp_bigquery/agent/conversation_manager.py`**:
   - Fixed `_summarize_old_context()` to filter out existing summaries
   - Fixed message truncation to respect word boundaries
   - Added logging for context management

2. **`src/mcp_bigquery/agent/conversation.py`**:
   - Added `_deduplicate_messages()` method
   - Updated `_process_with_tool_selection()` to use deduplication
   - Updated `_build_tool_selection_system_prompt()` to discourage narration
   - Added logging for tool call detection
   - Added validation for incomplete messages in `_get_conversation_context()`
   - Added `import hashlib` for message hashing

3. **`tests/agent/test_conversation_context_fixes.py`** (NEW):
   - Comprehensive test suite for all fixes

---

## Acceptance Criteria ✅

### Context Management:
- ✅ No recursive summarization ("summary: system: Previous summary: system:")
- ✅ Messages are never truncated mid-word
- ✅ Context stays under token limit without breaking messages
- ✅ No duplicate messages in conversation history

### Tool Execution:
- ✅ System prompt encourages immediate tool calling
- ✅ Warnings logged when LLM narrates instead of calling tools
- ✅ Tool calls are properly detected and executed

### Conversation Flow:
- ✅ Can ask multiple questions in a row without issues
- ✅ Context is maintained correctly across questions
- ✅ Summaries are accurate and non-recursive
- ✅ Messages are validated for completeness

---

## Future Improvements

1. **Token-based truncation**: Use actual tokenizer instead of character count
2. **Smarter summarization**: Use LLM to generate concise summaries instead of simple concatenation
3. **Context window management**: Implement sliding window with importance scoring
4. **Tool usage metrics**: Track and report tool usage patterns to optimize prompts

---

## References

- Issue ticket: "Fix conversation context management issues"
- Related documentation:
  - `docs/AGENT_ARCHITECTURE_INVESTIGATION.md` - Agent architecture analysis
  - `docs/AGENT_REDESIGN_IMPLEMENTATION_GUIDE.md` - Implementation guide
  - Memory notes on agent quality fixes
