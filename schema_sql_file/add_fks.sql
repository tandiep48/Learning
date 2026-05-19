-- Drop and recreate passage_vocabulary to include id and word_id
DROP TABLE IF EXISTS passage_vocabulary;

CREATE TABLE passage_vocabulary (
    id SERIAL PRIMARY KEY,
    passage_id VARCHAR(100),
    word_id INT,
    cn VARCHAR(100)
);

-- Ensure chinese_dict has a primary key on id
ALTER TABLE chinese_dict DROP CONSTRAINT IF EXISTS chinese_dict_pkey CASCADE;
ALTER TABLE chinese_dict ADD PRIMARY KEY (id);

-- Ensure lesson_passages has a primary key
ALTER TABLE lesson_passages DROP CONSTRAINT IF EXISTS lesson_passages_pkey CASCADE;
ALTER TABLE lesson_passages ADD PRIMARY KEY (passage_id);

-- Add Foreign Keys
ALTER TABLE passage_vocabulary 
ADD CONSTRAINT fk_passage 
FOREIGN KEY (passage_id) REFERENCES lesson_passages(passage_id) ON DELETE CASCADE;

ALTER TABLE passage_vocabulary 
ADD CONSTRAINT fk_word 
FOREIGN KEY (word_id) REFERENCES chinese_dict(id) ON DELETE CASCADE;

ALTER TABLE sematic_diffculty DROP CONSTRAINT IF EXISTS fk_sematic_dict;
ALTER TABLE sematic_diffculty 
ADD CONSTRAINT fk_sematic_dict 
FOREIGN KEY (word_id) REFERENCES chinese_dict(id) ON DELETE CASCADE;
