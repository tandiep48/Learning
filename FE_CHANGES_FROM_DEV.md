# Frontend changes merged from `dev` into `dev_version_2.0`

Port list for the separate Next.js frontend project.

Range: `766b4b5` (last common commit) → `134907f` (`dev` HEAD), merged into
`dev_version_2.0`. Every item below is a Jinja/vanilla-JS change that was applied to
`web_app/templates` + `web_app/static` so the monolith keeps working — reimplement each
one in Next.js, then the corresponding Jinja/JS file can be deleted.

Backend API contracts are noted per feature, because several of these are breaking
changes to the request/response shape.

---

## 1. Learn Together — new "Book" competition mode

Source commit: `3ce1a8b`
Files: `templates/competition/learn_together.html`, `static/competition/competition.js`

A room can now be `category: "book"` in addition to `vocab` and `lesson`. A book room's
word pool is the **deduped union of every participant's saved vocabulary** inside the
selected book parts, instead of a public passage word list.

### UI

- Mode `<select>` gains a `book` option.
- New **Book** multi-select (`#create-book-field` / `#create-book-ms`), shown only in
  book mode; the **HSK** multi-select (`#create-level-field`) is hidden in that mode.
  The two are mutually exclusive sources feeding the same Lesson → Part cascade.
- Book mode reuses the **vocab** type set (`typing`, `listening`, `reading`), not the
  lesson set. `TYPE_OPTIONS.book === TYPE_OPTIONS.vocab`.
- Room summary shows the book code(s) instead of an HSK label, and renders the
  `competition.book_pool_note` string instead of a word count (a book room's count is
  not known until the session starts).
- Switching mode clears the lesson/part cascade and the cached passage groups.

### Passage id shape

A book `passage_id` is `{BOOK_CODE}_{lesson}_{part}` (e.g. `GCS_1_2`) rather than
`H{level}_{lesson}_{part}`. The existing `parsePassageId` puts the book code in `hsk`
and leaves `level === 0`. New helper `sourceGroupLabel(info)` returns `HSK {level}` when
`level` is truthy, otherwise `info.hsk` (the book code). Group headers in the
lesson/part pickers use it.

### APIs

| Endpoint | Purpose |
| --- | --- |
| `GET /api/vocab/saved-books` | Already existed. Populates the Book picker: books the user has saved words in. |
| `GET /api/competition/book-passages?book_code=XXX` | **New.** `{ "passages": [{ "passage_id": "GCS_1_1" }, ...] }` — the parts of that book the current user has saved words in. |
| `GET /api/competition/sessions/<session_id>/book-words` | **New.** `{ "words": [...] }` — the shared, deterministic pool for a running book session. |

Word shape returned by `book-words`:
`{ word, cn, pinyin, meaning_vn, meaning_en, audio_key, level }`
(note: `level`, *not* `hsk_level`, and `word` is duplicated from `cn` — the vocab
trainer expects both).

### Client flow

- At trainer start: book rooms call `resolveBookWords()` (server-resolved) instead of
  `resolveRoomWords()` (client-resolved from public passage vocab). Every participant
  must call the endpoint, not compute locally — the pool is frozen server-side at
  session start from the scored-participant set so all players get an identical list.
- Host "edit room settings" reconstructs the Book picker from the room's
  `passage_ids` (first segment = book code) instead of HSK levels.

### i18n keys added (`en.json` / `vi.json`, `competition.*`)

`mode_book`, `book`, `select_book`, `no_saved_books`, `book_pool_note`

---

## 2. Profile page redesign

Source commits: `448d2a0`, `03a0b8b`
Files: `templates/profile/profile.html`, `static/profile/profile.js`,
`static/profile/profile.css`, `templates/shared/site_nav.html`

### Layout changes

- Header split into `profile-header-main` (avatar + username/email) and a new
  `profile-badge-col` showing an **HSK badge image**.
- Avatar upload moved out of the header into a **modal** (`#avatar-modal`), opened by
  clicking the avatar (`#avatar-trigger`, with a camera-icon overlay). Closes on
  backdrop click, the X button, `Escape`, and automatically ~800ms after a successful
  upload.
