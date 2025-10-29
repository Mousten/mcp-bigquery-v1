-- Chat persistence schema for Supabase
-- This schema supports storing conversational history per user for persistence across sessions

-- Chat sessions table
-- Stores session metadata for each conversation
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast user session lookups
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);

-- Chat messages table
-- Stores individual messages within each session
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ordering INTEGER NOT NULL
);

-- Indexes for fast message retrieval
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_ordering ON chat_messages(session_id, ordering);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_chat_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chat_sessions 
    SET updated_at = NOW() 
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update session timestamp when messages are added
DROP TRIGGER IF EXISTS trigger_update_chat_session_timestamp ON chat_messages;
CREATE TRIGGER trigger_update_chat_session_timestamp
    AFTER INSERT ON chat_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_chat_session_timestamp();

-- Row Level Security (RLS) Policies
-- Enable RLS on both tables
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own sessions
CREATE POLICY chat_sessions_select_policy ON chat_sessions
    FOR SELECT
    USING (auth.uid()::text = user_id);

-- Policy: Users can only insert their own sessions
CREATE POLICY chat_sessions_insert_policy ON chat_sessions
    FOR INSERT
    WITH CHECK (auth.uid()::text = user_id);

-- Policy: Users can only update their own sessions
CREATE POLICY chat_sessions_update_policy ON chat_sessions
    FOR UPDATE
    USING (auth.uid()::text = user_id);

-- Policy: Users can only delete their own sessions
CREATE POLICY chat_sessions_delete_policy ON chat_sessions
    FOR DELETE
    USING (auth.uid()::text = user_id);

-- Policy: Users can only see messages from their sessions
CREATE POLICY chat_messages_select_policy ON chat_messages
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

-- Policy: Users can only insert messages to their sessions
CREATE POLICY chat_messages_insert_policy ON chat_messages
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

-- Policy: Users can only update messages in their sessions
CREATE POLICY chat_messages_update_policy ON chat_messages
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

-- Policy: Users can only delete messages from their sessions
CREATE POLICY chat_messages_delete_policy ON chat_messages
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

-- Grant usage to authenticated users
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON chat_sessions TO authenticated;
GRANT ALL ON chat_messages TO authenticated;

-- Comments for documentation
COMMENT ON TABLE chat_sessions IS 'Stores chat session metadata for conversational history';
COMMENT ON TABLE chat_messages IS 'Stores individual messages within chat sessions';
COMMENT ON COLUMN chat_sessions.user_id IS 'Supabase auth user ID (from auth.users)';
COMMENT ON COLUMN chat_sessions.title IS 'User-defined session title, defaults to "New Conversation"';
COMMENT ON COLUMN chat_messages.role IS 'Message role: user, assistant, or system';
COMMENT ON COLUMN chat_messages.ordering IS 'Message order within session (0-indexed)';
COMMENT ON COLUMN chat_messages.metadata IS 'Additional message metadata (model, tokens, etc.)';
