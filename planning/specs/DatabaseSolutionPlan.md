# Database Solution Plan

This document identifies all data generated and stored by LIA, evaluates database requirements, and presents solution options.

---

## 1. Data Inventory

### 1.1 Authentication and Identity

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| User accounts (email, password hash, verification status) | Registration, OAuth | Low | High (every request) |
| OAuth provider links (Google) | OAuth login | Low | Medium |
| Sessions (token hash, expiry, persistent flag) | Login/logout | Medium | High (every request) |
| Password reset tokens | Forgot password flow | Low | Low |
| Auth audit events (login success/fail, lockouts, resets) | All auth actions | Medium | Low (admin/debug) |

### 1.2 User Preferences and Settings

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| Display name | Settings page | Low | Medium |
| Appearance theme (light/dark) | Settings toggle | Low | High (page load) |
| Notification preferences (in-app, email) | Settings page | Low | Medium |
| Language settings (display, response, report) | Settings page | Low | High |

### 1.3 Portfolio

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| Tracked tickers (symbol, company name) | Portfolio page add/remove | Medium | High |
| Groups (name, order) | Portfolio page | Low | High |
| Ticker-to-group assignments | Portfolio page | Medium | High |
| View mode and sort preferences (per group) | Portfolio page toggles | Low | Medium |

### 1.4 Chat History (All Departments)

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| Conversations (department, title, timestamps) | Every new chat session | Medium | Medium |
| Messages (role, content, timestamps) | Every message sent/received | High | Medium |

### 1.5 Generated Reports

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| Report metadata (id, filename, department, generated_at) | Report generation | Medium | Medium |
| Report file content (PDF/document body) | Report generation | Medium | Low (on preview/download) |

### 1.6 Repository (Saved Reports)

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| Save records (report_id, saved_at, saved_by) | SaveToRepo button | Low-Medium | Medium |

### 1.7 Department-Specific Configuration

| Data | Source | Write Frequency | Read Frequency |
|---|---|---|---|
| SR report section preferences (selected/custom sections, length) | SR settings | Low | Medium |
| ER watchlist (tickers, next earnings dates) | ER page | Low-Medium | High (daily scan) |
| ER cabinet entries (generated report references) | Automated/on-demand generation | Medium | Medium |
| MB coverage list (sections, topics, keywords, notes) | MB settings | Low | Medium (daily generation) |
| MB report schedules (time, timezone, days) | MB settings | Low | High (scheduler) |
| RS monitor list (keywords, hashtags) | RS dashboard | Low | High (continuous monitoring) |

---

## 2. Storage Requirements Analysis

### 2.1 Structured Relational Data
- User accounts, auth, sessions, portfolio, groups, watchlists, schedules, settings, report metadata, save records
- Requires: referential integrity (FK constraints), transactional writes, indexed queries by user_id
- Volume: Low-medium rows per user, but high read frequency on hot paths (auth, portfolio, settings)

### 2.2 Conversational / Semi-Structured Data
- Chat messages across all departments
- Characteristics: append-heavy, variable-length text content, queried by conversation_id with time ordering
- Volume: Can grow large over time per user (hundreds to thousands of messages)

### 2.3 File/Blob Storage
- Generated report files (PDFs, documents)
- Characteristics: large binary objects (100KB-10MB per report), write-once, read on demand
- Volume: Grows steadily; needs cost-effective storage with CDN-friendly retrieval

### 2.4 Ephemeral / Cache Data
- Rate limiting counters, session validation cache, real-time price data cache
- Characteristics: short TTL, high read/write frequency, loss-tolerant

---

## 3. Database Requirements

| Requirement | Priority | Reason |
|---|---|---|
| Relational integrity (FKs, constraints) | Must-have | Auth, portfolio, and report metadata require strict consistency |
| Transactional writes | Must-have | Account creation, save/unsave operations, watchlist updates |
| Full-text search | Nice-to-have | Repository search by filename; can start with LIKE/ILIKE |
| Scalable blob storage | Must-have | Report files should not bloat the primary database |
| Low-latency key-value lookups | Must-have | Session validation, rate limiting |
| Time-series or append-optimized writes | Nice-to-have | Chat history is append-heavy but standard RDBMS handles this fine at expected scale |
| Scheduled job persistence | Must-have | MB schedules and ER earnings scan triggers |

---

## 4. Recommended Architecture

### Option A: PostgreSQL + Object Storage + Redis (Recommended)

```
                    +------------------+
                    |   Application    |
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
  +-------v-------+  +------v------+  +--------v--------+
  |  PostgreSQL   |  |    Redis    |  | Object Storage  |
  | (primary DB)  |  |  (cache +   |  | (report files)  |
  |               |  |  rate limit)|  |                 |
  +---------------+  +-------------+  +-----------------+
```

