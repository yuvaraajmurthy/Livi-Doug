-- Chat (spec 2026-10-11 §3): persisted turns so a stateless server can rebuild context, and new memory kinds
-- the chat agent can write. Crisis-flagged turns are never stored.
CREATE TABLE IF NOT EXISTS chat_conversations (
  id         text PRIMARY KEY,
  student_id text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS chat_conversations_student_idx ON chat_conversations (student_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
  id              bigserial PRIMARY KEY,
  student_id      text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  conversation_id text NOT NULL,
  role            text NOT NULL CHECK (role IN ('user', 'assistant')),
  text            text NOT NULL DEFAULT '',
  blocks          jsonb NOT NULL DEFAULT '[]',
  source          text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messages_conv_idx ON chat_messages (student_id, conversation_id, id);
CREATE INDEX IF NOT EXISTS chat_messages_fts_idx ON chat_messages USING gin (to_tsvector('english', text));

ALTER TABLE student_memory DROP CONSTRAINT IF EXISTS student_memory_kind_check;
ALTER TABLE student_memory ADD CONSTRAINT student_memory_kind_check
  CHECK (kind IN ('likes_format','disliked_format','time_works','helped','declined','constraint','rung',
                  'likes','dislikes','interest','goal'));
