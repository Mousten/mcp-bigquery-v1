-- Complete Supabase Schema for MCP BigQuery Server
-- This schema includes all tables required for the MCP BigQuery Server with Streamlit agent
-- Tables: RBAC, Chat Persistence, Caching, Usage Tracking, and User Preferences

-- ========================================
-- RBAC (Role-Based Access Control) Schema
-- ========================================

-- User profiles table
-- Stores additional user metadata beyond what's in Supabase auth.users
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

-- Application roles table
-- Defines available roles in the system
CREATE TABLE IF NOT EXISTS app_roles (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_roles_name ON app_roles(role_name);

-- User role assignments table
-- Maps users to their assigned roles
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    role_id TEXT NOT NULL REFERENCES app_roles(role_id) ON DELETE CASCADE,
    role_name TEXT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);

-- Role permissions table
-- Defines permissions associated with each role
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id TEXT NOT NULL REFERENCES app_roles(role_id) ON DELETE CASCADE,
    permission TEXT NOT NULL,
    description TEXT,
    UNIQUE(role_id, permission)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_permission ON role_permissions(permission);

-- Role dataset access table
-- Controls which datasets and tables each role can access
CREATE TABLE IF NOT EXISTS role_dataset_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id TEXT NOT NULL REFERENCES app_roles(role_id) ON DELETE CASCADE,
    dataset_id TEXT NOT NULL,
    table_id TEXT,
    access_level TEXT DEFAULT 'read',
    UNIQUE(role_id, dataset_id, table_id)
);

CREATE INDEX IF NOT EXISTS idx_role_dataset_access_role_id ON role_dataset_access(role_id);
CREATE INDEX IF NOT EXISTS idx_role_dataset_access_dataset ON role_dataset_access(dataset_id);

COMMENT ON TABLE user_profiles IS 'Extended user profile data beyond Supabase auth.users';
COMMENT ON TABLE app_roles IS 'Application roles for RBAC (e.g., analyst, admin, viewer)';
COMMENT ON TABLE user_roles IS 'Maps users to their assigned roles';
COMMENT ON TABLE role_permissions IS 'Permissions granted to each role (e.g., query:execute, cache:read)';
COMMENT ON TABLE role_dataset_access IS 'Dataset and table access control for roles';

-- ========================================
-- Chat Persistence Schema
-- ========================================

-- Chat sessions table
-- Stores session metadata for each conversation
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_ordering ON chat_messages(session_id, ordering);

-- Trigger to update session timestamp when messages are added
CREATE OR REPLACE FUNCTION update_chat_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chat_sessions 
    SET updated_at = NOW() 
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_chat_session_timestamp ON chat_messages;
CREATE TRIGGER trigger_update_chat_session_timestamp
    AFTER INSERT ON chat_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_chat_session_timestamp();

COMMENT ON TABLE chat_sessions IS 'Stores chat session metadata for conversational history';
COMMENT ON TABLE chat_messages IS 'Stores individual messages within chat sessions';

-- ========================================
-- Caching Schema
-- ========================================

-- Query cache table
-- Stores cached BigQuery query results
CREATE TABLE IF NOT EXISTS query_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    sql_text TEXT NOT NULL,
    result_data JSONB NOT NULL,
    row_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_cache_hash_user ON query_cache(query_hash, user_id);
CREATE INDEX IF NOT EXISTS idx_query_cache_expires ON query_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_query_cache_user_id ON query_cache(user_id);

-- Metadata cache table
-- Stores cached BigQuery metadata (schemas, datasets, tables)
CREATE TABLE IF NOT EXISTS metadata_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cache_key TEXT NOT NULL UNIQUE,
    cache_type TEXT NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metadata_cache_key ON metadata_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_metadata_cache_type ON metadata_cache(cache_type);
CREATE INDEX IF NOT EXISTS idx_metadata_cache_expires ON metadata_cache(expires_at);

COMMENT ON TABLE query_cache IS 'Cached BigQuery query results (user-scoped for security)';
COMMENT ON TABLE metadata_cache IS 'Cached BigQuery metadata (schemas, datasets, tables)';

-- ========================================
-- Usage Tracking Schema
-- ========================================

-- User usage statistics table
-- Tracks token consumption and request counts per user per day
CREATE TABLE IF NOT EXISTS user_usage_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    tokens_consumed INTEGER NOT NULL DEFAULT 0,
    requests_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, period_start)
);

CREATE INDEX IF NOT EXISTS idx_user_usage_stats_user_id ON user_usage_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_stats_period ON user_usage_stats(period_start DESC);

COMMENT ON TABLE user_usage_stats IS 'Daily aggregated token usage and request counts per user';
COMMENT ON COLUMN user_usage_stats.metadata IS 'Provider/model breakdown: {providers: {openai: {gpt-4: {tokens: 1000, requests: 5}}}}';

-- User preferences table
-- Stores user-specific preferences including token quotas
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

COMMENT ON TABLE user_preferences IS 'User-specific preferences and settings';
COMMENT ON COLUMN user_preferences.preferences IS 'JSON preferences: {daily_token_quota: 10000, monthly_token_quota: 100000, default_llm_provider: "openai"}';

-- ========================================
-- Row Level Security (RLS) Policies
-- ========================================

