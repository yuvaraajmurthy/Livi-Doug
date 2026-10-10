"""Shape the synthetic dataset into schema_v2 tables and write load.sql.

Run:  python3 load_demo.py && psql "$DATABASE_URL" -f ../compass-kb/schema_v2.sql -f out/sql/load.sql
"""
import json, secrets
from pathlib import Path
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
SQL = OUT / "sql"; SQL.mkdir(exist_ok=True)
D = ["emotional", "environmental", "financial", "intellectual", "occupational", "physical", "social", "spiritual"]

S = pd.read_csv(OUT / "students.csv")
R = pd.read_csv(OUT / "inventory_results.csv")
L = pd.read_csv(OUT / "compass_usage_log.csv")
I = pd.read_csv(OUT / "kb_items_with_samples.csv")
C = json.load(open(OUT / "challenges.json"))
W = json.load(open(OUT / "wins.json"))

S.rename(columns={"student_id": "id", "preferred_language": "language"})[
    ["id", "campus", "level", "class_year", "housing", "first_gen", "works_20plus_hours", "school", "home_area", "language", "synthetic"]
].to_csv(SQL / "students.csv", index=False)

R = R.sort_values(["student_id", "take_no"]).reset_index(drop=True)
R["id"] = R.index + 1
R[["id", "student_id", "take_no", "taken_on", "source", "total"]].to_csv(SQL / "inventory_takes.csv", index=False)
R.melt(id_vars=["id"], value_vars=D, var_name="dimension", value_name="score").rename(
    columns={"id": "take_id"}).to_csv(SQL / "dimension_scores.csv", index=False)

I2 = I.copy()
I2["kind"] = I2["kind"].where(I2["campus"] != "online", "online")
I2["campus"] = I2["campus"].fillna("online")
I2["starts_at"] = I2["start"].fillna(""); I2["ends_at"] = I2["end"].fillna("")
I2 = I2.rename(columns={"item_id": "id"})
for col in ("lat", "lon"):
    if col not in I2: I2[col] = None
I2[["id", "kind", "title", "campus", "venue", "address", "lat", "lon", "starts_at", "ends_at", "cost",
    "social_level", "solo_friendly", "source", "synthetic"]].to_csv(SQL / "kb_items.csv", index=False)
tags = []
for _, r in I.iterrows():
    for d in str(r.dimensions).split("|"):
        if d in D: tags.append((r.item_id, "dimension", d, 1.0, "synthetic" if r.synthetic else "keyword"))
    for c in str(r.causes if isinstance(r.causes, str) else "").split("|"):
        if c: tags.append((r.item_id, "cause", c, 1.0, "keyword"))
pd.DataFrame(tags, columns=["item_id", "tag_type", "tag", "confidence", "tagged_by"]).drop_duplicates(
    ["item_id", "tag_type", "tag"]).to_csv(SQL / "kb_tags.csv", index=False)

L = L.reset_index(drop=True); L["id"] = L.index + 1
L.rename(columns={"focus_dimension": "dimension", "suggested_on": "shown_on"}).assign(
    status=L.committed.map({True: "committed", False: "shown"}))[
    ["id", "student_id", "item_id", "dimension", "shown_on", "status"]].to_csv(SQL / "recommendations.csv", index=False)
CM = L[L.committed].copy().reset_index(drop=True); CM["cid"] = CM.index + 1
CM.assign(status=CM.attended.map({True: "went", False: "missed"}))[
    ["cid", "id", "student_id", "item_id", "friend_joined", "status"]].rename(
    columns={"cid": "id", "id": "recommendation_id", "friend_joined": "with_friend"}).to_csv(SQL / "commitments.csv", index=False)
inv = CM[CM.invited_friend]
pd.DataFrame({"commitment_id": inv.cid, "token": [secrets.token_urlsafe(8) for _ in range(len(inv))],
              "accepted": inv.friend_joined}).to_csv(SQL / "invites.csv", index=False)
CM.assign(helped_1to5=CM.helped_1to5.astype("Int64"))[["cid", "student_id", "attended", "helped_1to5"]].rename(
    columns={"cid": "commitment_id", "attended": "went", "helped_1to5": "helped"}).to_csv(SQL / "feedback.csv", index=False)
pd.DataFrame([{"id": w["win_id"], "campus": w["campus"], "dimension": w["dimension"], "text": w["text"],
               "status": "approved", "same_here": w["same_here"]} for w in W]).to_csv(SQL / "wins.csv", index=False)

load = f"""\\set ON_ERROR_STOP on
\\copy students (id, campus, level, class_year, housing, first_gen, works_20plus_hours, school, home_area, language, synthetic) FROM '{SQL}/students.csv' CSV HEADER
\\copy inventory_takes (id, student_id, take_no, taken_on, source, total) FROM '{SQL}/inventory_takes.csv' CSV HEADER
SELECT setval('inventory_takes_id_seq', (SELECT max(id) FROM inventory_takes));
\\copy dimension_scores FROM '{SQL}/dimension_scores.csv' CSV HEADER
\\copy kb_items (id, kind, title, campus, venue, address, lat, lon, starts_at, ends_at, cost, social_level, solo_friendly, source, synthetic) FROM '{SQL}/kb_items.csv' CSV HEADER NULL ''
\\copy kb_tags FROM '{SQL}/kb_tags.csv' CSV HEADER
\\copy recommendations (id, student_id, item_id, dimension, shown_on, status) FROM '{SQL}/recommendations.csv' CSV HEADER
\\copy commitments (id, recommendation_id, student_id, item_id, with_friend, status) FROM '{SQL}/commitments.csv' CSV HEADER
CREATE TEMP TABLE inv_stage (commitment_id bigint, token text, accepted boolean);
\\copy inv_stage FROM '{SQL}/invites.csv' CSV HEADER
INSERT INTO invites (commitment_id, token, accepted_at) SELECT commitment_id, token, CASE WHEN accepted THEN now() END FROM inv_stage;
\\copy feedback (commitment_id, student_id, went, helped) FROM '{SQL}/feedback.csv' CSV HEADER NULL ''
INSERT INTO arc_credits (commitment_id, status) SELECT commitment_id, 'mock' FROM feedback WHERE went;
\\copy wins (id, campus, dimension, text, status, same_here) FROM '{SQL}/wins.csv' CSV HEADER
"""
for c in C:
    load += (f"INSERT INTO challenges (id, title, scope, dimension, starts_on, ends_on, rule) VALUES "
             f"('{c['challenge_id']}', '{c['title'].replace(chr(39), chr(39)*2)}', '{c['scope']}', "
             f"{repr(c['dimension']) if c.get('dimension') else 'NULL'}, '{c['week_of']}', "
             f"('{c['week_of']}'::date + 6), '{c['rule'].replace(chr(39), chr(39)*2)}');\n")
(SQL / "load.sql").write_text(load)
print("wrote", SQL / "load.sql")