**PostgreSQL** -- single primary database for all structured data:
- Auth tables (users, auth_accounts, sessions, password_reset_tokens, auth_events)
- User preferences (settings, language, theme, notifications)
- Portfolio (tickers, groups, assignments, view preferences)
- Chat history (conversations, messages)
- Report metadata (id, filename, department, timestamps, file_url pointer)
- Repository save records
- Department configs (SR sections, ER watchlist, MB coverage + schedules, RS monitor list)

**Object Storage (S3 / R2 / Supabase Storage)** -- report file blobs:
- Store generated PDFs and documents as objects keyed by report_id
- PostgreSQL stores the object URL/key; retrieval goes direct to object storage
- Enables CDN caching for downloads and previews

**Redis (Upstash / ElastiCache)** -- ephemeral data:
- Rate limiting counters (login abuse protection)
- Session validation cache (optional, reduces DB reads on hot path)
- Real-time price data cache for portfolio page
- Job queue for scheduled report generation (MB schedules, ER scans)

#### Why this option

- PostgreSQL is already recommended in the AccountManagementSpec; one database simplifies operations
- At the expected scale (individual retail users, not enterprise multi-tenant), PostgreSQL handles chat history and all structured data without issue
- Object storage is the standard for files; keeps PostgreSQL lean
- Redis is needed anyway for rate limiting (per AccountManagementSpec); reuse it for caching and job queues

### Option B: PostgreSQL + Object Storage (No Redis)

Same as Option A but without Redis:
- Rate limiting uses PostgreSQL or in-memory (single-instance only)
- No centralized cache; rely on PostgreSQL connection pooling and query optimization
- Job scheduling via pg-based solutions (pg-boss, graphile-worker)

**Trade-off:** Simpler infrastructure, but rate limiting is weaker in multi-instance deployments and no price data cache.

### Option C: Managed Backend-as-a-Service (Supabase)

Use Supabase as a unified platform providing:
- PostgreSQL (managed, with connection pooling)
- Auth (Supabase Auth replaces Auth.js)
- Object Storage (Supabase Storage for report files)
- Edge Functions for scheduled jobs
- Real-time subscriptions (useful for notifications)

**Trade-off:** Fastest to ship, less control over auth internals, vendor lock-in risk. Supabase's free tier is generous for MVP.

---

## 5. Schema Overview (Option A)

### Auth Domain
```
users
auth_accounts
sessions
password_reset_tokens
auth_events
```
(Already fully defined in AccountManagementSpec -- use as-is)

### User Preferences
```sql
user_settings
  - user_id UUID FK -> users(id) UNIQUE
  - display_name TEXT
  - theme TEXT DEFAULT 'light'           -- 'light' | 'dark'
  - notify_in_app BOOLEAN DEFAULT true
  - notify_email BOOLEAN DEFAULT false
  - lang_display TEXT DEFAULT 'en'       -- 'en' | 'zh-TW'
  - lang_response TEXT DEFAULT 'en'
  - lang_report TEXT DEFAULT 'en'        -- 'en' | 'zh-TW' | 'both'
  - updated_at TIMESTAMPTZ
```

### Portfolio Domain
```sql
portfolio_tickers
  - id UUID PK
  - user_id UUID FK -> users(id)
  - symbol TEXT NOT NULL
  - company_name TEXT
  - added_at TIMESTAMPTZ
  - UNIQUE(user_id, symbol)

portfolio_groups
  - id UUID PK
  - user_id UUID FK -> users(id)
  - name TEXT NOT NULL
  - sort_order INT NOT NULL
  - view_mode TEXT DEFAULT 'list'        -- 'list' | 'card'
  - sort_by TEXT DEFAULT 'alpha_asc'
  - is_default BOOLEAN DEFAULT false     -- "All" group
  - UNIQUE(user_id, name)

portfolio_group_tickers
  - group_id UUID FK -> portfolio_groups(id) ON DELETE CASCADE
  - ticker_id UUID FK -> portfolio_tickers(id) ON DELETE CASCADE
  - PK(group_id, ticker_id)
```

### Chat History Domain
```sql
conversations
  - id UUID PK
  - user_id UUID FK -> users(id)
  - department TEXT NOT NULL              -- 'secretary' | 'sr' | 'er' | 'mb' | 'rs' | 'mr'
  - title TEXT
  - created_at TIMESTAMPTZ
  - updated_at TIMESTAMPTZ

messages
  - id UUID PK
  - conversation_id UUID FK -> conversations(id) ON DELETE CASCADE
  - role TEXT NOT NULL                    -- 'user' | 'assistant'
  - content TEXT NOT NULL
  - created_at TIMESTAMPTZ
  - INDEX(conversation_id, created_at)
```

