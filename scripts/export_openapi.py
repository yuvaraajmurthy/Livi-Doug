"""Write contract/openapi.json from the app. Run after any contract change."""
import json
from pathlib import Path

from app.main import create_app

out = Path(__file__).resolve().parent.parent / "contract" / "openapi.json"
out.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
print("wrote", out)
