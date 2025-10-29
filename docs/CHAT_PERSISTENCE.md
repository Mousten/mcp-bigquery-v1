# Chat Persistence API

This document describes the chat persistence feature that allows users to store and retrieve conversational history across sessions.

## Overview

The chat persistence feature provides:
- Session management (create, list, rename, delete)
- Message storage with chronological ordering
- User-scoped access control
- Metadata support for messages

## Database Setup

### Prerequisites

1. A Supabase project with PostgreSQL database
2. Service role key for administrative operations
3. JWT secret for token validation

### Schema Installation

Run the SQL schema provided in `docs/supabase_chat_schema.sql` to set up the required tables:

```bash
psql -h your-db-host -U postgres -d your-database -f docs/supabase_chat_schema.sql
```

Or use the Supabase SQL Editor to execute the schema file.

### Tables Created

- **chat_sessions**: Stores session metadata
  - `id` (UUID, primary key)
  - `user_id` (TEXT, references auth.users)
  - `title` (TEXT, default: "New Conversation")
  - `created_at` (TIMESTAMPTZ)
  - `updated_at` (TIMESTAMPTZ)

- **chat_messages**: Stores individual messages
  - `id` (UUID, primary key)
  - `session_id` (UUID, foreign key to chat_sessions)
  - `role` (TEXT, one of: user, assistant, system)
  - `content` (TEXT, message content)
  - `metadata` (JSONB, for additional data)
  - `created_at` (TIMESTAMPTZ)
  - `ordering` (INTEGER, for message sequence)

### Row Level Security (RLS)

The schema includes RLS policies to ensure users can only access their own sessions and messages:

- Users can only view/modify sessions where `user_id` matches their authenticated user ID
- Messages are automatically scoped to the user's sessions
- All operations are protected by RLS policies

## API Endpoints

All endpoints require authentication via Bearer token in the `Authorization` header.

### Create Session

Create a new chat session.

```
POST /chat/sessions
```

**Request Body:**
```json
{
  "title": "My Conversation"  // Optional, defaults to "New Conversation"
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "title": "My Conversation",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

### List Sessions

Retrieve all sessions for the authenticated user.

```
GET /chat/sessions?limit=50&offset=0
```

**Query Parameters:**
- `limit` (optional): Maximum sessions to return (1-100, default: 50)
- `offset` (optional): Number of sessions to skip (default: 0)

**Response (200):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-123",
    "title": "My Conversation",
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T12:30:00Z"
  }
]
```

Sessions are ordered by `updated_at` in descending order (most recent first).

### Get Session

Retrieve details for a specific session.

```
GET /chat/sessions/{session_id}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "title": "My Conversation",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T12:30:00Z"
}
```

**Error (404):** Session not found or access denied

### Rename Session

Update the title of a session.

```
PUT /chat/sessions/{session_id}
```

**Request Body:**
```json
{
  "title": "Updated Title"
}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "title": "Updated Title",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T14:00:00Z"
}
```

### Delete Session

Delete a session and all its messages.

```
DELETE /chat/sessions/{session_id}
```

**Response (204):** No content (success)

**Error (404):** Session not found or access denied

### Append Message

Add a message to a session.

```
POST /chat/sessions/{session_id}/messages
```

**Request Body:**
```json
{
  "role": "user",
  "content": "Hello, how are you?",
  "metadata": {
    "model": "gpt-4",
    "temperature": 0.7
  }
}
```

**Fields:**
- `role` (required): One of `user`, `assistant`, or `system`
- `content` (required): Message text
- `metadata` (optional): Additional data as JSON object

**Response (201):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "user",
  "content": "Hello, how are you?",
  "metadata": {
    "model": "gpt-4",
    "temperature": 0.7
  },
  "created_at": "2024-01-15T10:05:00Z",
  "ordering": 0
}
```

### Fetch Messages

Retrieve all messages for a session in chronological order.

```
GET /chat/sessions/{session_id}/messages?limit=100
```

**Query Parameters:**
- `limit` (optional): Maximum messages to return

**Response (200):**
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "user",
    "content": "Hello, how are you?",
    "metadata": {},
    "created_at": "2024-01-15T10:05:00Z",
    "ordering": 0
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440002",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "assistant",
    "content": "I'm doing well, thank you!",
    "metadata": {
      "model": "gpt-4",
      "tokens": 12
    },
    "created_at": "2024-01-15T10:05:15Z",
    "ordering": 1
  }
]
```

Messages are ordered by the `ordering` field to preserve conversation sequence.

