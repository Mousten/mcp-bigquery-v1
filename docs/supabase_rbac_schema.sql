-- RBAC (Role-Based Access Control) schema for Supabase
-- This schema supports authentication and authorization for BigQuery dataset/table access

-- User profiles table
-- Stores additional user metadata beyond what's in Supabase auth.users
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

-- Application roles table
-- Defines available roles in the system
CREATE TABLE IF NOT EXISTS app_roles (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast role name lookups
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

-- Indexes for fast user and role lookups
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

-- Index for fast role permission lookups
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

-- Indexes for fast dataset access lookups
CREATE INDEX IF NOT EXISTS idx_role_dataset_access_role_id ON role_dataset_access(role_id);
CREATE INDEX IF NOT EXISTS idx_role_dataset_access_dataset ON role_dataset_access(dataset_id);

-- Row Level Security (RLS) Policies
-- Enable RLS on all tables (service role key will bypass RLS)
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_dataset_access ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own profile
CREATE POLICY user_profiles_select_policy ON user_profiles
    FOR SELECT
    USING (auth.uid()::text = user_id);

-- Policy: Users can update their own profile metadata
CREATE POLICY user_profiles_update_policy ON user_profiles
    FOR UPDATE
    USING (auth.uid()::text = user_id);

-- Policy: All authenticated users can read roles (for discovery)
CREATE POLICY app_roles_select_policy ON app_roles
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy: Users can read their own role assignments
CREATE POLICY user_roles_select_policy ON user_roles
    FOR SELECT
    USING (auth.uid()::text = user_id);

-- Policy: Users can read permissions for their assigned roles
CREATE POLICY role_permissions_select_policy ON role_permissions
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles 
            WHERE user_roles.role_id = role_permissions.role_id 
            AND user_roles.user_id = auth.uid()::text
        )
    );

-- Policy: Users can read dataset access for their assigned roles
CREATE POLICY role_dataset_access_select_policy ON role_dataset_access
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles 
            WHERE user_roles.role_id = role_dataset_access.role_id 
            AND user_roles.user_id = auth.uid()::text
        )
    );

-- Grant usage to authenticated users
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON user_profiles TO authenticated;
GRANT SELECT ON app_roles TO authenticated;
GRANT SELECT ON user_roles TO authenticated;
GRANT SELECT ON role_permissions TO authenticated;
GRANT SELECT ON role_dataset_access TO authenticated;

-- Comments for documentation
COMMENT ON TABLE user_profiles IS 'Extended user profile data beyond Supabase auth.users';
COMMENT ON TABLE app_roles IS 'Application roles for RBAC (e.g., analyst, admin, viewer)';
COMMENT ON TABLE user_roles IS 'Maps users to their assigned roles';
COMMENT ON TABLE role_permissions IS 'Permissions granted to each role (e.g., query:execute, cache:read)';
COMMENT ON TABLE role_dataset_access IS 'Dataset and table access control for roles';

COMMENT ON COLUMN user_profiles.user_id IS 'Supabase auth user ID (from auth.users)';
COMMENT ON COLUMN user_profiles.metadata IS 'Additional user metadata (preferences, settings, etc.)';
COMMENT ON COLUMN app_roles.role_id IS 'Unique role identifier';
COMMENT ON COLUMN app_roles.role_name IS 'Human-readable role name';
COMMENT ON COLUMN user_roles.user_id IS 'Supabase auth user ID';
COMMENT ON COLUMN user_roles.role_id IS 'Reference to app_roles.role_id';
COMMENT ON COLUMN user_roles.role_name IS 'Denormalized role name for faster lookups';
COMMENT ON COLUMN role_permissions.permission IS 'Permission string (e.g., query:execute, cache:read)';
COMMENT ON COLUMN role_dataset_access.dataset_id IS 'BigQuery dataset identifier (use "*" for wildcard access)';
COMMENT ON COLUMN role_dataset_access.table_id IS 'BigQuery table identifier (use "*" for wildcard, NULL for all tables in dataset)';
COMMENT ON COLUMN role_dataset_access.access_level IS 'Access level (default: read)';

-- Sample data for testing (optional - uncomment to use)
-- INSERT INTO app_roles (role_id, role_name, description) VALUES
--     ('role-analyst', 'analyst', 'Data analyst with query execution permissions'),
--     ('role-viewer', 'viewer', 'Read-only viewer with limited access'),
--     ('role-admin', 'admin', 'Administrator with full access');

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

-- INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level) VALUES
--     ('role-analyst', 'public_data', NULL, 'read'),
--     ('role-analyst', 'analytics', 'events', 'read'),
--     ('role-viewer', 'public_data', NULL, 'read'),
--     ('role-admin', '*', NULL, 'read');
