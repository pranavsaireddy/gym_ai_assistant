-- ══════════════════════════════════════════════════════════
-- Migration 001: Cognitive Layer
-- Run once in Supabase SQL Editor
-- Adds user model columns + episodic memory table
-- ══════════════════════════════════════════════════════════

-- 1. pgvector extension (Supabase has this available)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. User model columns on members table
ALTER TABLE members ADD COLUMN IF NOT EXISTS fitness_goal          VARCHAR(200);
ALTER TABLE members ADD COLUMN IF NOT EXISTS preferred_workout_time VARCHAR(50);   -- 'morning' | 'evening' | 'afternoon'
ALTER TABLE members ADD COLUMN IF NOT EXISTS diet_preference        VARCHAR(200);  -- 'vegetarian' | 'non-veg' | 'vegan' | etc
ALTER TABLE members ADD COLUMN IF NOT EXISTS response_style         VARCHAR(20)  DEFAULT 'motivational'; -- 'terse' | 'detailed' | 'motivational'
ALTER TABLE members ADD COLUMN IF NOT EXISTS last_mood              VARCHAR(30)  DEFAULT 'unknown';      -- 'positive' | 'frustrated' | 'disengaged' | 'unknown'
ALTER TABLE members ADD COLUMN IF NOT EXISTS days_to_expiry         INTEGER;      -- computed daily, stored for fast access

-- 3. Episodic memory table (one row per conversation turn)
CREATE TABLE IF NOT EXISTS episodic_memory (
    id                  SERIAL PRIMARY KEY,
    yoactiv_member_id   VARCHAR(20) NOT NULL,
    timestamp           TIMESTAMPTZ DEFAULT NOW(),
    user_message        TEXT,
    assistant_reply     TEXT,
    agent_used          VARCHAR(100),                         -- comma-separated list of agents that ran
    mood                VARCHAR(30)  DEFAULT 'unknown',
    outcome             VARCHAR(30)  DEFAULT 'unknown',       -- positive_response | ignored | follow_up_asked | negative_response
    embedding           vector(384),                          -- all-MiniLM-L6-v2 output
    CONSTRAINT fk_episodic_member FOREIGN KEY (yoactiv_member_id)
        REFERENCES members(yoactiv_member_id) ON DELETE CASCADE
);

-- 4. Indexes
CREATE INDEX IF NOT EXISTS idx_episodic_member    ON episodic_memory (yoactiv_member_id);
CREATE INDEX IF NOT EXISTS idx_episodic_timestamp ON episodic_memory (timestamp DESC);
-- IVFFlat index for cosine similarity — needs at least 100 rows before it helps
-- Run this separately after you have data:
-- CREATE INDEX episodic_embedding_idx ON episodic_memory
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 5. Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'members'
  AND column_name IN ('fitness_goal','preferred_workout_time','diet_preference',
                      'response_style','last_mood','days_to_expiry')
ORDER BY column_name;