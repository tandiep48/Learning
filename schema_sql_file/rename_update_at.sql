-- Rename progress tracking tables to new naming convention
ALTER TABLE IF EXISTS user_learning_progress RENAME TO vocab_records;
ALTER TABLE IF EXISTS lesson_learning_progress RENAME TO lesson_records;
