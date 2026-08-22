"""
service/lesson_task_service.py
------------------------------
Builds a lesson-trainer round: a fixed number of tasks sampled from the selected
passages, split across the four task types (listening / meaning / typing / reorder).

Extracted from lesson_routes so it can be reused by the multiplayer "Learn Together"
lesson mode, which generates one shared task set per session for a fair ranking.
"""

import random

from db import get_passage_content


# ── Lesson-trainer question mix ──────────────────────────────────────────────
# A round samples a fixed number of tasks (so the learner no longer answers every
# possible question) split across the four task types. "part" = one part; "master"
# = the whole lesson (all parts).
LESSON_TASK_DISTRIBUTION = [
    ("listening", 0.30),
    ("meaning", 0.30),
    ("typing", 0.30),
    ("reorder", 0.10),
]

LESSON_PART_COUNTS = {
    "HSK1": 10, "HSK2": 12, "HSK3": 15,
    "HSK4": 18, "HSK5": 21, "HSK6": 24,
}

LESSON_MASTER_COUNTS = {
    "HSK1": 24, "HSK2": 36, "HSK3": 48,
    "HSK4": 54, "HSK5": 75, "HSK6": 90,
}

DEFAULT_LESSON_TASK_COUNT = 10


def normalize_hsk_level(raw):
    """Coerce values like 'HSK1', 'H1', '1' to the canonical 'HSK1' form."""
    s = str(raw or "").upper().strip()
    if s.startswith("HSK"):
        return s
    digits = "".join(ch for ch in s if ch.isdigit())
    return f"HSK{digits}" if digits else ""


def _allocate_task_counts(total, distribution):
    """Split `total` across the distribution, using largest-remainder rounding so
    the per-type counts always sum back to `total`."""
    raw = [(name, total * pct) for name, pct in distribution]
    counts = {name: int(value) for name, value in raw}
    remainder = total - sum(counts.values())
    # Hand the leftover slots to the types with the biggest fractional parts.
    by_frac = sorted(raw, key=lambda item: item[1] - int(item[1]), reverse=True)
    for name, _ in by_frac[:remainder]:
        counts[name] += 1
    return counts


def _sample_task_pool(pool, count):
    """Pick `count` tasks from `pool`. Prefers unique tasks; only repeats when the
    pool is smaller than the requested count."""
    if count <= 0 or not pool:
        return []
    if count <= len(pool):
        return random.sample(pool, count)
    return pool[:] + random.choices(pool, k=count - len(pool))


def _collect_line_items(passage_ids):
    """Load the selected passages and return (passages, quizable line items).

    Only lines that introduce a new word (flag == 1) are quizzed, falling back to
    every line when a part has none so a directly-selected part is never empty."""
    passages = []
    for pid in passage_ids or []:
        passage = get_passage_content(pid)
        if passage:
            passages.append((pid, passage))
    if not passages:
        return [], []

    line_items = []
    for pid, passage in passages:
        for line in passage.get("lines", []):
            line_items.append((pid, passage, line))

    flagged_items = [item for item in line_items if item[2].get("flag", 1) == 1]
    if flagged_items:
        line_items = flagged_items
    return passages, line_items


def count_lesson_lines(passage_ids):
    """Number of quizable lines across the passages — used to validate a room has
    material and to show a task-source count. 0 means nothing to quiz."""
    _, line_items = _collect_line_items(passage_ids)
    return len(line_items)


