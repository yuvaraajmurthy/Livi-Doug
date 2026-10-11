-- Compass additions on top of schema_v2: simulated clock, demo sessions, memory, richer KB,
-- ranked recommendations with reasons, notification lifecycle, caches. See spec section 6.

-- Clock and sessions ---------------------------------------------------------------
CREATE TABLE app_clock (
  id      smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  sim_now timestamptz NOT NULL
);
CREATE TABLE demo_sessions (
  sid        text PRIMARY KEY,
  persona    text NOT NULL,
  student_id text REFERENCES students(id) ON DELETE CASCADE,
  sim_now    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Profiles --------------------------------------------------------------------------
ALTER TABLE profiles
  ADD COLUMN language    text NOT NULL DEFAULT 'en' CHECK (language IN ('en','es')),
  ADD COLUMN rung_reason text,
  ADD COLUMN barriers_from_text text[] NOT NULL DEFAULT '{}';

-- Knowledge base ----------------------------------------------------------------------
ALTER TABLE kb_items DROP CONSTRAINT kb_items_kind_check;
ALTER TABLE kb_items ADD CONSTRAINT kb_items_kind_check
  CHECK (kind IN ('event','resource','study','online','place','micro'));
ALTER TABLE kb_items
  ADD COLUMN phone        text,
  ADD COLUMN hours_text   text,
  ADD COLUMN open_hours   jsonb,          -- {"mon": [["08:00","22:00"]], ...} only when published
  ADD COLUMN source_url   text,
  ADD COLUMN attribution  text,
  ADD COLUMN verified_on  date,
  ADD COLUMN summary_es   text,
  ADD COLUMN modified_at  timestamptz,
  ADD COLUMN all_day      boolean NOT NULL DEFAULT false,
  ADD COLUMN demo_pin     boolean NOT NULL DEFAULT false,
  ADD COLUMN series_key   text,
  ADD COLUMN formats      text[] NOT NULL DEFAULT '{}',
  ADD COLUMN ext_id       text,
  ADD COLUMN updated_at   timestamptz NOT NULL DEFAULT now();
CREATE INDEX kb_items_campus_start ON kb_items (campus, starts_at);

ALTER TABLE kb_tags DROP CONSTRAINT kb_tags_tag_type_check;
ALTER TABLE kb_tags ADD CONSTRAINT kb_tags_tag_type_check
  CHECK (tag_type IN ('dimension','cause','audience','format','barrier'));

-- Recommendations, commitments --------------------------------------------------------
ALTER TABLE recommendations
  ADD COLUMN set_id         text,
  ADD COLUMN rank           smallint,
  ADD COLUMN reasons        jsonb,
  ADD COLUMN engine_version text,
  ADD COLUMN pushed         boolean NOT NULL DEFAULT true,
  ADD COLUMN why_source     text,
  ADD COLUMN shown_at       timestamptz;
CREATE INDEX recommendations_student ON recommendations (student_id, status);
CREATE INDEX recommendations_item ON recommendations (item_id);

ALTER TABLE commitments
  ADD COLUMN plan_source text,
  ADD COLUMN starts_at   timestamptz,
  ADD COLUMN ends_at     timestamptz,
  ADD COLUMN reminder_at timestamptz,
  ADD COLUMN followup_at timestamptz,
  ADD COLUMN planned_at  timestamptz;
CREATE INDEX commitments_student ON commitments (student_id);
CREATE INDEX commitments_item ON commitments (item_id, status);

ALTER TABLE arc_credits ADD COLUMN occurred_at timestamptz;

-- Social -------------------------------------------------------------------------------
ALTER TABLE challenges
  ADD COLUMN group_size    int NOT NULL DEFAULT 0,
  ADD COLUMN base_progress int NOT NULL DEFAULT 0,
  ADD COLUMN synthetic     boolean NOT NULL DEFAULT true,
  ADD COLUMN scope_label   text;

ALTER TABLE wins DROP CONSTRAINT wins_status_check;
ALTER TABLE wins ADD CONSTRAINT wins_status_check
  CHECK (status IN ('pending','approved','held','rejected','routed_to_care'));
ALTER TABLE wins
  ADD COLUMN moderation_code text,
  ADD COLUMN synthetic boolean NOT NULL DEFAULT false;
CREATE TABLE win_reactions (
  win_id     text REFERENCES wins(id) ON DELETE CASCADE,
  student_id text REFERENCES students(id) ON DELETE CASCADE,
  PRIMARY KEY (win_id, student_id)
);

-- Safety ------------------------------------------------------------------------------
ALTER TABLE safety_events DROP CONSTRAINT safety_events_level_check;
ALTER TABLE safety_events ADD CONSTRAINT safety_events_level_check
  CHECK (level IN ('crisis','concern','care_first','guardrail_block'));
ALTER TABLE safety_events DROP CONSTRAINT safety_events_source_check;
ALTER TABLE safety_events ADD CONSTRAINT safety_events_source_check
  CHECK (source IN ('ask_box','wins_post','barrier_text','voice','score_rule','plan_text'));
ALTER TABLE safety_events ADD COLUMN stage text;

DROP TABLE crisis_lines;
CREATE TABLE crisis_lines (
  id          serial PRIMARY KEY,
  campus      text NOT NULL CHECK (campus IN ('all','new_brunswick','newark','camden')),
  name        text NOT NULL,
  kind        text NOT NULL CHECK (kind IN ('call','text','web','emergency')),
  contact     text NOT NULL,
  href        text,
  hours       text NOT NULL,
  language    text NOT NULL DEFAULT 'any',
  sort        smallint NOT NULL DEFAULT 100,
  verified    boolean NOT NULL DEFAULT false,
  verified_on date,
  verified_by text,
  source_url  text
);

-- Notifications ----------------------------------------------------------------------
ALTER TABLE notifications DROP CONSTRAINT notifications_status_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_status_check
  CHECK (status IN ('scheduled','sent','opened','failed','cancelled','held_budget','skipped'));
ALTER TABLE notifications DROP CONSTRAINT notifications_channel_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_channel_check CHECK (channel IN ('push','email','in_app'));
ALTER TABLE notifications
  ADD COLUMN commitment_id bigint REFERENCES commitments(id) ON DELETE CASCADE,
  ADD COLUMN delivered     text,
  ADD COLUMN created_at    timestamptz NOT NULL DEFAULT now();
CREATE INDEX notifications_due ON notifications (status, send_at);
CREATE UNIQUE INDEX notifications_one_per_kind ON notifications (commitment_id, kind) WHERE commitment_id IS NOT NULL;
ALTER TABLE push_subscriptions ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

-- Memory: what Compass learned, typed and bounded. Never raw text, scores, moods or health. -----
CREATE TABLE student_memory (
  id            bigserial PRIMARY KEY,
  student_id    text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  kind          text NOT NULL CHECK (kind IN ('likes_format','disliked_format','time_works','helped','declined','constraint','rung')),
  key           text NOT NULL,
  statement     text NOT NULL,
  statement_es  text,
  source_type   text NOT NULL CHECK (source_type IN ('rating','attendance','decline','your_words','rule','you_chose')),
  source_label  text NOT NULL,
  source_ref    jsonb,
  confidence    real NOT NULL DEFAULT 0.6,
  used_for      text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  last_used_at  timestamptz,
  UNIQUE (student_id, kind, key)
);

-- Caches and jobs ---------------------------------------------------------------------
CREATE TABLE llm_cache (
  key        text PRIMARY KEY,          -- sha256 of purpose + lang + facts; never a student id
  purpose    text NOT NULL,
  lang       text NOT NULL,
  model      text NOT NULL,
  text       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wording_queue (
  key        text PRIMARY KEY,
  purpose    text NOT NULL,
  lang       text NOT NULL,
  facts      jsonb NOT NULL,
  attempts   smallint NOT NULL DEFAULT 0,
  status     text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','done','failed')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE geocode_cache (
  address    text PRIMARY KEY,
  lat        double precision,
  lon        double precision,
  provider   text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ingest_runs (
  id         bigserial PRIMARY KEY,
  source     text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  fetched    int, upserted int, skipped int, failed int,
  note       text
);
