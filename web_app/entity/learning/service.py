"""
entity/learning/service.py
---------------------------
Business logic for a user's vocabulary-learning state and practice history —
mastered words, practice recommendations, practice sessions, and the
unlearned / unsure / review / hard-word selections.

Every function here is read-only; the session lifecycle only ever needs
remove(), never commit()/rollback(). Manages that lifecycle and shapes
repository rows into the plain dicts/lists callers expect.
"""

from entity.database import SessionLocal
from entity.learning.repository import LearningRepository
from entity.record.service import get_learned_words


def get_mastered_words_with_recency(user_id):
    """
    Returns mastered words with the timestamp of the latest mastered learning day
    (word + learned_at only). Uses the same 3-mode round-1 mastery rule as
    get_learned_words(). Kept lightweight — no vocabulary join — since callers only
    need the word and its recency; per-word details come from get_mastered_words_page().
    """
    session = SessionLocal()
    try:
        rows = LearningRepository(session).get_mastered_words_with_recency(user_id)
        return [{"word": r[0], "learned_at": r[1]} for r in rows]
    except Exception as e:
        print(f"⚠️ Database query failed (get_mastered_words_with_recency): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_mastered_words_page(user_id, page=1, page_size=24):
    """
    Returns one page of mastered words with the timestamp of the latest mastered learning day.
    Uses the same 3-mode round-1 mastery rule as get_learned_words().
    """
    page_size = min(100, max(1, int(page_size or 24)))
    page = max(1, int(page or 1))

    session = SessionLocal()
    try:
        repo = LearningRepository(session)
        total = repo.get_mastered_words_total(user_id)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size

        rows = repo.get_mastered_words_rows(user_id, page_size, offset)
        return {
            "rows": [
                {
                    "word": row[0],
                    "cn": row[0],
                    "learned_at": row[1].isoformat() if hasattr(row[1], "isoformat") else row[1],
                    "pinyin": row[2] or "",
                    "meaning_vn": row[3] or "",
                    "meaning_en": row[4] or "",
                    "audio_key": row[5] or "",
                    "hsk_level": row[6] or "",
                    "level": row[6] or "",
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        }
    except Exception as e:
        print(f"⚠️ Database query failed (get_mastered_words_page): {e}")
        return {"rows": [], "page": 1, "page_size": page_size, "total": 0, "total_pages": 1}
    finally:
        SessionLocal.remove()


def get_recommended_practices(user_id, threshold=0.80, limit=None, status_filter=None):
    """
    Returns practice progress groups the user is ready for.
    Uses question_bank + learning_units + vocab_records — NO CSV loading.

    A group is recommended when coverage = known_words/total_words >= threshold,
    measured over the user's ENTIRE mastered-word set (no recency or HSK-level bias).
    Groups are ordered by coverage (highest first).

    Returns list of dicts:
      {level, lesson, progress, skill, type, category, status, unit_ids,
       total_words, known_words, coverage, coverage_pct, matched_words, question_count}
    """
    session = SessionLocal()
    try:
        # Every mastered word (3-mode round-1 rule). No recency or HSK-level bias —
        # the whole mastered set drives coverage.
        mastered = get_learned_words(user_id)
        if not mastered:
            return []
        mastered_list = list(mastered)

        repo = LearningRepository(session)

        group_coverage = {
            (row[0], row[1], row[2], row[3]): {
                'total_words': row[4],
                'known_words': row[5],
                'coverage': row[5] / row[4],
                'matched_words': row[6] or [],
            }
            for row in repo.get_group_words_coverage(mastered_list)
            if row[4] > 0
        }

        ready_keys = {k for k, d in group_coverage.items() if d['coverage'] >= threshold}
        if not ready_keys:
            return []

        # Bound the status scan to the ready groups' lessons so we don't join the user's
        # entire practice history on every call.
        ready_levels = list({k[1] for k in ready_keys})
        ready_lessons = list({str(k[2]) for k in ready_keys})

        lesson_status = {}
        for r in repo.get_group_latest_status(user_id, ready_levels, ready_lessons):
            cat, lvl, les, prog, pct = r[0], r[1], r[2], r[3], r[4]
            key = (cat, lvl, int(les) if str(les).isdigit() else les, prog)
            lesson_status[key] = "Finish and success" if pct == 1.0 else "Finish and fail"

        # Build lightweight summaries before fetching per-group metadata.
        summaries = []
        for category, level, lesson, progress in ready_keys:
            status = lesson_status.get((category, level, lesson, progress), "Not start")
            if status_filter and status != status_filter:
                continue
            data = group_coverage[(category, level, lesson, progress)]
            summaries.append({
                'level':        level,
                'lesson':       lesson,
                'progress':     progress,
                'category':     category,
                'status':       status,
                'total_words':  data['total_words'],
                'known_words':  data['known_words'],
                'coverage':     round(data['coverage'], 4),
                'coverage_pct': round(data['coverage'] * 100, 1),
                'matched_words': sorted(data['matched_words']),
            })

        # Order by coverage (highest first); stable tie-break on level/lesson/progress so
        # the list is deterministic between calls.
        summaries.sort(key=lambda s: (s['level'], s['lesson'], str(s['progress'])))
        summaries.sort(key=lambda s: s['coverage'], reverse=True)
        if limit:
            summaries = summaries[:limit]
        if not summaries:
            return []

        # Fetch only lightweight per-group metadata (count + representative skill/type +
        # unit ids). The full question payloads aren't needed here — the practice screen
        # loads them on demand.
        meta_by_key = {
            (r[0], r[1], r[2], r[3]): {
                'question_count': r[4],
                'skill':          r[5] or 'listening',
                'type':           r[6],
                'unit_ids':       sorted(r[7] or []),
            }
            for r in repo.get_group_metadata(
                [(s['category'], s['level'], s['lesson'], s['progress']) for s in summaries]
            )
        }

        results = []
        for item in summaries:
            key = (item['category'], item['level'], item['lesson'], item['progress'])
            meta = meta_by_key.get(key)
            if not meta or not meta['question_count']:
                continue
            item['skill'] = meta['skill']
            item['type'] = meta['type']
            item['unit_ids'] = meta['unit_ids']
            item['question_count'] = meta['question_count']
            results.append(item)

        return results
    except Exception as e:
        print(f"[WARN] get_recommended_practices failed: {e}")
        return []
    finally:
        SessionLocal.remove()


def get_practice_history_sessions(user_id, hsk_level=None, category=None,
                                   date=None, sort='recent', page=1, page_size=20):
    """
    List a user's past practice/exam sessions for the review page, with optional
    backend filters (hsk_level, category, date) and ordering. One row per session_id,
    with score and the level(s)/lesson(s) it covered.

    Returns (sessions, has_more). has_more lets the caller do prev/next paging without a
    separate COUNT query (we fetch one extra row and trim it). Scoped to user_id.
    """
    page = max(1, int(page or 1))
    page_size = min(50, max(1, int(page_size or 20)))

    session = SessionLocal()
    try:
        rows = LearningRepository(session).list_practice_sessions(
            user_id, hsk_level, category, date, sort, page, page_size
        )
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        sessions = []
        for row in rows:
            session_id, ended, total, correct, levels, lessons, categories = row
            total = total or 0
            correct = correct or 0
            sessions.append({
                'session_id':   session_id,
                'ended_at':     ended.isoformat() if ended else None,
                'total':        total,
                'correct':      correct,
                'score_pct':    round(correct / total * 100, 1) if total else 0.0,
                'levels':       sorted([l for l in (levels or []) if l is not None]),
                'lessons':      sorted([str(l) for l in (lessons or []) if l is not None]),
                'categories':   [c for c in (categories or []) if c],
            })
        return sessions, has_more
    except Exception as e:
        print(f"[WARN] get_practice_history_sessions failed: {e}")
        return [], False
    finally:
        SessionLocal.remove()


def get_practice_session_detail(user_id, session_id):
    """
    Full detail for one of the user's sessions: every answered question joined back
    to question_bank so the review page can show the prompt, options, correct answer
    and the user's own answer. Scoped to user_id so users only see their own records.
    """
    session = SessionLocal()
    try:
        rows = LearningRepository(session).get_practice_session_rows(user_id, session_id)
        cols = ['level', 'lesson', 'no', 'skill', 'type', 'user_answer',
                'is_correct', 'answered_at', 'category', 'content', 'question',
                'answer', 'audio_key', 'image', 'options', 'progress']
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        print(f"[WARN] get_practice_session_detail failed: {e}")
        return None
    finally:
        SessionLocal.remove()


def get_unlearned_words_from_db(user_id):
    """
    Returns a list of words from the user's history that have NOT been fully learned
    (less than 3 distinct correct modes in round 1).
    """
    session = SessionLocal()
    try:
        return LearningRepository(session).get_unlearned_words(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_unlearned_words_from_db): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_unsure_words_from_db(user_id):
    """
    Returns learned words the user answers slowly. For each mastered word, response times are
    z-scored per mode against the baseline of all the user's mastered words on their latest
    mastery day; words whose average z-score >= 1.0 are "unsure". Only meaningful once the user
    has mastered >= 50 words — returns [] below that, to keep the baseline stable.
    """
    session = SessionLocal()
    try:
        return LearningRepository(session).get_unsure_words(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_unsure_words_from_db): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_review_words(user_id):
    """
    Combines unsure + unlearned words into one prioritized review list.

    Tiers:
      - 'critical'   : word is in BOTH lists (slow AND not fully mastered)
      - 'unsure'     : mastered but slow to answer
      - 'incomplete' : not yet mastered across all 3 modes

    Returns a list of {"word": str, "reason": str}, critical first; within each tier the
    original ordering from the source functions is preserved.
    """
    unsure_list = get_unsure_words_from_db(user_id)
    unlearned_list = get_unlearned_words_from_db(user_id)

    unsure_set = set(unsure_list)
    unlearned_set = set(unlearned_list)

    seen = set()
    result = []

    # Pass 1: 'critical' — in both lists (unsure order primary, then any unlearned-first ones)
    for word in unsure_list:
        if word in unlearned_set and word not in seen:
            result.append({"word": word, "reason": "critical"})
            seen.add(word)
    for word in unlearned_list:
        if word in unsure_set and word not in seen:
            result.append({"word": word, "reason": "critical"})
            seen.add(word)

    # Pass 2: 'unsure' — slow but fully mastered
    for word in unsure_list:
        if word not in seen:
            result.append({"word": word, "reason": "unsure"})
            seen.add(word)

    # Pass 3: 'incomplete' — not yet mastered all 3 modes
    for word in unlearned_list:
        if word not in seen:
            result.append({"word": word, "reason": "incomplete"})
            seen.add(word)

    return result


def get_review_words_flat(user_id):
    """
    Same as get_review_words() but returns a plain prioritized list of word strings
    (critical > unsure > incomplete).
    """
    return [entry["word"] for entry in get_review_words(user_id)]


def get_hard_semantic_learned_words(user_id):
    """
    Returns a list of learned words (by the given user) but difficult in semantic.
    """
    session = SessionLocal()
    try:
        words = LearningRepository(session).get_hard_semantic_words_ordered(user_id)
        # sematic_diffculty has duplicate word_id rows, so dedup while keeping order.
        seen = set()
        result = []
        for word in words:
            if word not in seen:
                seen.add(word)
                result.append(word)
        return result
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_semantic_learned_words): {e}")
        return []
    finally:
        SessionLocal.remove()


def get_hard_stroke_learned_words(user_id):
    """
    Returns a list of learned words (by the given user) but difficult in strokes.
    """
    session = SessionLocal()
    try:
        return LearningRepository(session).get_hard_stroke_words_ordered(user_id)
    except Exception as e:
        print(f"⚠️ Database query failed (get_hard_stroke_learned_words): {e}")
        return []
    finally:
        SessionLocal.remove()