def build_lesson_tasks(passage_ids, mode="part", types=None):
    """Build a shuffled lesson-trainer round for the selected passages.

    mode: "part" (one part) or "master" (a whole lesson / multiple parts) — only the
    target task count differs. types: optional subset of the task types to include
    (listening / meaning / typing / reorder); None or empty means the full mix. Returns
    a list of task dicts (same shape the lesson trainer client expects). Empty list when
    the passages have no quizable lines."""
    passages, line_items = _collect_line_items(passage_ids)
    if not line_items:
        return []

    # Restrict the task mix to the requested types (re-normalizing their shares to 100%),
    # falling back to the full distribution when nothing valid is requested.
    distribution = LESSON_TASK_DISTRIBUTION
    if types:
        wanted = {str(x).strip().lower() for x in types}
        selected = [(name, pct) for name, pct in LESSON_TASK_DISTRIBUTION if name in wanted]
        total_pct = sum(pct for _, pct in selected)
        if selected and total_pct > 0:
            distribution = [(name, pct / total_pct) for name, pct in selected]

    # Build a pool of candidate tasks per type, one per line, then sample from each
    # pool to hit the target count and 30/30/30/10 mix.
    pools = {"listening": [], "meaning": [], "typing": [], "reorder": []}

    # Collect all Vietnamese meanings in this session for multiple-choice distractors.
    all_vn_meanings = [line["translations"]["vi"] for _, _, line in line_items]

    for line_passage_id, passage, line in line_items:
        line_id = line.get("line_id", 0)
        correct_meaning = line["translations"]["vi"]

        meaning_options = list(set([opt for opt in all_vn_meanings if opt != correct_meaning]))
        distractors = random.sample(meaning_options, min(3, len(meaning_options)))
        m_options = distractors + [correct_meaning]
        random.shuffle(m_options)

        pools["meaning"].append({
            "type": "meaning",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "content": line["content"],
            "options": m_options,
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "hsk_level": passage.get("hsk_level"),
            "book_code": passage.get("book_code"),
        })

        pools["listening"].append({
            "type": "listening",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "options": m_options,  # Same options logic as meaning
            "correct_answer": correct_meaning,
            "audio_key": line.get("audio_key"),
            "content": line["content"],  # provided for reveal
            "hsk_level": passage.get("hsk_level"),
            "book_code": passage.get("book_code"),
        })

        tokens = line.get("tokens", [])
        if len(tokens) > 1:  # Only reorder if there are multiple tokens
            shuffled_tokens = tokens[:]
            random.shuffle(shuffled_tokens)
            pools["reorder"].append({
                "type": "reorder",
                "passage_id": line_passage_id,
                "line_id": line_id,
                "content": line["content"],
                "tokens": tokens,
                "shuffled_tokens": shuffled_tokens,
                "correct_answer": "".join(tokens),
                "audio_key": line.get("audio_key"),
                "hsk_level": passage.get("hsk_level"),
                "book_code": passage.get("book_code"),
            })

        pools["typing"].append({
            "type": "typing",
            "passage_id": line_passage_id,
            "line_id": line_id,
            "content": line["content"],
            "correct_answer": line["content"],
            "audio_key": line.get("audio_key"),
            "pinyin": line.get("pinyin", ""),
            "hsk_level": passage.get("hsk_level"),
            "book_code": passage.get("book_code"),
        })

    # Target count depends on the mode (part vs master) and the lesson's HSK level.
    mode = "master" if mode == "master" else "part"
    hsk_level = normalize_hsk_level(passages[0][1].get("hsk_level"))
    count_table = LESSON_MASTER_COUNTS if mode == "master" else LESSON_PART_COUNTS
    target_total = count_table.get(hsk_level, DEFAULT_LESSON_TASK_COUNT)

    targets = _allocate_task_counts(target_total, distribution)

    # If a type has no candidates (e.g. no multi-token lines → no reorder), move its
    # share to another selected type that has material, falling back to any type so the
    # round is never empty.
    selected_names = [name for name, _ in distribution]
    for name in selected_names:
        if targets.get(name) and not pools[name]:
            moved = targets[name]
            targets[name] = 0
            fallbacks = [n for n in selected_names if n != name] + list(pools.keys())
            for fallback in fallbacks:
                if pools[fallback]:
                    targets[fallback] = targets.get(fallback, 0) + moved
                    break

    tasks = []
    for name in targets:
        tasks.extend(_sample_task_pool(pools[name], targets.get(name, 0)))
    random.shuffle(tasks)
    return tasks
