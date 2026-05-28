# QuizHub

> A Django quiz platform with role-based creators, weighted scoring, shuffled questions, and live leaderboards.

<!-- BADGES — feel free to add coverage, CI, etc. later -->
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Django](https://img.shields.io/badge/Django-5.x-092E20)
![Tailwind](https://img.shields.io/badge/Tailwind-4.x-38B2AC)
![daisyUI](https://img.shields.io/badge/daisyUI-5.x-5A0EF8)
![License](https://img.shields.io/badge/license-MIT-green)

---

**QuizHub** is a full-featured quiz platform built with Django, HTMX, and Tailwind/daisyUI. Users can request creator privileges, build quizzes with single- or multiple-choice questions, share them publicly or via invitation, and watch live leaderboards.

The frontend is server-rendered with HTMX for interactivity — no SPA, no JSON API, no client-side framework. Everything you'd expect from a "modern" feeling app, delivered with significantly less code than a React + DRF equivalent.

## 🔗 Live demo

🌐 **[Try it live](https://YOUR-DEPLOY-URL.example.com)** *(coming soon)*

> Note: social login (Google, Facebook) is enabled but in development mode — please use email signup to try the app end-to-end.

---

## 📸 Screenshots

<!-- TODO: replace placeholders with real screenshots -->

| Landing page | Creator dashboard |
|---|---|
| ![landing](docs/screenshots/landing.png) | ![dashboard](docs/screenshots/dashboard.png) |

| Taking a quiz | Leaderboard |
|---|---|
| ![quiz](docs/screenshots/quiz-taking.png) | ![leaderboard](docs/screenshots/leaderboard.png) |

| Question editor (HTMX) | Theme switcher (30+ themes) |
|---|---|
| ![editor](docs/screenshots/question-editor.png) | ![themes](docs/screenshots/themes.png) |

---

## ✨ Highlights

### For everyone
- 🎯 Take quizzes with weighted scoring (points per question, strict all-or-nothing for multi-choice)
- 🔀 Questions shuffle per attempt — no two users see the same order
- ⏱️ Optional timer per quiz with server-enforced expiry
- 🏆 Per-quiz leaderboards with personal rank highlighted
- 📊 Personal history of every attempt with stats
- 🎨 30+ themes via daisyUI — saved to your profile when logged in

### For creators
- Request creator access via admin approval
- Build quizzes with single- or multiple-choice questions
- Weighted points per question
- Public or private quizzes (with invitations & access requests)
- Categories and free-form tags for discoverability
- Manual or auto-close (datetime) quiz availability
- Per-quiz analytics: attempts, average score, top scorer, recent activity
- Choose to show results immediately or release manually

### Tech polish
- HTMX-driven question editor with inline editing & autosave
- SweetAlert2 toasts & confirmation modals (theme-aware)
- Email notifications for invitations, approvals, access requests
- Email + Google + Facebook social login (via django-allauth)
- Server-rendered, accessible, works without JavaScript for core flows

---

## 🛠️ Tech stack

| Layer | Tool | Why |
|---|---|---|
| **Language** | Python 3.11+ | Modern Django requires 3.10+; we target 3.11+ for performance |
| **Framework** | Django 5 | Mature, batteries-included, ORM is hard to beat for this domain |
| **Database** | PostgreSQL | Conditional unique constraints, JSON fields, real concurrency |
| **Frontend** | HTMX + Alpine.js | SPA feel without the SPA complexity |
| **Styling** | Tailwind CSS v4 + daisyUI v5 | Utility-first, component-rich, theming for free |
| **Auth** | django-allauth | Email + social (Google, Facebook) without rolling our own |
| **Testing** | pytest + factory-boy | Cleaner than Django's `TestCase`, factories scale better than fixtures |
| **Deps** | uv | Faster than pip, deterministic via uv.lock |
| **Notifications** | SweetAlert2 | Themed toasts & modals, replaces browser-native dialogs |

---

## 🏗️ Architecture notes

Decisions I made that I think are worth understanding.

### Server is the source of truth, always

The timer is a clean example: a JavaScript countdown ticks down for the user, but the server holds the canonical `time_limit_expires_at`. Every entry point (page load, answer save, heartbeat, submit) checks for expiry independently. If the user disables JS, edits the DOM, or tampers with the clock, the server still finalizes the attempt correctly.

Same principle applies to scoring (computed at submit time, never re-derived from possibly-changed quiz data), access control (every view validates ownership, never trusts client claims), and visibility (filters happen at query level, not after rendering).

### Wrap the framework, don't replace it

When I replaced Django's messages framework UI with SweetAlert2 toasts, I kept `messages.success(request, "...")` as the API. View code didn't change at all. The change happened in the middleware layer (converting messages to `HX-Trigger` headers for HTMX requests) and the template layer (rendering session messages as toasts on page load).

This means allauth, the admin, and any future third-party Django apps that use `messages.*` also benefit. If I had built a custom `toast()` helper instead, I'd own that integration forever.

### HTMX for the question editor

The question/choice editor needed real-time feel: add a choice, see it appear; toggle "correct", see the badge flip; reorder questions, no flicker. Every option I considered (vanilla JS, Alpine alone, a small SPA) traded off against complexity.

HTMX wins because the same view functions that render the full page also render the fragments. No JSON API, no client-side state, no duplicate validation. The total JS in the editor is roughly 0 lines — every interaction is a server round-trip rendered as HTML.

The performance cost (one HTTP request per interaction) is negligible at this scale, and the code-readability win is enormous.

### Visibility rules in one place

The query "what quizzes can this viewer see?" lives in a single function, `visible_quizzes(viewer)` in `quizzes/queries.py`. It encodes the rules: published + (public OR invited-to-private). Every list view, every detail view, every creator profile uses this same function.

The benefit: when the rules change (and they will), I edit one place. The test suite for visibility (`tests/test_access.py`) targets this function specifically.

### Tag normalization on the model

`Tag.from_string("DJANGO  ")` and `Tag.from_string("django")` produce the same row. The normalization is a `@classmethod` on the model, not buried in a form. Any code path that creates tags — forms, admin actions, future API, data migrations — gets the same canonicalization. Single source of truth at the data layer.

### Strict scoring (no partial credit)

A multi-choice question is scored full points only if the user selects exactly the correct set. No partial credit. This is a deliberate UX choice — the rule is easy to explain ("got it right or you didn't") and easy to defend against disputes.

The architecture supports adding partial credit later as an opt-in per-quiz setting; the data model already stores selected choices per attempt, so re-scoring with a different rule is straightforward.

### Tests focus on business logic, not glue

The test suite covers scoring, access control, the creator request workflow, the quiz state machine, and the attempt lifecycle. View-rendering tests are deliberately skipped — they'd test that Django's `render` works, which Django already tests.

The investment is in the parts where bugs would be embarrassing: a quiz scored wrong, a private quiz visible to the wrong user, a creator request that doesn't grant creator status. Tests for those are tight and fast (~60 tests in <10 seconds).

---

## 🚀 Getting started

### Prerequisites
- Python 3.11+
- Node.js 18+ (for the Tailwind build pipeline)
- PostgreSQL (running locally or via Docker)
- [uv](https://docs.astral.sh/uv/) for Python dependency management

### Setup

```bash
# 1. Clone
git clone https://github.com/MahdiKheireddine/quizhub.git
cd quizhub

# 2. Python environment
uv sync

# 3. Environment variables
cp .env.example .env
# Edit .env with your secret key, database credentials, etc.
# Generate a Django secret key:
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Database
createdb quizhub
uv run python manage.py migrate

# 5. Tailwind/daisyUI build
uv run python manage.py tailwind install

# 6. Superuser
uv run python manage.py createsuperuser
```

### Run

In two terminals:

```bash
# Terminal 1 — Tailwind watcher
uv run python manage.py tailwind start

# Terminal 2 — Django dev server
uv run python manage.py runserver
```

Or, using the included Procfile:

```bash
uv run honcho -f Procfile.tailwind start
```

Visit http://127.0.0.1:8000

### Optional: seed test data

A management command exists to create dummy quizzes:

```bash
uv run python manage.py seed_dummy_quizzes --username YOUR_USERNAME --count 30
```

### Social login (optional)

To enable Google and Facebook login locally, register OAuth apps on each console (instructions in [`docs/social-login.md`](docs/social-login.md) — coming soon), then add the credentials via Django admin under "Social applications".

The buttons only render when credentials are configured, so the app works fine without them.

---

## 📁 Project structure

```
quizhub/
├── config/                      # Django project settings (split layout)
│   ├── django/
│   │   ├── base.py              # shared settings
│   │   ├── local.py             # development overrides
│   │   ├── production.py        # production overrides
│   │   └── tests.py             # pytest settings
│   ├── env.py                   # env loading via django-environ
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── accounts/                    # Custom User, creator requests, profile, preferences
│   ├── models.py                # User (role + is_creator_approved), CreatorRequest, UserPreferences
│   ├── views.py
│   ├── forms.py
│   ├── signals.py               # auto-create UserPreferences on signup
│   └── social.py                # detect configured social providers
├── quizzes/                     # Core quiz domain
│   ├── models.py                # Quiz, Question, Choice, Category, Tag, Invitation, JoinRequest
│   ├── queries.py               # visibility helpers
│   ├── stats.py                 # creator dashboard analytics
│   ├── forms.py
│   ├── views.py
│   └── migrations/              # includes data migration for categories
├── attempts/                    # Quiz-taking state
│   ├── models.py                # Attempt, Answer
│   ├── services.py              # start_attempt, score_attempt, timer enforcement, stats
│   └── views.py
├── core/                        # Site-wide concerns
│   ├── context_processors.py
│   ├── middleware.py            # HTMX → toast bridge
│   ├── email.py                 # notification dispatch
│   └── pagination.py            # shared paginator helper
├── theme/                       # django-tailwind app (Tailwind + daisyUI build)
├── templates/                   # Server-rendered HTML
│   ├── base.html                # layout, theme, HTMX, Alpine, toasts, confirms
│   ├── components/              # navbar, footer, pagination
│   ├── account/                 # allauth overrides
│   ├── accounts/                # creator request, profile
│   ├── quizzes/                 # browse, detail, editor, dashboard
│   ├── attempts/                # quiz start, runner, result, leaderboard
│   └── emails/                  # text + HTML pairs for every notification
└── tests/                       # pytest suite
    ├── conftest.py
    ├── factories.py
    └── test_*.py
```

---

## 🧪 Testing

```bash
uv run pytest
```

Run specific files or tests:

```bash
uv run pytest tests/test_scoring.py        # one file
uv run pytest -k "scoring"                 # by keyword
uv run pytest -v                           # verbose
```

The suite covers ~60 tests across scoring, access control, the creator request workflow, the quiz state machine, attempt lifecycle, timer enforcement, and tag normalization. Runs in under 10 seconds.

---

## 🗺️ Roadmap

Features I'd build next. Each is an interesting design problem in its own right.

### Already considered, designed-but-not-built

- **Question revisit controls** — let creators choose whether takers can go back to previous questions or whether each answer is locked once submitted. Useful for exams vs casual quizzes.
- **Explanations for choices** — creators add an explanation per choice, shown on the result page so users learn from their mistakes.

### Quality-of-life

- **Question banks** — store questions independently of quizzes and reuse them across multiple quizzes. Cleanest implementation: an M2M with a through-table that captures per-quiz overrides (points, order).
- **Quiz duplication** — clone an existing quiz as a starting point. One-click "save as draft copy".
- **Soft delete** — recoverable deletion for quizzes. A creator's nightmare is accidentally deleting a quiz with 500 attempts on it.
- **Quiz versioning** — track edits to questions; when a quiz is materially changed, freeze the version for previous attempts so old scores remain meaningful.
- **CSV import** — bulk question entry from a spreadsheet. Useful for educators who already have question banks elsewhere.

### Media & UX

- **Image support** — upload images to questions and choices (think geography quizzes, art history, code screenshots).
- **Rich text** in question and explanation fields (markdown, syntax-highlighted code blocks for programming quizzes).
- **Multilingual support** — internationalization for at least Arabic, French, and English. Django i18n + locale-aware templates.

### Analytics

- **Score distribution graphs** on the creator dashboard. Histogram of scores per quiz.
- **Question difficulty analysis** — flag questions everyone gets right (too easy) or everyone gets wrong (broken or too hard).
- **Time-spent analytics** — average time per question, helps creators tune difficulty and timing.

### Engagement & community

- **Comments on quizzes** — threaded discussion per quiz.
- **Following creators** — get notified when a creator you follow publishes a new quiz.
- **Quiz collections / playlists** — group related quizzes into a learning path.

### Real-time & infrastructure

- **WebSocket leaderboards** — live position updates while a quiz is being taken across multiple users.
- **Public API** — token-authenticated read API for quizzes and stats. Would enable mobile apps, third-party integrations.
- **Background email queue** — currently emails send synchronously inline with the request. Moving to Celery or django-rq would unblock requests immediately and add retry on failure.

---

## 📜 License

MIT. See [LICENSE](LICENSE).

---

## 🙏 Built with

- [Django](https://www.djangoproject.com/) — the web framework
- [HTMX](https://htmx.org/) — interactivity without the SPA tax
- [Alpine.js](https://alpinejs.dev/) — sprinkles of reactivity
- [Tailwind CSS](https://tailwindcss.com/) + [daisyUI](https://daisyui.com/) — utility-first styling and theming
- [django-allauth](https://docs.allauth.org/) — authentication including social providers
- [SweetAlert2](https://sweetalert2.github.io/) — themed notifications

Cover art and screenshots: my own.

---

Built by **[Mahdi Kheireddine](https://github.com/MahdiKheireddine)** as a portfolio project. Reach out if you find this useful or have feedback.