-- 1. Create table for sematic_diffculty.csv
CREATE TABLE IF NOT EXISTS sematic_diffculty (
    word_id INTEGER PRIMARY KEY,
    sematic_difficulty NUMERIC,
    tags TEXT
);

-- 2. Create table for chinese_stroke_info.csv
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
    strokes_difficult_zh_norm NUMERIC
);

-- 3. Create table for chinese_dict.csv
CREATE TABLE IF NOT EXISTS chinese_dict (
    id INTEGER PRIMARY KEY,
    cn VARCHAR(255),
    zh VARCHAR(255),
    pinyin VARCHAR(255),
    audio_key VARCHAR(255),
    freq NUMERIC,
    pos VARCHAR(255),
    meaning_vn TEXT,
    meaning_en TEXT,
    tags TEXT
);