-- Enable RLS on all tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_dataset_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE metadata_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_usage_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- User Profiles Policies
CREATE POLICY user_profiles_select_policy ON user_profiles
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY user_profiles_update_policy ON user_profiles
    FOR UPDATE USING (auth.uid()::text = user_id);

-- App Roles Policies (all authenticated users can read)
CREATE POLICY app_roles_select_policy ON app_roles
    FOR SELECT TO authenticated USING (true);

-- User Roles Policies
CREATE POLICY user_roles_select_policy ON user_roles
    FOR SELECT USING (auth.uid()::text = user_id);

-- Role Permissions Policies
CREATE POLICY role_permissions_select_policy ON role_permissions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_roles 
            WHERE user_roles.role_id = role_permissions.role_id 
            AND user_roles.user_id = auth.uid()::text
        )
    );

-- Role Dataset Access Policies
CREATE POLICY role_dataset_access_select_policy ON role_dataset_access
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_roles 
            WHERE user_roles.role_id = role_dataset_access.role_id 
            AND user_roles.user_id = auth.uid()::text
        )
    );

-- Chat Sessions Policies
CREATE POLICY chat_sessions_select_policy ON chat_sessions
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY chat_sessions_insert_policy ON chat_sessions
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY chat_sessions_update_policy ON chat_sessions
    FOR UPDATE USING (auth.uid()::text = user_id);

CREATE POLICY chat_sessions_delete_policy ON chat_sessions
    FOR DELETE USING (auth.uid()::text = user_id);

-- Chat Messages Policies
CREATE POLICY chat_messages_select_policy ON chat_messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

CREATE POLICY chat_messages_insert_policy ON chat_messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

CREATE POLICY chat_messages_update_policy ON chat_messages
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

CREATE POLICY chat_messages_delete_policy ON chat_messages
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM chat_sessions 
            WHERE chat_sessions.id = chat_messages.session_id 
            AND chat_sessions.user_id = auth.uid()::text
        )
    );

-- Query Cache Policies
CREATE POLICY query_cache_select_policy ON query_cache
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY query_cache_insert_policy ON query_cache
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY query_cache_delete_policy ON query_cache
    FOR DELETE USING (auth.uid()::text = user_id);

-- Metadata Cache Policies (all authenticated users can read)
CREATE POLICY metadata_cache_select_policy ON metadata_cache
    FOR SELECT TO authenticated USING (true);

-- User Usage Stats Policies
CREATE POLICY user_usage_stats_select_policy ON user_usage_stats
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY user_usage_stats_insert_policy ON user_usage_stats
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY user_usage_stats_update_policy ON user_usage_stats
    FOR UPDATE USING (auth.uid()::text = user_id);

-- User Preferences Policies
CREATE POLICY user_preferences_select_policy ON user_preferences
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY user_preferences_insert_policy ON user_preferences
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY user_preferences_update_policy ON user_preferences
    FOR UPDATE USING (auth.uid()::text = user_id);

-- ========================================
-- Grant Permissions
-- ========================================

GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON user_profiles TO authenticated;
GRANT SELECT ON app_roles TO authenticated;
GRANT SELECT ON user_roles TO authenticated;
GRANT SELECT ON role_permissions TO authenticated;
GRANT SELECT ON role_dataset_access TO authenticated;
GRANT ALL ON chat_sessions TO authenticated;
GRANT ALL ON chat_messages TO authenticated;
GRANT ALL ON query_cache TO authenticated;
GRANT SELECT ON metadata_cache TO authenticated;
GRANT ALL ON user_usage_stats TO authenticated;
GRANT ALL ON user_preferences TO authenticated;

-- ========================================
-- Sample Data (Optional - Uncomment to Use)
-- ========================================

-- Sample roles
-- INSERT INTO app_roles (role_id, role_name, description) VALUES
--     ('role-analyst', 'analyst', 'Data analyst with query execution permissions'),
--     ('role-viewer', 'viewer', 'Read-only viewer with limited access'),
--     ('role-admin', 'admin', 'Administrator with full access');

-- Sample permissions
-- INSERT INTO role_permissions (role_id, permission, description) VALUES
--     ('role-analyst', 'query:execute', 'Execute BigQuery queries'),
--     ('role-analyst', 'cache:read', 'Read from query cache'),
--     ('role-analyst', 'cache:write', 'Write to query cache'),
--     ('role-analyst', 'schema:read', 'Read dataset/table schemas'),
--     ('role-viewer', 'schema:read', 'Read dataset/table schemas'),
--     ('role-admin', 'query:execute', 'Execute BigQuery queries'),
--     ('role-admin', 'cache:read', 'Read from query cache'),
--     ('role-admin', 'cache:write', 'Write to query cache'),
--     ('role-admin', 'cache:invalidate', 'Invalidate cache entries'),
--     ('role-admin', 'schema:read', 'Read dataset/table schemas');

-- Sample dataset access
-- INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level) VALUES
--     ('role-analyst', 'public_data', NULL, 'read'),
--     ('role-analyst', 'analytics', 'events', 'read'),
--     ('role-viewer', 'public_data', NULL, 'read'),
--     ('role-admin', '*', NULL, 'read');  -- Wildcard for all datasets
