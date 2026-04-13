-- TODO-DB1: Rename part_type → party_type in user_preference table
-- Run in Supabase dashboard BEFORE deploying the Python code changes.
ALTER TABLE user_preference RENAME COLUMN part_type TO party_type;
