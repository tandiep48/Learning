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
