-- Enable uuid-ossp extension if you plan to use UUID generation locally
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table to store vocabulary words
CREATE TABLE words (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    word VARCHAR(100) NOT NULL UNIQUE,
    pinyin VARCHAR(100) NOT NULL,
    meaning_vn TEXT,
    meaning_en TEXT,
    level VARCHAR(50),
    audio_key VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- Recommended Indexes for Performance
-- ==========================================

-- 1. Index to quickly search by word
CREATE INDEX idx_words_word ON words(word);

-- 2. Index to retrieve all words for a specific HSK level
CREATE INDEX idx_words_level ON words(level);
