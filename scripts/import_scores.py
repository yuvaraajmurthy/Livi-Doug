"""Import Wellness Inventory results from a CSV export, mapped by config/import_mapping.yaml. Idempotent:
re-importing the same file changes nothing; a take is identified by (student, taken_on). Scores are copied, never computed
by a model; item-level exports are averaged per dimension exactly as configured.

  python -m scripts.import_scores export.csv [--mapping config/import_mapping.yaml] [--dry-run]
"""
import argparse
import csv
import hashlib
import os
from datetime import date, datetime
from pathlib import Path

import yaml

from app.db import connect_direct

DIMS = ["emotional", "environmental", "financial", "intellectual", "occupational", "physical", "social", "spiritual"]


def _date(s: str) -> date:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date: {s!r}")


def _scores(row: dict, m: dict) -> dict[str, float]:
    out = {}
    if m.get("items"):
        lo, hi = m["item_scale"]["min"], m["item_scale"]["max"]
        for d, cols in m["items"].items():
            vals = [float(row[c]) for c in cols if row.get(c) not in (None, "")]
            if vals:
                v = sum(vals) / len(vals)
                out[d] = round(1 + (v - lo) * 3 / (hi - lo), 2) if (lo, hi) != (1, 4) else round(v, 2)
    else:
        for d, col in m["dimensions"].items():
            if row.get(col) not in (None, ""):
                out[d] = round(float(row[col]), 2)
    for d, v in out.items():
        if not 1.0 <= v <= 4.0:
            raise ValueError(f"{d} score {v} outside 1-4")
    return out


def run(path: Path, mapping: Path, dry: bool = False) -> dict:
    m = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    cols = m["columns"]
    salt = os.environ.get("IMPORT_SALT", "")
    stats = {"rows": 0, "new_students": 0, "new_takes": 0, "updated_takes": 0, "skipped": 0}
    with connect_direct() as c, path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            stats["rows"] += 1
            sid = row[cols["student_id"]].strip()
            if m.get("hash_ids"):
                sid = "SW-" + hashlib.sha256((salt + sid).encode()).hexdigest()[:16]
            taken = _date(row[cols["taken_on"]])
            scores = _scores(row, m)
            if len(scores) < 8:
                stats["skipped"] += 1
                continue
            if not c.execute("SELECT 1 FROM students WHERE id = %s", (sid,)).fetchone():
                campus = m["campus_values"].get((row.get(cols.get("campus") or "", "") or "").strip(), "new_brunswick")
                c.execute("INSERT INTO students (id, campus, synthetic) VALUES (%s, %s, false)", (sid, campus))
                stats["new_students"] += 1
            total = round(sum(scores.values()) / 8, 2)
            take = c.execute("SELECT id FROM inventory_takes WHERE student_id = %s AND taken_on = %s", (sid, taken)).fetchone()
            if take:
                tid = take["id"]
                c.execute("UPDATE inventory_takes SET total = %s WHERE id = %s", (total, tid))
                stats["updated_takes"] += 1
            else:
                n = c.execute("SELECT coalesce(max(take_no), 0) + 1 AS n FROM inventory_takes WHERE student_id = %s", (sid,)).fetchone()["n"]
                tid = c.execute("INSERT INTO inventory_takes (student_id, take_no, taken_on, source, total) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                (sid, n, taken, m.get("source", "scarletwell_export"), total)).fetchone()["id"]
                stats["new_takes"] += 1
            for d, v in scores.items():
                c.execute("""INSERT INTO dimension_scores (take_id, dimension, score) VALUES (%s, %s, %s)
                             ON CONFLICT (take_id, dimension) DO UPDATE SET score = EXCLUDED.score""", (tid, d, v))
        if dry:
            c.rollback()
        else:
            c.commit()
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--mapping", default="config/import_mapping.yaml")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(run(Path(a.csv), Path(a.mapping), a.dry_run))
