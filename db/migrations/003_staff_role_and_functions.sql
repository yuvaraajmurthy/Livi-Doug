-- Staff Pulse: small-group suppression enforced in the database.
-- Staff routes run `SET LOCAL ROLE compass_staff_ro`. That role can read nothing except through
-- these SECURITY DEFINER functions, and the functions never return a number for a group under 10.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_staff_ro') THEN
    CREATE ROLE compass_staff_ro NOLOGIN;
  END IF;
END $$;
GRANT compass_staff_ro TO CURRENT_USER;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM compass_staff_ro;
GRANT USAGE ON SCHEMA public TO compass_staff_ro;

CREATE OR REPLACE FUNCTION staff_min_group() RETURNS int LANGUAGE sql IMMUTABLE AS $$ SELECT 10 $$;

-- Students matching a population filter.
CREATE OR REPLACE FUNCTION staff_population(p_campus text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (id text, campus text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT s.id, s.campus::text FROM students s
  WHERE (p_campus IS NULL OR s.campus = p_campus)
    AND (p_level IS NULL OR s.level = p_level)
    AND (p_first_gen IS NULL OR s.first_gen = p_first_gen)
    AND (p_housing IS NULL OR s.housing = p_housing)
$$;
REVOKE ALL ON FUNCTION staff_population(text, text, boolean, text) FROM PUBLIC;

CREATE OR REPLACE FUNCTION staff_funnel(p_campus text, p_dimension text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (campus text, dimension text, suppressed boolean, students bigint, suggested bigint, committed bigint,
               with_friend bigint, attended bigint, helped bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH g AS (
    SELECT p.campus, r.dimension::text AS dimension,
           count(DISTINCT r.student_id) AS students, count(*) AS suggested, count(c.id) AS committed,
           count(c.id) FILTER (WHERE c.with_friend) AS with_friend,
           count(f.id) FILTER (WHERE f.went) AS attended,
           count(f.id) FILTER (WHERE f.went AND f.helped >= 4) AS helped
    FROM recommendations r
    JOIN staff_population(p_campus, p_level, p_first_gen, p_housing) p ON p.id = r.student_id
    LEFT JOIN commitments c ON c.recommendation_id = r.id
    LEFT JOIN feedback f ON f.commitment_id = c.id
    WHERE p_dimension IS NULL OR r.dimension = p_dimension
    GROUP BY 1, 2)
  SELECT campus, dimension, students < staff_min_group(),
         CASE WHEN students >= staff_min_group() THEN students END,
         CASE WHEN students >= staff_min_group() THEN suggested END,
         CASE WHEN students >= staff_min_group() THEN committed END,
         CASE WHEN students >= staff_min_group() THEN with_friend END,
         CASE WHEN students >= staff_min_group() THEN attended END,
         CASE WHEN students >= staff_min_group() THEN helped END
  FROM g ORDER BY campus, dimension
$$;

CREATE OR REPLACE FUNCTION staff_gaps(p_campus text, p_dimension text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (campus text, dimension text, suppressed boolean, low_students bigint, items bigint, low_students_per_item numeric)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH latest AS (
    SELECT DISTINCT ON (t.student_id, d.dimension) t.student_id, d.dimension::text AS dimension, d.score
    FROM inventory_takes t JOIN dimension_scores d ON d.take_id = t.id
    ORDER BY t.student_id, d.dimension, t.taken_on DESC),
  need AS (
    SELECT p.campus, l.dimension, count(*) AS low_students
    FROM latest l JOIN staff_population(p_campus, p_level, p_first_gen, p_housing) p ON p.id = l.student_id
    WHERE l.score < 2.3 AND (p_dimension IS NULL OR l.dimension = p_dimension)
    GROUP BY 1, 2),
  supply AS (
    SELECT i.campus::text AS campus, t.tag AS dimension, count(DISTINCT i.id) AS items
    FROM kb_items i JOIN kb_tags t ON t.item_id = i.id AND t.tag_type = 'dimension'
    WHERE i.active AND i.kind <> 'micro'
    GROUP BY 1, 2)
  SELECT n.campus, n.dimension, n.low_students < staff_min_group(),
         CASE WHEN n.low_students >= staff_min_group() THEN n.low_students END,
         CASE WHEN n.low_students >= staff_min_group() THEN coalesce(s.items, 0) END,
         CASE WHEN n.low_students >= staff_min_group()
              THEN round(n.low_students::numeric / greatest(coalesce(s.items, 0), 1), 1) END
  FROM need n LEFT JOIN supply s ON s.campus = n.campus AND s.dimension = n.dimension
  ORDER BY 6 DESC NULLS LAST
$$;

CREATE OR REPLACE FUNCTION staff_weekly(p_campus text, p_dimension text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (campus text, dimension text, week date, suppressed boolean, avg_score numeric, n bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH g AS (
    SELECT p.campus, d.dimension::text AS dimension, date_trunc('week', t.taken_on)::date AS week,
           avg(d.score) AS avg_score, count(DISTINCT t.student_id) AS n
    FROM inventory_takes t
    JOIN dimension_scores d ON d.take_id = t.id
    JOIN staff_population(p_campus, p_level, p_first_gen, p_housing) p ON p.id = t.student_id
    WHERE p_dimension IS NULL OR d.dimension = p_dimension
    GROUP BY 1, 2, 3)
  SELECT campus, dimension, week, n < staff_min_group(),
         CASE WHEN n >= staff_min_group() THEN round(avg_score, 3) END,
         CASE WHEN n >= staff_min_group() THEN n END
  FROM g ORDER BY campus, dimension, week
$$;

CREATE OR REPLACE FUNCTION staff_dips(p_threshold numeric, p_campus text, p_dimension text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (campus text, dimension text, week date, avg_score numeric, trailing_avg numeric, drop numeric, n bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH w AS (
    SELECT * FROM staff_weekly(p_campus, p_dimension, p_level, p_first_gen, p_housing) WHERE NOT suppressed),
  t AS (
    SELECT w.*, avg(w.avg_score) OVER (PARTITION BY w.campus, w.dimension ORDER BY w.week
                                       ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS trail_avg,
           count(*) OVER (PARTITION BY w.campus, w.dimension ORDER BY w.week
                          ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS k
    FROM w)
  SELECT campus, dimension, week, avg_score, round(trail_avg, 3), round(trail_avg - avg_score, 3), n
  FROM t WHERE k = 4 AND trail_avg - avg_score >= p_threshold
  ORDER BY week, campus, dimension
$$;

CREATE OR REPLACE FUNCTION staff_retakes(p_campus text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (campus text, suppressed boolean, users bigint, users_retook bigint, non_users bigint, non_users_retook bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH s AS (
    SELECT p.campus, p.id,
           EXISTS (SELECT 1 FROM recommendations r WHERE r.student_id = p.id) AS user_,
           (SELECT max(take_no) FROM inventory_takes t WHERE t.student_id = p.id) >= 2 AS retook
    FROM staff_population(p_campus, p_level, p_first_gen, p_housing) p),
  g AS (
    SELECT campus, count(*) FILTER (WHERE user_) AS users, count(*) FILTER (WHERE user_ AND retook) AS users_retook,
           count(*) FILTER (WHERE NOT user_) AS non_users, count(*) FILTER (WHERE NOT user_ AND retook) AS non_users_retook
    FROM s GROUP BY campus)
  SELECT campus, least(users, non_users) < staff_min_group(),
         CASE WHEN least(users, non_users) >= staff_min_group() THEN users END,
         CASE WHEN least(users, non_users) >= staff_min_group() THEN users_retook END,
         CASE WHEN least(users, non_users) >= staff_min_group() THEN non_users END,
         CASE WHEN least(users, non_users) >= staff_min_group() THEN non_users_retook END
  FROM g ORDER BY campus
$$;

GRANT EXECUTE ON FUNCTION staff_min_group(), staff_funnel(text,text,text,boolean,text), staff_gaps(text,text,text,boolean,text),
  staff_weekly(text,text,text,boolean,text), staff_dips(numeric,text,text,text,boolean,text),
  staff_retakes(text,text,boolean,text) TO compass_staff_ro;
