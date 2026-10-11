import pytest

from app.ask.staff_sql import validate


@pytest.mark.parametrize("sql", [
    "SELECT campus, low_students_per_item FROM staff_gaps(NULL, 'financial', NULL, NULL, NULL) WHERE NOT suppressed ORDER BY 2 DESC",
    "select week, avg(avg_score) from staff_weekly('camden', null, null, null, null) where not suppressed group by week",
])
def test_valid(sql):
    assert validate(sql)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM students",
    "SELECT * FROM staff_gaps(NULL,NULL,NULL,NULL,NULL); DROP TABLE students",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "SELECT * FROM staff_gaps(NULL,NULL,NULL,NULL,NULL) JOIN inventory_takes ON true",
    "SELECT pg_sleep(10)",
    "UPDATE wins SET status='approved'",
    "SELECT * FROM staff_gaps",
    "SELECT * FROM staff_gaps(NULL,NULL,NULL,NULL,NULL) -- comment",
])
def test_rejected(sql):
    assert validate(sql) is None
