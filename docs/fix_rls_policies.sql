-- Fix RLS Policies for user_usage_stats Table
-- This migration adds missing INSERT and UPDATE policies for user_usage_stats
-- Run this SQL in your Supabase SQL Editor to fix RLS violations

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS user_usage_stats_insert_policy ON user_usage_stats;
DROP POLICY IF EXISTS user_usage_stats_update_policy ON user_usage_stats;

-- Add INSERT policy: Users can insert their own usage stats
CREATE POLICY user_usage_stats_insert_policy ON user_usage_stats
    FOR INSERT
    WITH CHECK (auth.uid()::text = user_id);

-- Add UPDATE policy: Users can update their own usage stats
CREATE POLICY user_usage_stats_update_policy ON user_usage_stats
    FOR UPDATE
    USING (auth.uid()::text = user_id);

-- Update grants to allow INSERT and UPDATE operations
-- (if not already granted)
GRANT INSERT, UPDATE ON user_usage_stats TO authenticated;

-- Verify policies were created
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE tablename = 'user_usage_stats'
ORDER BY policyname;