- **Removed from the profile page:** the stats grid (HSK level / vocab / lesson /
  practice / exam time), the time-breakdown section, the learned-vocabulary list with
  its pagination, and the "Practice Review" CTA card. The corresponding JS
  (`renderProfile`, `renderBreakdown`, `renderLearnedWords`, `loadLearnedWords`,
  `formatDuration`, `formatDate`) was deleted.
  `loadProfileSummary()` now only reads `data.user.avatar_url`.
  > The backend endpoints `/api/user/profile-summary` (time totals/breakdowns) and
  > `/api/user/learned-vocab` still exist and are now unused by this page. Decide in the
  > Next.js project whether to keep them.
- The **practice review panel is now embedded in the profile page** — see §3.
- The `/learning` link was removed from the profile topbar.

### Badge image

New Jinja helper `badge_url(level)` → `{GCS_BUCKET_URL}/badge/HSK{n}.png`, `''` for a
level outside 1–6 or when GCS is unconfigured. On `dev_version_2.0` this lives in
`web_app/service/gcs_service.py::badge_url` and is exposed to templates through
`inject_avatar_helpers`. **Next.js needs an equivalent URL builder** (or a small API
field on the user payload).

### Change-password form — BREAKING API CHANGE

`POST /api/user/change-password`

- Old body: `{ username, new_password }` — the server verified `username` matched the
  session user and returned 403 on mismatch.
- New body: `{ new_password, confirm_password }` — the username field is gone from the
  form entirely; the server returns 400 `"New password is required."` when empty and
  400 `"Passwords do not match."` when the two differ.
- The client also validates the match before sending.

i18n: `profile.confirm_password_label`, `profile.passwords_do_not_match`,
`profile.new_password_required` added; `profile.username_new_password_required`
**removed**. `profile.badge` added.

### Nav avatar live refresh

`templates/shared/site_nav.html` now carries ids: `#site-user-link`, `#site-avatar`
(the `<img>`) and `#site-avatar-fallback` (the letter `<span>`). After an avatar upload,
`updateNavAvatar(url)` swaps the nav `<img>`'s `src` in place — or replaces the letter
fallback with a new `<img>` — so the nav updates without a page reload.

In Next.js this is just shared user state; no DOM surgery needed, but the behaviour
("nav avatar reflects a new upload immediately") must be preserved.

### Server-side avatar cleanup (no FE work, noted for completeness)

`POST /api/user/avatar` now deletes the user's previous avatar object from GCS after a
successful upload — one avatar per user.

---

## 3. Practice review — extracted panel, new filters, dropped date filter

Source commits: `448d2a0`, `556564b`
Files: `templates/review/_review_panel.html` (new), `templates/review/review.html`,
`static/review/review.js`, `static/review/review.css`

### Reusable panel

The whole review UI (filters + session list + pagination + detail view) was extracted
into `templates/review/_review_panel.html` and is now included by **both**
`review.html` and `profile.html`. In Next.js this should be one shared
`<PracticeReviewPanel />` component.

`profile.html` therefore also loads `review.css` and `review.js`.
Note: `profile.js` no longer defines `escapeHtml` — it relies on the copy in
`review.js`. Watch for this if the two are ported separately.

### Date filter removed — BREAKING API CHANGE

`GET /api/practice/history`

- The `date` query parameter (`YYYY-MM-DD`) is **gone**. The server no longer accepts
  or validates it; the review page used to default it to *today*, which hid older
  sessions.
- Remaining params: `level` (1–6 or `all`), `category` (`practice` | `exam` | `all`),
  `sort` (`recent` | `oldest`), `page`.
- The date `<input>` and its "All dates" clear button were removed from the filter row,
  along with `todayStr()` and `clearDateFilter()`.

`review.date` / `review.all_dates` i18n keys are now unused by this page (still present
in the JSON files).

### Session card simplified

The card no longer shows the category label or the score badge (`score_pct`,
`session_summary`, and the good/mid/low colour classes). It now shows only:
level(s) · lesson(s), the end date, and the question count. The corresponding CSS
(`.session-cat`, `.session-score*`) was deleted.

> The API still returns `score_pct`, `correct`, `total` and `categories` — the FE just
> stopped rendering some of them.

### Session detail gains its own filters

`renderDetail()` now stores the question list in memory and renders a filter row above
it, re-filtering client-side (no refetch):

