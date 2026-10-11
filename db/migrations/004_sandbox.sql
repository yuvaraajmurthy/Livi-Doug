-- Sandbox students: per-session clones of a demo persona for table-mode tours (spec: web design 11.1).
-- Staff never count them; demo reset and a 6-hour sweep delete them.
ALTER TABLE students ADD COLUMN IF NOT EXISTS sandbox boolean NOT NULL DEFAULT false;
ALTER TABLE students ADD COLUMN IF NOT EXISTS sandbox_created timestamptz;
CREATE INDEX IF NOT EXISTS students_sandbox_idx ON students (sandbox) WHERE sandbox;

CREATE OR REPLACE FUNCTION staff_population(p_campus text, p_level text, p_first_gen boolean, p_housing text)
RETURNS TABLE (id text, campus text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT s.id, s.campus::text FROM students s
  WHERE NOT s.sandbox
    AND (p_campus IS NULL OR s.campus = p_campus)
    AND (p_level IS NULL OR s.level = p_level)
    AND (p_first_gen IS NULL OR s.first_gen = p_first_gen)
    AND (p_housing IS NULL OR s.housing = p_housing)
$$;
REVOKE ALL ON FUNCTION staff_population(text, text, boolean, text) FROM PUBLIC;
