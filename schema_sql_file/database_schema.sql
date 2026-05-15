-- Enable uuid-ossp extension if you plan to use UUID generation locally
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table to track user learning progress and performance
CREATE TABLE vocab_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    session_id UUID NOT NULL,
    mode VARCHAR(50) NOT NULL,            -- e.g., 'listen', 'typing', 'meaning'
    word VARCHAR(100) NOT NULL,           -- the vocabulary word being tested
    round_num INTEGER DEFAULT 1,          -- tracks retry rounds for missed words
    game_info JSONB,                      -- stores flexible metadata like the presented options, pinyin, or HSK level
    user_answer TEXT,                     -- the user's actual input
    is_correct BOOLEAN NOT NULL,          -- whether the answer was marked correct
    response_time_ms INTEGER,             -- time taken to provide an answer
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_at TIMESTAMP WITH TIME ZONE    -- time after a user answers the question
);

-- ==========================================
-- Recommended Indexes for Performance
-- ==========================================

-- 1. Index to quickly pull all history for a specific user
CREATE INDEX idx_user_learning_userid ON vocab_records(user_id);

-- 2. Index to retrieve all answers in a specific game session
CREATE INDEX idx_user_learning_session ON vocab_records(session_id);

-- 3. Composite Index to map out the weakest words for a user (fast calculation of how often a user gets a specific word wrong)
CREATE INDEX idx_user_learning_user_word ON vocab_records(user_id, word);
