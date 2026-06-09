# 🏋️ AI Gym Assistant — Milo

A production-grade multi-agent AI fitness assistant built on real gym data from **398 members**. Members chat with Milo, an AI coach that knows their attendance history, membership status, and fitness goals — and routes each query through a LangGraph agent pipeline to answer intelligently.

> Built for a real gym. Not a toy project.

---

## Architecture

```
Member Chat (React 19 + Vite)
        │
        ▼
POST /chat  ←─── FastAPI Backend
        │
        ▼
┌─────────────────────────────────────────────────┐
│                   8-Step Pipeline                │
│                                                  │
│  1. Init working memory                          │
│  2. Reflection  ← classifies last turn outcome  │
│  3. Semantic fetch  ← member profile + goals    │
│  4. Episodic retrieve  ← top-5 similar chats    │
│  5. Perception  ← intent / mood / urgency       │
│  6. LangGraph plan  ← parallel agent fan-out    │
│  7. Personality + Groq call                     │
│  8. Save to chat_messages + episodic_memory     │
└─────────────────────────────────────────────────┘
        │
        ▼
    Supabase (PostgreSQL + pgvector)
```

---

## LangGraph Agent Graph

```
START → router_node
            │ conditional fan-out (parallel)
    ┌───────┬────────────┬──────┬───────────┬───────────┐
attendance membership  diet  analytics  occupancy
    └───────┴────────────┴──────┴───────────┴───────────┘
                           │
                      collect_node → END
```

**Routing by intent:**

| Category | Agents Run |
|---|---|
| `ATTENDANCE` | attendance + membership |
| `DIET / FITNESS` | diet + attendance |
| `OCCUPANCY` | occupancy only |
| `ANALYTICS` | analytics only (staff/owner token) |
| `GENERAL` | attendance + membership |

> Extra rule: if `days_to_expiry ≤ 7`, membership agent is always appended regardless of category.

---

## Memory Architecture — 3 Layers

| Layer | Storage | What it holds |
|---|---|---|
| **Working** | In-process Python dict | Current turn state — cleared after each request |
| **Episodic** | `episodic_memory` table + pgvector | One row per turn, 384-dim embedding, cosine similarity retrieval (top-5) |
| **Semantic** | `members` table columns | `fitness_goal`, `diet_preference`, `preferred_workout_time`, `response_style`, `last_mood` |

Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs locally, no API key).

Vector query syntax: `embedding <=> CAST(:vec AS vector)` — uses `CAST()` not `::vector` (asyncpg rejects parameterized `::` casts).

---

## Agents

| Agent | What it does |
|---|---|
| `perception.py` | Single Groq call at `temp=0` — classifies `{category, mood, urgency, is_question, key_topic}`. Shortcut for greetings (no LLM call). |
| `attendance.py` | Pulls last 30 days from DB. Computes visits, missed days, current streak, longest streak. Renders ASCII 30-day chart. |
| `membership.py` | Pulls member + last 5 billing records. Classifies urgency: `expired / critical / warning / ok`. |
| `diet.py` | LLM-only. Loads owner-editable `diet_guidelines.txt` if present. Injects member goal, plan, diet preference, workout time. |
| `analytics.py` | 8 DB queries — active/inactive counts, expiry alerts, revenue MoM, top payment mode, top-10 at-risk members by dropout score. Staff/owner only. |
| `occupancy.py` | Live scrape of Yoactiv `clientcheckins.aspx` on every call. Counts members currently checked in (no clock-out). Classifies: quiet / moderate / busy / packed. |
| `reflection.py` | Signal-based (no LLM). Runs at start of next turn — classifies how the previous reply landed (`positive_response / follow_up_asked / ignored / negative_response`). Updates semantic memory. |
| `personality.py` | Pure function, no LLM. Assembles final system prompt from identity + tone + member profile + episodic excerpts + agent outputs + proactive signals. |

---

## Tech Stack