- **Result**: all / correct / incorrect (on `q.is_correct`)
- **Skill**: all / reading / listening (on `q.skill`)

The old detail header (`%` score + correct/total summary) was removed.

i18n keys added: `review.filter_result`, `review.result_all`, `review.skill_all`.

---

## 4. Translation page → flashcard drill

Source commit: `9392f33`
Files: `templates/translation/translation.html`,
`static/translation/translation.js`, `static/translation/translation.css`

Replaced the scrolling list of sentence rows (`#translation-list`, one input per
sentence) with a **single-card drill** (`#translation-card-view`), matching the
"Learn these words" flow.

Per card:
- counter `n / total` + a progress bar fill
- the sentence meaning in the UI language
- a Chinese text input that gets a `success-highlight` class the moment the typed value
  trims-equal to the answer
- a reveal/hide answer toggle
- Prev / Shuffle / Next buttons (`prevCard()`, `shuffleCards()`, `nextCard()`),
  with Prev/Next disabled at the ends

Extras:
- `ArrowLeft` / `ArrowRight` move between cards, **suppressed while the input is
  focused**.
- `shuffleCards()` is an in-place Fisher–Yates over the loaded rows, then resets to
  card 1.
- The input is auto-focused on each card change.
- `escapeHtml()` was dropped from `translation.js` (the card path uses `textContent`).
- Empty state now sets the message text on `#translation-empty` and keeps the card view
  hidden.

No API change — still `GET /api/translation/lesson?hsk_level=&lesson=`.

i18n reused: `translation.reveal`, `translation.hide`, `translation.input_placeholder`,
`reading.prev`, `reading.next`, `vocab_learning.shuffle`.

---

## 5. Dashboard — translate "Lesson" in the current-lesson title

Source commit: `a7ca05e`
Files: `static/dashboard/dashboard.js`, `templates/index.html`

`#home-lesson-title` was hardcoded to `` `${hsk} - Lesson ${n}` ``. It now uses the
i18n string: `` `${hsk} - ${t('picker.lesson_prefix')} ${n}` ``.

---

## 6. i18n additions (full list)

Added to **both** `web_app/i18n/en.json` and `web_app/i18n/vi.json`:

```
review.filter_result        review.result_all          review.skill_all
profile.badge               profile.confirm_password_label
profile.passwords_do_not_match
competition.mode_book       competition.book           competition.select_book
competition.no_saved_books  competition.book_pool_note
```

Renamed:

```
profile.username_new_password_required  ->  profile.new_password_required
```

Now unused by the FE (still defined): `review.date`, `review.all_dates`.

The Next.js project should take these two JSON files as the translation source — they
are served by `GET /api/i18n/translations` on the backend.

---

## 7. Asset cache-busting bumps (Jinja only — ignore in Next.js)

| File | `?v=` |
| --- | --- |
| `competition/competition.js` | 8 → 9 |
| `dashboard/dashboard.js` | 7 → 8 |
| `review/review.js`, `review/review.css` | 3 → 5 |
| `translation/translation.js` | 3 → 4 |
| `translation/translation.css` | 5 → 6 |
| `profile/profile.js` | (none) → 5 |
| `profile/profile.css` | (none) → 8 |

`profile.html` and `review/_review_panel.html` also pull in Font Awesome 6.5.2 from
cdnjs for the camera / chevron / shuffle / close icons.

---

## Backend contract summary (what the Next.js client must target)

| Endpoint | Change |
| --- | --- |
| `POST /api/user/change-password` | Body is now `{ new_password, confirm_password }`; `username` removed. |
| `POST /api/user/avatar` | Unchanged shape; now deletes the old avatar object server-side. |
| `GET /api/practice/history` | `date` param removed. |
| `GET /api/competition/book-passages` | New. |
| `GET /api/competition/sessions/<id>/book-words` | New. |
| `POST /api/competition/rooms` (+ host edit) | `category` accepts `"book"`. A book room reports `source_count: 0` — do not render it as a word count. |

Not yet ported to Next.js and still unused by the redesigned profile page:
`GET /api/user/profile-summary` (time totals + per-mode breakdowns) and
`GET /api/user/learned-vocab`.
