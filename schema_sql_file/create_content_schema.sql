CREATE TABLE IF NOT EXISTS vocabulary (
    id SERIAL PRIMARY KEY,
    cn VARCHAR(100) NOT NULL,
    pinyin VARCHAR(100),
    meaning_en TEXT,
    meaning_vn TEXT,
    audio_key VARCHAR(100),
    hsk_level VARCHAR(10),
    source VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS lesson_passages (
    passage_id VARCHAR(100) PRIMARY KEY,
    hsk_level VARCHAR(10),
    content JSONB
);

CREATE TABLE IF NOT EXISTS passage_vocabulary (
    passage_id VARCHAR(100),
    cn VARCHAR(100),
    PRIMARY KEY (passage_id, cn)
);

-- Indexes for fast querying
CREATE INDEX idx_vocab_source ON vocabulary(source);
CREATE INDEX idx_vocab_hsk ON vocabulary(hsk_level);
CREATE INDEX idx_passages_hsk ON lesson_passages(hsk_level);
