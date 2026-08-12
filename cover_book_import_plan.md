# Cover-Book Lesson Import — Plan

## Goal
Import 15 topic "books" (`AML, CHE, DSBD, IBT, IE, KB, LM, LOG, OFC, OW, SA, SC, SD, SR, TOU`)
from `content_info/Final/*.json` into the lesson tables, expose them as a **separate Books
section** with cover images, keep their progress **independent** of the HSK level system, and
wire audio to the per-code GCS folders (audio + covers uploaded manually).

## Source data (verified)
- 15 JSON files, all well-formed. **1,938 passages / 18,805 lines total.**
- `passage_id = {CODE}_{lesson}_{part}` (e.g. `AML_1_1`), 2 parts per lesson.
- Each line: `line_id, speaker, content, pinyin, audio_key ({CODE}_{lesson}_{part}_{line}),
  translations{en,vi}, tokens[]`. Translations are inline → **no `translation` table rows needed.**
- No vocab / grammar in the JSON → Books have lines only (vocab & grammar tabs hidden).
- Passage IDs are code-prefixed, so they never collide with the `H1_2_1` HSK IDs.
- Audio lives at `Audio_Combined/{CODE}/{audio_key}.mp3` → maps to GCS `lesson_audio/{CODE}/`.

## Decisions (confirmed)
1. **No new `books` table** — reuse the existing `lesson_passages` + `lesson_lines`. Add only a
   lightweight nullable `book_code` column on `lesson_passages` to separate book content from HSK.
2. **Skip titles for now** — books are identified by their code (`AML`, …); no title metadata yet.
3. Separate Books browse section (cover grid), not folded into the HSK picker.
4. Book progress is independent — never calls `recompute_user_level`.
5. User uploads audio & covers to GCS manually.
6. Book lessons have **no associated vocab** → the Word Summary screen must be handled (§9).

---

## 1. Schema (`schema_sql_file/schema.sql`)
```sql
-- Reuse lesson_passages / lesson_lines as-is; only tag book passages.
ALTER TABLE lesson_passages ADD COLUMN IF NOT EXISTS book_code VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_passages_book ON lesson_passages(book_code);
```
- Book passages: `book_code` set (e.g. `AML`), `hsk_level` left NULL (keeps them out of HSK
  queries/grouping). `passage_id` already carries the code, so this column is just a fast,
  explicit filter — no separate table, no title.
- Reuse `user_lesson_part_progress` (keyed by `passage_id`) for book progress — no new table.

## 2. Entity layer (SQLAlchemy, per entity/<model>/ pattern — Rule 2.5)
- Add `book_code` to the `LessonPassage` entity/repository. **No new entity package.**

## 3. Import script — `web_app/scripts/import_book_lessons.py`
- `--source <dir>` (default `../../content_info/Final`), `--dry-run` / `--apply`, `--codes` filter.
- For each of the 15 codes: upsert `lesson_passages` (set `book_code`, `hsk_level` NULL) and
  `lesson_lines` (line_id/speaker/content/pinyin/audio_key/translation_en/translation_vi/tokens).
- Idempotent upserts, single transaction per book, SQLAlchemy only. Follows the dry-run/apply
  style of `update_lesson_lines.py`.

## 4. Audio (frontend fix only)
- Backend `/lesson_audio/<path:filename>` already redirects arbitrary paths → **no change**.
- `web_app/static/lesson/lesson.js:193-197` currently forces an `HSK` prefix. Make it book-aware:
  when the task belongs to a book, use `/lesson_audio/{book_code}/{audio_key}.mp3`.
- Add `book_code` to the task payload built in `lesson_routes.start_session`.

## 5. Covers (GCS, by convention — no table)
- Convention: GCS `lesson_cover/{CODE}.png`.
- New route `/lesson-cover/<code>` → redirect `{GCS_BUCKET_URL}/lesson_cover/{code}.png`
  (mirrors existing `serve_lesson_image`). No DB row needed — cover URL derived from the code.
  **User uploads the 15 PNGs there.**

## 6. Backend API — `web_app/routes/lesson_routes.py` (+ db/content.py queries)
- `GET /api/lesson/books` → `[{book_code, cover_url, lesson_count, done_count}]`
  (derived via `SELECT DISTINCT book_code ...`; no title yet).
- `GET /api/lesson/book/<code>` → lessons → parts (`passage_id`, part index, completed flag).
- Reuse existing `/start`, `/passage/<id>`, `/vocab/<id>` (returns empty), `/part-complete`.
- `/part-complete`: when the passage has a `book_code`, **skip `recompute_user_level`** and the
  HSK mastery path; still record part completion in `user_lesson_part_progress`.

## 7. Frontend — Books section
- New browse page: cover grid (from `/api/lesson/books`) → book detail (lessons/parts with
  progress) → launches the existing trainer via `startSession(passage_id)`.
- Hide vocab & grammar tabs for book passages (no such data).
- Note: book passages have NULL hsk_level → trainer uses `DEFAULT_LESSON_TASK_COUNT` (10 tasks
  per part). Acceptable; adjust later if a book-specific count is wanted.

## 9. Word Summary handling (book lessons have NO vocab)
The Word Summary / vocab-learning flow fetches `/api/lesson/vocab/{passage_id}` →
`get_passage_vocab` → `passage_vocabulary` JOIN `vocabulary`. Book passages have **no**
`passage_vocabulary` rows, so today the screen would get an empty list and bounce back with
`vocab_learning.no_words_found` (`vocab_learning.js:130-134`). The book vocab is also specialized
(AI, finance, …) and largely absent from the HSK `vocabulary` table, so we can't rely on lookups.

**Recommended: skip the Word Summary for book lessons, go straight to the sentence trainer.**
Books are passage/sentence oriented (they map cleanly onto `lesson_lines`), and there is no curated
word list to show. The Books UI (§7) launches directly into the existing `/api/lesson/start`
trainer via `startSession(passage_id)` — never into the vocab-learning word-summary screen.

If a word list is still wanted later, two fallbacks (decide separately):
- **Derive from tokens** — build the list on the fly from each line's `tokens[]` (already well
  segmented in the JSON): dedupe, drop punctuation, and left-join `vocabulary` by `cn` to fill
  pinyin/meaning/audio where a match exists. Words with no match show Chinese only (no
  pinyin/meaning/per-word audio). Add a `source='tokens'` branch in `get_passage_vocab` /
  `/api/lesson/vocab` keyed on `book_code`.
- **Import passage_vocabulary** — match tokens to existing `vocabulary` at import time and insert
  the matches. Simplest data-wise but yields sparse lists (few specialized words exist in HSK vocab).

Also guard the empty-state so a book passage never hard-bounces if the vocab screen is reached:
show an informational empty state instead of the `no_words_found` alert.

**Decision: SKIP the Word Summary for book lessons.** The Books UI launches directly into the
sentence trainer; the vocab-learning word-summary screen is never entered for books, and the
empty-state guard is the only safety net. No token derivation, no `passage_vocabulary` import.

## 8. Manual steps (you)
- Upload audio to GCS `lesson_audio/{CODE}/` (folder = code) — filenames already match `audio_key`.
- Upload the 15 covers to GCS `lesson_cover/{CODE}.png`.
- Run the import script (`--dry-run` then `--apply`) with the DB env configured.

## Open / follow-up
- Book titles: skipped for now — code (`AML`, …) is the display label until a title map is provided.
- Per-book task counts / difficulty tuning if the default 10 feels off.
- Where the Books section links from in the main nav (confirm during UI step).
