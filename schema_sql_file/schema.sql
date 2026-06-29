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
-- 3. Users and Authentication
-- ==========================================

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    level SMALLINT DEFAULT 1
);

-- ==========================================
-- 4. User Progress and Records
-- ==========================================

CREATE TABLE IF NOT EXISTS lesson_records (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    session_id BIGINT,
    passage_id VARCHAR(255),
    line_id INTEGER,
    mode SMALLINT,
    game_info TEXT,
    user_answer TEXT,
    is_correct BOOLEAN,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vocab_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL,
    mode VARCHAR(50) NOT NULL,            -- e.g., 'listen', 'typing', 'meaning'
    word VARCHAR(100) NOT NULL,           -- the vocabulary word being tested
    round_num INTEGER DEFAULT 1,          -- tracks retry rounds for missed words
    game_info JSONB,                      -- stores flexible metadata like the presented options, pinyin, or HSK level
    user_answer TEXT,                     -- the user's actual input
    is_correct BOOLEAN NOT NULL,          -- whether the answer was marked correct
    response_time_ms INTEGER,             -- time taken to provide an answer
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE    -- time after a user answers the question
);

CREATE INDEX IF NOT EXISTS idx_user_learning_userid ON vocab_records(user_id);
CREATE INDEX IF NOT EXISTS idx_user_learning_session ON vocab_records(session_id);
CREATE INDEX IF NOT EXISTS idx_user_learning_user_word ON vocab_records(user_id, word);
CREATE INDEX IF NOT EXISTS idx_vocab_records_user_word_updated ON vocab_records(user_id, word, updated_at);

CREATE TABLE IF NOT EXISTS practice_record (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL,
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
-- 5. Question Bank and Recommendations
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

-- ==========================================
-- 6. Grammar
-- ==========================================

CREATE TABLE IF NOT EXISTS grammar_rule (
    id SERIAL PRIMARY KEY,
    grammar_id VARCHAR(50) NOT NULL,
    type SMALLINT,
    passage_number SMALLINT,
    vietnamese_content TEXT,
    english_content TEXT
);

CREATE INDEX IF NOT EXISTS idx_grammar_rule_id_passage ON grammar_rule(grammar_id, passage_number);

CREATE TABLE IF NOT EXISTS grammar_context (
    id SERIAL PRIMARY KEY,
    grammar_id VARCHAR(50) NOT NULL,
    content_json JSONB
);

-- ==========================================
-- Updates from profile_recent_learning
-- ==========================================

ALTER TABLE users
ADD COLUMN IF NOT EXISTS avatar_path TEXT;

CREATE TABLE IF NOT EXISTS user_learning_state (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current_passage_id VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_lesson_part_progress (
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    passage_id VARCHAR(255) NOT NULL,
    lesson_trainer_completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, passage_id)
);

CREATE INDEX IF NOT EXISTS idx_user_lesson_part_progress_user
ON user_lesson_part_progress(user_id);

-- ==========================================
-- Learn Together / Competitive Mode
-- ==========================================

CREATE TABLE IF NOT EXISTS competition_rooms (
    id BIGSERIAL PRIMARY KEY,
    room_code VARCHAR(12) NOT NULL UNIQUE,
    host_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(20) NOT NULL DEFAULT 'practice',
    level SMALLINT NOT NULL,
    lesson INTEGER NOT NULL,
    progress VARCHAR(30) NOT NULL,
    max_users SMALLINT NOT NULL DEFAULT 8,
    section_timeout_minutes SMALLINT NOT NULL DEFAULT 15,
    status VARCHAR(30) NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_competition_rooms_code
ON competition_rooms(room_code);
CREATE INDEX IF NOT EXISTS idx_competition_rooms_host_created
ON competition_rooms(host_user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_competition_rooms_status_created
ON competition_rooms(status, created_at);

CREATE TABLE IF NOT EXISTS competition_room_members (
    id BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL REFERENCES competition_rooms(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'participant',
    status VARCHAR(30) NOT NULL DEFAULT 'online',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (room_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_competition_members_room_status
ON competition_room_members(room_id, status);
CREATE INDEX IF NOT EXISTS idx_competition_members_user_joined
ON competition_room_members(user_id, joined_at);

CREATE TABLE IF NOT EXISTS competition_chat_messages (
    id BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL REFERENCES competition_rooms(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_competition_chat_room_created
ON competition_chat_messages(room_id, created_at);
CREATE INDEX IF NOT EXISTS idx_competition_chat_user_created
ON competition_chat_messages(user_id, created_at);

CREATE TABLE IF NOT EXISTS competition_sessions (
    id BIGSERIAL PRIMARY KEY,
    room_id BIGINT NOT NULL REFERENCES competition_rooms(id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'listening',
    current_section VARCHAR(20) NOT NULL DEFAULT 'listening',
    section_started_at TIMESTAMP WITH TIME ZONE,
    section_ends_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_competition_sessions_room_created
ON competition_sessions(room_id, created_at);
CREATE INDEX IF NOT EXISTS idx_competition_sessions_status_started
ON competition_sessions(status, started_at);
CREATE INDEX IF NOT EXISTS idx_competition_sessions_finished
ON competition_sessions(finished_at);

CREATE TABLE IF NOT EXISTS competition_session_questions (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES competition_sessions(id) ON DELETE CASCADE,
    source_question_id INTEGER,
    section VARCHAR(20) NOT NULL,
    section_order INTEGER NOT NULL,
    question_payload JSONB NOT NULL,
    correct_answer TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id, section, section_order)
);

CREATE INDEX IF NOT EXISTS idx_competition_questions_session_section
ON competition_session_questions(session_id, section);
CREATE INDEX IF NOT EXISTS idx_competition_questions_source
ON competition_session_questions(source_question_id);

CREATE TABLE IF NOT EXISTS competition_answers (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES competition_sessions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_question_id BIGINT NOT NULL REFERENCES competition_session_questions(id) ON DELETE CASCADE,
    section VARCHAR(20) NOT NULL,
    user_answer TEXT,
    is_correct BOOLEAN NOT NULL,
    response_time_ms INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id, user_id, session_question_id)
);

CREATE INDEX IF NOT EXISTS idx_competition_answers_session_user
ON competition_answers(session_id, user_id);
CREATE INDEX IF NOT EXISTS idx_competition_answers_session_question
ON competition_answers(session_id, session_question_id);
CREATE INDEX IF NOT EXISTS idx_competition_answers_user_submitted
ON competition_answers(user_id, submitted_at);

CREATE TABLE IF NOT EXISTS competition_scores (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES competition_sessions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listening_points INTEGER NOT NULL DEFAULT 0,
    reading_points INTEGER NOT NULL DEFAULT 0,
    total_points INTEGER NOT NULL DEFAULT 0,
    total_response_time_ms INTEGER NOT NULL DEFAULT 0,
    finished_at TIMESTAMP WITH TIME ZONE,
    rank INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_competition_scores_session_rank
ON competition_scores(session_id, total_points DESC, total_response_time_ms ASC);
CREATE INDEX IF NOT EXISTS idx_competition_scores_user_created
ON competition_scores(user_id, created_at);

ALTER TABLE practice_record
ADD COLUMN IF NOT EXISTS response_time_ms INTEGER;

ALTER TABLE practice_record
ADD COLUMN IF NOT EXISTS category VARCHAR(20) DEFAULT 'practice';

ALTER TABLE grammar_context ALTER COLUMN content_json TYPE json;
