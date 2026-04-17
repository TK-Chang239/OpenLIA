# Chat History Component Spec

> **Placeholder (2026-04-15):** Full spec pending. This component manages the chat session sidebar, session list, and message history display for chat-based departments (Secretary, Equity Research follow-ups).

## Database References

Chat persistence is backed by the following tables from `database-design.md`:

- **`chat_sessions`** — one row per conversation thread. Columns: `user_id`, `department`, `title` (auto-generated or user-renamed), `pinned`, `archived_at`. Departments: `secretary`, `equity_research`.
- **`chat_messages`** — individual messages within a session. Columns: `session_id`, `role` (`user`, `assistant`, `system`, `tool`), `content` (Text), `tool_calls` (JSON), `token_usage` (JSON), `stopped_at` (non-null if cancelled mid-stream).
- **`chat_attachments`** — reserved for v2 vision inputs. Columns: `message_id`, `file_name`, `mime_type`, `file_path`, `size_bytes`.

## Key Behaviors (to be specified)

- Session list in sidebar, sorted by last activity
- Search across session titles and message content
- Pin / archive / delete sessions
- Rename session title inline
- Session auto-title generation (first user message or LLM summary)
- Infinite scroll or pagination for long session lists
- Message persistence on `chat.done` SSE event (server-side, not frontend concern)
- Partial message persistence on cancellation (`stopped_at` marker)