### Reports Domain
```sql
reports
  - id UUID PK
  - user_id UUID FK -> users(id)
  - conversation_id UUID FK -> conversations(id) NULL
  - department TEXT NOT NULL
  - filename TEXT NOT NULL
  - file_url TEXT NOT NULL               -- object storage URL/key
  - file_size_bytes BIGINT
  - generated_at TIMESTAMPTZ NOT NULL
  - created_at TIMESTAMPTZ

saved_reports                            -- Repository
  - id UUID PK
  - user_id UUID FK -> users(id)
  - report_id UUID FK -> reports(id) ON DELETE CASCADE
  - saved_at TIMESTAMPTZ NOT NULL
  - UNIQUE(user_id, report_id)
```

### Department Config Domain
```sql
-- Stock Research: per-user report preferences
sr_report_config
  - user_id UUID FK -> users(id) UNIQUE
  - selected_sections JSONB              -- array of section identifiers
  - custom_sections JSONB                -- [{name, description}]
  - report_length TEXT DEFAULT 'normal'  -- 'concise' | 'normal' | 'elaborative'

-- Earnings Report: watchlist
er_watchlist
  - id UUID PK
  - user_id UUID FK -> users(id)
  - symbol TEXT NOT NULL
  - company_name TEXT
  - next_earnings_date DATE
  - release_timing TEXT                  -- 'pre_market' | 'post_market' | 'unknown'
  - added_at TIMESTAMPTZ
  - UNIQUE(user_id, symbol)

-- Morning Briefings: coverage config
mb_coverage_config
  - user_id UUID FK -> users(id) UNIQUE
  - sections JSONB                       -- [{section_id, enabled, topics: [{keyword, notes}]}]
  - custom_sections JSONB                -- [{name, description, topics}]

mb_schedules
  - id UUID PK
  - user_id UUID FK -> users(id)
  - time TIME NOT NULL
  - timezone TEXT NOT NULL
  - days_of_week INT[] NOT NULL          -- [0-6], 0=Sunday
  - enabled BOOLEAN DEFAULT true
  - created_at TIMESTAMPTZ

-- Retail Sentiment: monitor list
rs_monitor_items
  - id UUID PK
  - user_id UUID FK -> users(id)
  - keyword TEXT NOT NULL
  - item_type TEXT                       -- 'ticker' | 'hashtag' | 'topic'
  - added_at TIMESTAMPTZ
  - UNIQUE(user_id, keyword)

-- Macro Research: no persistent config (on-demand only)
```

---

## 6. Sizing Estimates

| Data Category | Per User (1 year) | 1,000 Users (1 year) |
|---|---|---|
| Auth + Settings | ~5 KB | ~5 MB |
| Portfolio (50 tickers, 5 groups) | ~10 KB | ~10 MB |
| Chat messages (500 conversations, 20 msgs each) | ~5 MB | ~5 GB |
| Report metadata (100 reports) | ~50 KB | ~50 MB |
| Report files (100 reports, avg 500KB) | ~50 MB | ~50 GB |
| Department configs | ~20 KB | ~20 MB |
| **Total structured (PostgreSQL)** | **~5 MB** | **~5 GB** |
| **Total files (Object Storage)** | **~50 MB** | **~50 GB** |

PostgreSQL comfortably handles this scale. Object storage handles file growth cost-effectively.

---

## 7. Key Design Decisions to Make

| Decision | Options | Recommendation |
|---|---|---|
| ORM | Prisma vs Drizzle | Prisma (per AccountManagementSpec recommendation, better DX) |
| PostgreSQL hosting | Neon, Supabase, RDS, Railway | Neon or Supabase (serverless-friendly, generous free tier) |
| Object storage | S3, Cloudflare R2, Supabase Storage | Match hosting choice; R2 has zero egress fees |
| Redis hosting | Upstash, ElastiCache | Upstash (serverless, pay-per-request, simple) |
| Chat message storage | PostgreSQL vs separate document DB | PostgreSQL (volume is manageable, keeps stack simple) |
| Department config format | Normalized tables vs JSONB columns | JSONB for flexible configs (sections, topics); normalized for watchlists/schedules |
| File reference strategy | Store URL in DB vs store object key + resolve at runtime | Store object key; generate signed URLs at read time for security |
| Migration strategy | Prisma Migrate vs manual SQL | Prisma Migrate (matches ORM choice) |

---

## 8. Summary

**Recommended stack: PostgreSQL + Object Storage + Redis (Option A)**

- One PostgreSQL database holds all structured data across auth, portfolio, chat, reports, and department configs
- Object storage holds report file blobs, referenced by key in PostgreSQL
- Redis handles rate limiting, session caching, price data caching, and job queues
- This aligns with the AccountManagementSpec's existing PostgreSQL recommendation and keeps the architecture simple with three well-understood components