| Layer | Stack |
|---|---|
| **Backend** | FastAPI · SQLAlchemy (async) · asyncpg · Pydantic-settings |
| **AI / Agents** | LangGraph · LangChain-Groq · LLaMA 3.3 70B · sentence-transformers |
| **Database** | Supabase (PostgreSQL) · pgvector · 10 tables · 398 member rows |
| **Auth** | JWT (python-jose) · bcrypt==4.0.1 (version-locked, passlib incompatible with 4.x+) |
| **Scheduler** | APScheduler — 6 IST-timezone jobs (keepalive, member discovery, daily sync, billing, irregular, monthly) |
| **Scraper** | httpx · BeautifulSoup4 · lxml — 6 Yoactiv endpoints |
| **Frontend** | React 19 · Vite · Tailwind v4 · react-query · Framer Motion |

---

## Data Layer

**10 Supabase tables:** `members`, `attendance_logs`, `monthly_attendance`, `billing_records`, `staff_users`, `alerts_log`, `chat_messages`, `sync_log`, `dropout_score_history`, `yoactiv_session`

**Yoactiv scraper** pulls from 6 endpoints — member discovery (a-z + 0-9 prefix search), member details, attendance history, monthly bulk register, billing records, irregular member flags.

**Cookie architecture:** Chrome extension pushes `ASP.NET_SessionId` + AWS cookies to Supabase every 14 min. Backend has 3-layer fallback: `cookies.json → Supabase → RuntimeError`. Playwright was permanently abandoned (Cloudflare Turnstile).

---

## API Endpoints

```
POST  /auth/member/login       → {access_token, member_name, member_id}
POST  /auth/staff/login        → {access_token, role, full_name}

GET   /member/me               ← member JWT required
GET   /member/attendance       ← member JWT, ?limit=30 (capped at 100)

POST  /chat                    ← member JWT, {message} → {reply, agent, category, mood}

GET   /health
GET   /health/cookies          ← checks Yoactiv cookie validity

POST  /admin/sync/members
POST  /admin/sync/status
POST  /admin/sync/billing
POST  /admin/sync/all
GET   /admin/sync/logs
```

---

## Setup

### Prerequisites
- Python 3.11 (not 3.12+ — `bcrypt==4.0.1` constraint)
- Supabase project with pgvector enabled
- Groq API key

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**`backend/.env`:**
```env
DATABASE_URL=postgresql+asyncpg://...
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
JWT_SECRET_KEY=<32+ char hex>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
COOKIE_PUSH_SECRET=<hex>
YOACTIV_BASE_URL=https://backstage.yoactiv.com
APP_ENV=development
CORS_ORIGINS=http://localhost:5173
```

**One-time migration** (run in Supabase SQL Editor):
```sql
-- backend/migrations/001_cognitive_layer.sql
-- Enables pgvector, creates episodic_memory table, adds user model columns
```

**Generate member accounts** (required before any member can log in):
```bash
python scripts/generate_member_accounts.py
```

### Frontend

```bash
cd member-chat
npm install
npm run dev     # http://localhost:5173
```

---

## Known Gaps

| Gap | Status |
|---|---|
| Member accounts | `generate_member_accounts.py` exists but never run — no member can log in yet |
| `dropout_score` | Column exists, always `0.0` — scoring algorithm not implemented |
| Admin routes | All `/admin/sync/*` endpoints are unprotected (no JWT guard) |
| Owner dashboard | Folder exists, content is a stub |
| WhatsApp alerts | `alerts_log` table exists, Meta Cloud API not integrated |
| Docker / CI | Not started |
| `diet_guidelines.txt` | Diet agent loads it if present — file doesn't exist yet |
| IVFFlat index | Commented out in migration — uncomment after 100+ episodic rows |

---

## Folder Structure

```
gym-ai/
├── backend/
│   ├── app/
│   │   ├── agents/         ← planner, perception, attendance, membership,
│   │   │                      diet, analytics, occupancy, memory,
│   │   │                      personality, reflection
│   │   ├── auth/           ← JWT handler + role dependencies
│   │   ├── routes/         ← auth, member, chat
│   │   ├── yoactiv/        ← scraper, session manager, cookie store
│   │   ├── config.py
│   │   ├── database.py     ← 10 SQLAlchemy models
│   │   ├── main.py
│   │   └── scheduler.py    ← APScheduler 6 jobs
│   ├── migrations/
│   └── requirements.txt
├── member-chat/            ← React 19 + Vite + Tailwind v4
└── owner-dashboard/        ← stub
```
