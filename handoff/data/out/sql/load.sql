\set ON_ERROR_STOP on
\copy students (id, campus, level, class_year, housing, first_gen, works_20plus_hours, school, home_area, language, synthetic) FROM 'out/sql/students.csv' CSV HEADER
\copy inventory_takes (id, student_id, take_no, taken_on, source, total) FROM 'out/sql/inventory_takes.csv' CSV HEADER
SELECT setval('inventory_takes_id_seq', (SELECT max(id) FROM inventory_takes));
\copy dimension_scores FROM 'out/sql/dimension_scores.csv' CSV HEADER
\copy kb_items (id, kind, title, campus, venue, address, lat, lon, starts_at, ends_at, cost, social_level, solo_friendly, source, synthetic) FROM 'out/sql/kb_items.csv' CSV HEADER NULL ''
\copy kb_tags FROM 'out/sql/kb_tags.csv' CSV HEADER
\copy recommendations (id, student_id, item_id, dimension, shown_on, status) FROM 'out/sql/recommendations.csv' CSV HEADER
\copy commitments (id, recommendation_id, student_id, item_id, with_friend, status) FROM 'out/sql/commitments.csv' CSV HEADER
CREATE TEMP TABLE inv_stage (commitment_id bigint, token text, accepted boolean);
\copy inv_stage FROM 'out/sql/invites.csv' CSV HEADER
INSERT INTO invites (commitment_id, token, accepted_at) SELECT commitment_id, token, CASE WHEN accepted THEN now() END FROM inv_stage;
\copy feedback (commitment_id, student_id, went, helped) FROM 'out/sql/feedback.csv' CSV HEADER NULL ''
INSERT INTO arc_credits (commitment_id, status) SELECT commitment_id, 'mock' FROM feedback WHERE went;
\copy wins (id, campus, dimension, text, status, same_here) FROM 'out/sql/wins.csv' CSV HEADER
INSERT INTO challenges (id, title, scope, dimension, starts_on, ends_on, rule) VALUES ('ch-campus-cup-oct', 'Scarlet Wellness Cup: steps this week', 'campus', NULL, '2026-10-05', ('2026-10-05'::date + 6), 'Cooperative: each campus races its own goal, sized to enrollment. No individual leaderboard.');
INSERT INTO challenges (id, title, scope, dimension, starts_on, ends_on, rule) VALUES ('ch-sleep-week', 'Sleep Week: three wind-down nights', 'all', 'physical', '2026-10-19', ('2026-10-19'::date + 6), 'Timed for midterms. Counts check-ins, not hours slept.');
INSERT INTO challenges (id, title, scope, dimension, starts_on, ends_on, rule) VALUES ('ch-busch-halls', 'Busch residence halls: bring-a-friend week', 'hall', 'social', '2026-11-02', ('2026-11-02'::date + 6), 'Steps taken with a friend count double.');
