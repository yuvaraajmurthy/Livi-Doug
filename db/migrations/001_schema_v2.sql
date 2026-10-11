-- Compass database v2 (engagement edition): Postgres 16 + pgvector
-- Changes from v1: no questionnaire tables (scores are imported), plus the social
-- layer (invites, challenges, wins), The Arc credit, care-first flag, and the
-- Staff Pulse views (conversion funnel, need vs supply, weekly dimension averages).
-- Local: docker run -e POSTGRES_PASSWORD=dev -p 5432:5432 pgvector/pgvector:pg16
-- Rule:  no names, emails, NetIDs or phone numbers of students anywhere.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE DOMAIN dimension AS text CHECK (VALUE IN
  ('emotional','environmental','financial','intellectual','occupational','physical','social','spiritual'));
CREATE DOMAIN campus AS text CHECK (VALUE IN ('new_brunswick','newark','camden','online','community'));

-- 1. PEOPLE AND CONSENT ------------------------------------------------------
CREATE TABLE students (
  id            text PRIMARY KEY,           -- anonymous ID (dataset ID now; hashed SSO subject later)
  campus        campus NOT NULL,
  level         text CHECK (level IN ('undergrad','grad')),
  class_year    text CHECK (class_year IN ('first_year','sophomore','junior','senior','grad')),
  housing       text CHECK (housing IN ('resident','commuter')),
  first_gen     boolean,
  works_20plus_hours boolean,
  school        text,
  home_area     text,
  language      text NOT NULL DEFAULT 'en' CHECK (language IN ('en','es')),
  synthetic     boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE profiles (                      -- what the student chose in Compass
  student_id      text PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
  focus_dimension dimension,                 -- the one area they chose to grow
  barriers        text[],                    -- {'no_time','dont_know_anyone','money','coursework'}
  free_windows    text[],                    -- {'Tue 12:20-14:30'}
  social_rung     smallint NOT NULL DEFAULT 1 CHECK (social_rung BETWEEN 1 AND 3),
  care_first      boolean NOT NULL DEFAULT false,   -- set by the plain-code rule, never by AI
  free_only       boolean NOT NULL DEFAULT true,
  quiet_start     time DEFAULT '22:00', quiet_end time DEFAULT '08:00',
  max_pushes_per_week smallint NOT NULL DEFAULT 3,
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE consents (                      -- append-only; newest row per kind wins
  id bigserial PRIMARY KEY,
  student_id text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('use_scores','push','email','location','social_signals','aggregate_stats')),
  granted boolean NOT NULL, wording_version text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE VIEW current_consents AS
SELECT DISTINCT ON (student_id, kind) student_id, kind, granted, created_at
FROM consents ORDER BY student_id, kind, created_at DESC;

-- 2. SCORES (imported, never computed by AI) ---------------------------------
CREATE TABLE inventory_takes (
  id          bigserial PRIMARY KEY,
  student_id  text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  take_no     smallint NOT NULL,
  taken_on    date NOT NULL,
  source      text NOT NULL CHECK (source IN ('myrutgers','scarletwell_export','synthetic','synthetic_persona')),
  total       numeric(4,2),
  UNIQUE (student_id, take_no)
);
CREATE TABLE dimension_scores (
  take_id   bigint REFERENCES inventory_takes(id) ON DELETE CASCADE,
  dimension dimension,
  score     numeric(4,2) NOT NULL,          -- placeholder scale 1.00-4.00; swap for the official scoring
  PRIMARY KEY (take_id, dimension)
);
CREATE VIEW scores_banded AS                 -- placeholder bands; replace with ScarletWell's cut-offs
SELECT t.student_id, t.take_no, t.taken_on, d.dimension, d.score,
       CASE WHEN d.score < 2.3 THEN 'low' WHEN d.score >= 3.2 THEN 'high' ELSE 'middle' END AS band
FROM inventory_takes t JOIN dimension_scores d ON d.take_id = t.id;

-- 3. KNOWLEDGE BASE ------------------------------------------------------------
CREATE TABLE kb_items (
  id            text PRIMARY KEY,
  kind          text NOT NULL CHECK (kind IN ('event','resource','study','online')),
  title         text NOT NULL,
  summary       text,
  campus        campus NOT NULL,
  venue         text, address text, lat double precision, lon double precision,
  starts_at     timestamp, ends_at timestamp,   -- local Eastern time
  cost          text NOT NULL DEFAULT 'unknown' CHECK (cost IN ('free','paid','unknown')),
  social_level  smallint CHECK (social_level BETWEEN 1 AND 3),   -- 1 just show up, 2 structured, 3 open social
  solo_friendly boolean,
  url           text,
  source        text NOT NULL,
  arc_activity_id text,                      -- The Arc activity to credit, when one exists
  synthetic     boolean NOT NULL DEFAULT false,
  active        boolean NOT NULL DEFAULT true,
  embedding     vector(1024)
);
CREATE TABLE kb_tags (
  item_id text REFERENCES kb_items(id) ON DELETE CASCADE,
  tag_type text CHECK (tag_type IN ('dimension','cause','audience','format')),
  tag text, confidence real NOT NULL DEFAULT 1.0,
  tagged_by text NOT NULL DEFAULT 'keyword' CHECK (tagged_by IN ('ai','staff','keyword','synthetic')),
  PRIMARY KEY (item_id, tag_type, tag)
);
CREATE INDEX kb_tags_lookup ON kb_tags (tag_type, tag);

-- 4. THE LOOP ------------------------------------------------------------------
CREATE TABLE recommendations (
  id          bigserial PRIMARY KEY,
  student_id  text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  item_id     text NOT NULL REFERENCES kb_items(id),
  dimension   dimension NOT NULL,
  rung        smallint,
  why_shown   text,                          -- "Fits your Tuesday gap, 3 min walk, free lunch"
  shown_on    date NOT NULL,
  status      text NOT NULL DEFAULT 'shown' CHECK (status IN ('shown','dismissed','snoozed','committed'))
);
CREATE TABLE commitments (
  id                bigserial PRIMARY KEY,
  recommendation_id bigint UNIQUE REFERENCES recommendations(id) ON DELETE CASCADE,
  student_id        text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  item_id           text NOT NULL REFERENCES kb_items(id),
  if_then_plan      text,                    -- "When Econ ends Tue 12:20, I walk to the Robeson Center"
  with_friend       boolean NOT NULL DEFAULT false,
  status            text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','went','missed','cancelled')),
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE invites (                       -- bring-a-friend: a link, never a contact list
  id            bigserial PRIMARY KEY,
  commitment_id bigint NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
  token         text NOT NULL UNIQUE,
  opened_at     timestamptz, accepted_at timestamptz
);
CREATE TABLE feedback (                      -- "did you go? did it help?"
  id            bigserial PRIMARY KEY,
  commitment_id bigint UNIQUE REFERENCES commitments(id) ON DELETE CASCADE,
  student_id    text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  went          boolean NOT NULL,
  helped        smallint CHECK (helped BETWEEN 1 AND 5),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE arc_credits (                   -- only "attended" ever leaves Compass
  id            bigserial PRIMARY KEY,
  commitment_id bigint NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
  arc_activity_id text,
  status        text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed','mock')),
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- 5. SOCIAL LAYER --------------------------------------------------------------
CREATE TABLE challenges (
  id          text PRIMARY KEY,
  title       text NOT NULL,
  scope       text NOT NULL CHECK (scope IN ('all','campus','hall','club')),
  scope_value text,
  dimension   dimension,
  starts_on   date NOT NULL, ends_on date NOT NULL,
  goal_steps  int,
  rule        text
);
CREATE TABLE challenge_steps (               -- cooperative progress; no individual leaderboard
  challenge_id  text REFERENCES challenges(id) ON DELETE CASCADE,
  commitment_id bigint REFERENCES commitments(id) ON DELETE CASCADE,
  weight        smallint NOT NULL DEFAULT 1, -- 2 when taken with a friend
  PRIMARY KEY (challenge_id, commitment_id)
);
CREATE TABLE wins (                          -- anonymous wins wall
  id          text PRIMARY KEY,
  student_id  text REFERENCES students(id) ON DELETE SET NULL,  -- never shown
  campus      campus, dimension dimension,
  text        text NOT NULL CHECK (length(text) <= 140),
  status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','routed_to_care')),
  same_here   int NOT NULL DEFAULT 0,        -- the only reaction; no comments, no replies
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- 6. SAFETY, NOTIFICATIONS ------------------------------------------------------
CREATE TABLE safety_events (                 -- that the check fired; never what was said
  id bigserial PRIMARY KEY,
  student_id text REFERENCES students(id) ON DELETE SET NULL,
  source text NOT NULL CHECK (source IN ('ask_box','wins_post','barrier_text','voice','score_rule')),
  level text NOT NULL CHECK (level IN ('crisis','care_first','guardrail_block')),
  action text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE crisis_lines (
  id serial PRIMARY KEY, campus text NOT NULL, name text NOT NULL, phone text, text_to text,
  hours text NOT NULL, verified_on date NOT NULL, verified_by text NOT NULL
);
CREATE TABLE push_subscriptions (
  id bigserial PRIMARY KEY, student_id text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  endpoint text NOT NULL UNIQUE, p256dh text NOT NULL, auth text NOT NULL, revoked_at timestamptz
);
CREATE TABLE notifications (
  id bigserial PRIMARY KEY, student_id text NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  channel text NOT NULL CHECK (channel IN ('push','email')),
  kind text NOT NULL CHECK (kind IN ('reminder','followup','weekly_pick','retake_nudge','challenge')),
  title text NOT NULL, body text NOT NULL,   -- lock-screen safe: never scores, moods or crisis words
  deep_link text NOT NULL, send_at timestamptz NOT NULL, sent_at timestamptz, opened_at timestamptz,
  status text NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','sent','opened','failed','cancelled'))
);

-- 7. STAFF PULSE VIEWS (aggregates only; groups under 10 students are hidden) ---
CREATE VIEW what_helped AS
SELECT c.student_id, c.item_id, count(*) AS times, round(avg(f.helped), 2) AS avg_helped
FROM commitments c JOIN feedback f ON f.commitment_id = c.id
WHERE f.went GROUP BY c.student_id, c.item_id;

CREATE VIEW going_counts AS                  -- "14 students are going"; shown only from 5 up
SELECT item_id, count(*) AS going FROM commitments
WHERE status IN ('planned','went') GROUP BY item_id HAVING count(*) >= 5;

CREATE VIEW conversion_funnel AS
SELECT s.campus, r.dimension,
       count(DISTINCT r.student_id)                                   AS students,
       count(*)                                                       AS suggested,
       count(c.id)                                                    AS committed,
       count(c.id) FILTER (WHERE c.with_friend)                       AS with_friend,
       count(f.id) FILTER (WHERE f.went)                              AS attended,
       count(f.id) FILTER (WHERE f.went AND f.helped >= 4)            AS helped
FROM recommendations r
JOIN students s ON s.id = r.student_id
LEFT JOIN commitments c ON c.recommendation_id = r.id
LEFT JOIN feedback f ON f.commitment_id = c.id
GROUP BY s.campus, r.dimension
HAVING count(DISTINCT r.student_id) >= 10;

CREATE VIEW latest_scores AS
SELECT DISTINCT ON (t.student_id, d.dimension) t.student_id, d.dimension, d.score, t.taken_on
FROM inventory_takes t JOIN dimension_scores d ON d.take_id = t.id
ORDER BY t.student_id, d.dimension, t.taken_on DESC;

CREATE VIEW need_vs_supply AS                -- low scorers per campus and dimension vs. free items there
WITH need AS (
  SELECT s.campus, l.dimension, count(*) AS low_students
  FROM latest_scores l JOIN students s ON s.id = l.student_id
  WHERE l.score < 2.3 GROUP BY s.campus, l.dimension),
supply AS (
  SELECT i.campus, t.tag AS dimension, count(DISTINCT i.id) AS items
  FROM kb_items i JOIN kb_tags t ON t.item_id = i.id AND t.tag_type = 'dimension'
  WHERE i.active GROUP BY i.campus, t.tag)
SELECT n.campus, n.dimension, n.low_students, coalesce(s.items, 0) AS items,
       round(n.low_students::numeric / greatest(coalesce(s.items, 0), 1), 1) AS low_students_per_item
FROM need n LEFT JOIN supply s ON s.campus = n.campus AND s.dimension = n.dimension
WHERE n.low_students >= 10;

CREATE VIEW weekly_dimension_avg AS          -- for the dips heatmap
SELECT s.campus, date_trunc('week', t.taken_on)::date AS week, d.dimension,
       count(*) AS takes, round(avg(d.score), 2) AS avg_score
FROM inventory_takes t JOIN dimension_scores d ON d.take_id = t.id JOIN students s ON s.id = t.student_id
GROUP BY 1, 2, 3 HAVING count(*) >= 10;

-- "Forget me" = DELETE FROM students WHERE id = $1;  (everything personal cascades)
