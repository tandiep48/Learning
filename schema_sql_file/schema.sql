-- Enable uuid-ossp extension if you plan to use UUID generation locally
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- 1. Core Vocabulary and Passage Content
-- ==========================================

CREATE TABLE IF NOT EXISTS vocabulary (
    id SERIAL PRIMARY KEY,
    cn VARCHAR(100) NOT NULL UNIQUE,
    pinyin VARCHAR(100),
    meaning_en TEXT,
    meaning_vn TEXT,
    audio_key VARCHAR(100),
    hsk_level VARCHAR(10),
    source VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_vocab_source ON vocabulary(source);
CREATE INDEX IF NOT EXISTS idx_vocab_hsk ON vocabulary(hsk_level);

CREATE TABLE IF NOT EXISTS lesson_passages (
    passage_id VARCHAR(100) PRIMARY KEY,
    hsk_level VARCHAR(10),
    content JSONB
);

CREATE INDEX IF NOT EXISTS idx_passages_hsk ON lesson_passages(hsk_level);

CREATE TABLE IF NOT EXISTS passage_vocabulary (
    passage_id VARCHAR(100),
    cn VARCHAR(100),
    PRIMARY KEY (passage_id, cn),
    CONSTRAINT fk_passage FOREIGN KEY (passage_id) REFERENCES lesson_passages(passage_id) ON DELETE CASCADE,
    CONSTRAINT fk_pv_vocab FOREIGN KEY (cn) REFERENCES vocabulary(cn) ON DELETE CASCADE
);

-- ==========================================
-- 2. Extended Vocabulary Info
-- ==========================================

CREATE TABLE IF NOT EXISTS sematic_diffculty (
    word_id INTEGER PRIMARY KEY,
    sematic_difficulty NUMERIC,
    tags TEXT,
    CONSTRAINT fk_sematic_vocab FOREIGN KEY (word_id) REFERENCES vocabulary(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chinese_stroke_info (
    cn VARCHAR(255) PRIMARY KEY,
    zh VARCHAR(255),
    total_strokes_cn INTEGER,
    total_strokes_zh INTEGER,
    strokes_cn TEXT,
    strokes_zh TEXT,
    word_length INTEGER,
    strokes_difficult_cn NUMERIC,
    strokes_difficult_cn_norm NUMERIC,
    strokes_difficult_zh NUMERIC,
    strokes_difficult_zh_norm NUMERIC,
    CONSTRAINT fk_stroke_vocab FOREIGN KEY (cn) REFERENCES vocabulary(cn) ON DELETE CASCADE
);

-- ==========================================
-- 3. User Progress and Records
-- ==========================================

CREATE TABLE IF NOT EXISTS lesson_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    session_id UUID,
    passage_id VARCHAR(255),
    line_id INTEGER,
    mode VARCHAR(50), 
    game_info TEXT,
    user_answer TEXT,
    is_correct BOOLEAN,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vocab_records (
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

CREATE INDEX IF NOT EXISTS idx_user_learning_userid ON vocab_records(user_id);
CREATE INDEX IF NOT EXISTS idx_user_learning_session ON vocab_records(session_id);
CREATE INDEX IF NOT EXISTS idx_user_learning_user_word ON vocab_records(user_id, word);

CREATE TABLE IF NOT EXISTS practice_record (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_id UUID NOT NULL,
    hsk_level INTEGER,
    lesson VARCHAR(50),
    question_no INTEGER,
    skill VARCHAR(50),
    question_type INTEGER,
    user_answer TEXT,
    is_correct BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_practice_record_user_session ON practice_record(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_practice_record_lesson ON practice_record(hsk_level, lesson);

-- ==========================================
-- 4. Question Bank and Recommendations
-- ==========================================

-- Enum for question category
DO $$ BEGIN
    CREATE TYPE question_category AS ENUM ('practice', 'exam');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Enum for question skill
DO $$ BEGIN
    CREATE TYPE question_skill AS ENUM ('listening', 'reading');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS question_bank (
    id          SERIAL PRIMARY KEY,
    level       SMALLINT NOT NULL,
    category    question_category NOT NULL,
    lesson      INTEGER NOT NULL,
    no          INTEGER NOT NULL,
    skill       question_skill,
    type        SMALLINT NOT NULL,
    content     TEXT,
    question    TEXT,
    answer      VARCHAR(50),
    audio_key   TEXT,
    image       VARCHAR(255),
    options     JSONB,
    progress    VARCHAR(30) NOT NULL,
    unit_id     VARCHAR(20) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_qb_category_level_lesson ON question_bank(category, level, lesson);
CREATE INDEX IF NOT EXISTS idx_qb_progress              ON question_bank(level, lesson, progress);
CREATE INDEX IF NOT EXISTS idx_qb_unit_id               ON question_bank(unit_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qb_unique         ON question_bank(category, level, lesson, no);

CREATE TABLE IF NOT EXISTS learning_units (
    id          SERIAL PRIMARY KEY,
    unit_id     VARCHAR(20)  NOT NULL,
    unique_word VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lu_unit_id ON learning_units(unit_id);
CREATE INDEX IF NOT EXISTS idx_lu_word    ON learning_units(unique_word);
