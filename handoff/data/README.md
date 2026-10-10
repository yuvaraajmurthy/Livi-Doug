# Compass dummy dataset (SYNTHETIC: not real students)

A made-up fall 2026 semester for 1,500 students plus 5 hand-made demo personas.
Every pattern (midterm and finals dips, group differences, the effect of taking
steps, going with a friend) was built in on purpose so the demo has something to
show. Label it "synthetic" on every screen. Replace `out/inventory_results.csv`
with ScarletWell's de-identified export when it arrives.

## Files (in `out/`)
| File | Rows | Contents |
|---|---|---|
| students.csv | 1,505 | anonymous ID, campus, level, year, housing, first_gen, works_20plus_hours, school, home_area, preferred_language |
| inventory_results.csv | 3,058 | one row per inventory take: taken_on, 8 dimension scores (1.00-4.00), total |
| compass_usage_log.csv | 8,407 | weekly suggestions to 880 Compass users: item, focus dimension, committed, invited_friend, friend_joined, attended, helped_1to5 |
| kb_items_with_samples.csv | 172 | 116 real items (live Wellness Calendar events + ScarletWell list) + 56 SAMPLE Newark/Camden events (synthetic=True) |
| academic_calendar_fall2026.json | | real registrar dates + an APPROXIMATE midterm window |
| personas.json | 5 | Andre, Jordan, Priya, Sofia, Taylor (stories, free windows, takes, demo steps) |
| challenges.json / wins.json | 3 / 20 | sample group challenges and anonymous wins |
| sql/ | | the same data shaped for schema_v2.sql, plus load.sql |

## Placeholders to replace
- Score scale 1.00-4.00 (mean of items on a 4-point scale) and bands (low < 2.3, high >= 3.2).
- Care-first threshold (emotional <= 1.6) is a placeholder; ScarletWell sets the real one.
- Sample events use real venue names with approximate coordinates; they are not real events.

## Run
    pip install numpy pandas
    python3 generate.py            # writes out/
    python3 load_demo.py           # writes out/sql/
    createdb compass && psql -d compass -f schema_v2.sql -f out/sql/load.sql
    # try: SELECT * FROM conversion_funnel; SELECT * FROM need_vs_supply; SELECT * FROM weekly_dimension_avg;
