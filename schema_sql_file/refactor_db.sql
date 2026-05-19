-- STEP 1: Deduplicate vocabulary table
-- 1a. Merge data (preferring non-null hsk_level from duplicates)
UPDATE vocabulary v1
SET hsk_level = COALESCE(v1.hsk_level, v2.hsk_level),
    audio_key = COALESCE(v1.audio_key, v2.audio_key)
FROM vocabulary v2
WHERE v1.cn = v2.cn AND v1.id < v2.id;

-- 1b. Delete duplicates (keeping the one with the smallest ID)
DELETE FROM vocabulary v1
USING vocabulary v2
WHERE v1.cn = v2.cn AND v1.id > v2.id;

-- 1c. Add UNIQUE constraint to vocabulary.cn
ALTER TABLE vocabulary ADD CONSTRAINT vocab_cn_unique UNIQUE (cn);


-- STEP 3: Remap Foreign Keys
-- Note: sematic_diffculty currently points to chinese_dict.id. 
-- We need to change it to point to vocabulary.id

-- Add a temporary column to map
ALTER TABLE sematic_diffculty ADD COLUMN new_word_id INT;

-- Update the new word_id based on matching 'cn'
UPDATE sematic_diffculty s
SET new_word_id = v.id
FROM chinese_dict c
JOIN vocabulary v ON c.cn = v.cn
WHERE s.word_id = c.id;

-- Drop old constraint and column
ALTER TABLE sematic_diffculty DROP CONSTRAINT IF EXISTS fk_sematic_dict;
ALTER TABLE sematic_diffculty DROP COLUMN word_id;

-- Rename and add new constraint
ALTER TABLE sematic_diffculty RENAME COLUMN new_word_id TO word_id;

-- Delete any orphaned semantic difficulty rows (where word didn't exist in vocabulary)
DELETE FROM sematic_diffculty WHERE word_id IS NULL;

ALTER TABLE sematic_diffculty 
ADD CONSTRAINT fk_sematic_vocab 
FOREIGN KEY (word_id) REFERENCES vocabulary(id) ON DELETE CASCADE;

-- Update chinese_stroke_info
ALTER TABLE chinese_stroke_info DROP CONSTRAINT IF EXISTS fk_stroke_vocab;
ALTER TABLE chinese_stroke_info 
ADD CONSTRAINT fk_stroke_vocab 
FOREIGN KEY (cn) REFERENCES vocabulary(cn) ON DELETE CASCADE;

-- Update passage_vocabulary
ALTER TABLE passage_vocabulary DROP CONSTRAINT IF EXISTS fk_word;
ALTER TABLE passage_vocabulary DROP COLUMN word_id;

-- Ensure passage_vocabulary only has entries that exist in vocabulary
DELETE FROM passage_vocabulary pv
WHERE NOT EXISTS (SELECT 1 FROM vocabulary v WHERE v.cn = pv.cn);

ALTER TABLE passage_vocabulary 
ADD CONSTRAINT fk_pv_vocab 
FOREIGN KEY (cn) REFERENCES vocabulary(cn) ON DELETE CASCADE;


-- STEP 4 part 1: Safely drop deprecated tables
DROP TABLE IF EXISTS chinese_dict CASCADE;
DROP TABLE IF EXISTS words CASCADE;