## Authentication

All endpoints require a valid Supabase JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

The token must:
- Be signed with the configured `SUPABASE_JWT_SECRET`
- Not be expired
- Contain a valid `sub` claim (user ID)

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Missing authentication token"
}
```

### 403 Forbidden
```json
{
  "detail": "Token has expired"
}
```

### 404 Not Found
```json
{
  "detail": "Session not found or access denied"
}
```

### 400 Bad Request
```json
{
  "detail": "Invalid role. Must be one of: user, assistant, system"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to create chat session"
}
```

## Usage Examples

### Python Client

```python
import requests
from typing import List, Dict, Any

class ChatClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def create_session(self, title: str = "New Conversation") -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/chat/sessions",
            json={"title": title},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/chat/sessions",
            params={"limit": limit, "offset": offset},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def append_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/chat/sessions/{session_id}/messages",
            json={
                "role": role,
                "content": content,
                "metadata": metadata or {}
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def fetch_history(self, session_id: str) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/chat/sessions/{session_id}/messages",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Example usage
client = ChatClient("http://localhost:8000", "your-jwt-token")

# Create a new session
session = client.create_session("AI Assistant Chat")
session_id = session["id"]

# Add messages
client.append_message(session_id, "user", "What is BigQuery?")
client.append_message(
    session_id, 
    "assistant", 
    "BigQuery is Google's serverless data warehouse.",
    metadata={"model": "gpt-4", "tokens": 50}
)

# Fetch history
history = client.fetch_history(session_id)
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

### JavaScript/TypeScript Client

```typescript
interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata: Record<string, any>;
  created_at: string;
  ordering: number;
}

class ChatClient {
  constructor(private baseUrl: string, private token: string) {}
  
  async createSession(title: string = 'New Conversation'): Promise<ChatSession> {
    const response = await fetch(`${this.baseUrl}/chat/sessions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title }),
    });
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  
  async listSessions(limit = 50, offset = 0): Promise<ChatSession[]> {
    const response = await fetch(
      `${this.baseUrl}/chat/sessions?limit=${limit}&offset=${offset}`,
      {
        headers: { 'Authorization': `Bearer ${this.token}` },
      }
    );
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  
  async appendMessage(
    sessionId: string,
    role: 'user' | 'assistant' | 'system',
    content: string,
    metadata: Record<string, any> = {}
  ): Promise<ChatMessage> {
    const response = await fetch(
      `${this.baseUrl}/chat/sessions/${sessionId}/messages`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ role, content, metadata }),
      }
    );
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  
  async fetchHistory(sessionId: string): Promise<ChatMessage[]> {
    const response = await fetch(
      `${this.baseUrl}/chat/sessions/${sessionId}/messages`,
      {
        headers: { 'Authorization': `Bearer ${this.token}` },
      }
    );
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
}

// Example usage
const client = new ChatClient('http://localhost:8000', 'your-jwt-token');

const session = await client.createSession('AI Chat');
await client.appendMessage(session.id, 'user', 'Hello!');
const history = await client.fetchHistory(session.id);
```

## Best Practices

1. **Session Management**
   - Create a new session for each distinct conversation
   - Use descriptive titles for easy identification
   - Clean up old sessions periodically if needed

2. **Message Ordering**
   - Messages are automatically ordered using the `ordering` field
   - Always fetch messages in order to preserve conversation flow
   - Don't modify the `ordering` field manually

3. **Metadata Usage**
   - Store model information (model name, version)
   - Track token usage for billing/monitoring
   - Include timestamps or other contextual data
   - Keep metadata reasonably sized (< 1KB per message)

4. **Error Handling**
   - Always check for 404 errors when accessing sessions
   - Handle 401/403 errors by refreshing authentication
   - Retry failed operations with exponential backoff

5. **Performance**
   - Use pagination when listing sessions
   - Limit message fetching for long conversations
   - Cache session lists on the client side

## Troubleshooting

### "Session not found or access denied"

- Verify the session ID is correct
- Ensure the authenticated user owns the session
- Check that the session hasn't been deleted

### "Invalid role" error

- Role must be exactly one of: `user`, `assistant`, `system`
- Check for typos or extra whitespace

### RLS policy errors

- Ensure RLS policies are properly configured
- Verify the service role key has necessary permissions
- Check that `auth.uid()` returns the correct user ID

## Future Enhancements

Potential future improvements:
- Message editing and deletion
- Session sharing between users
- Full-text search across messages
- Session archiving
- Bulk operations
- WebSocket support for real-time updates
