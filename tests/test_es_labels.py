"""Sofia reads Spanish: the window label and the filter checks must be Spanish too, not only the sentence."""
from app.services.present import localize_window, localize_filter


def test_window_labels_in_spanish():
    assert localize_window("Fits your Wednesday gap, 7–9:30", "es") == "Cabe en tu hueco del miércoles, 7–9:30"
    assert localize_window("Mostly inside your Tuesday gap, 12:20–2:30", "es") == "Casi todo dentro de tu hueco del martes, 12:20–2:30"
    assert localize_window("Open during your Monday gap, 6–10:30", "es") == "Abierto durante tu hueco del lunes, 6–10:30"
    assert localize_window("Any time, online", "es") == "Cuando quieras, en línea"
    assert localize_window("Fits your Wednesday gap, 7–9:30", "en") == "Fits your Wednesday gap, 7–9:30"
    assert localize_window(None, "es") is None


def test_filter_checks_in_spanish():
    assert localize_filter("free", "Free", "es") == "Gratis"
    assert localize_filter("in_window", "Inside one of your free windows", "es") == "Dentro de uno de tus horarios libres"
    assert localize_filter("campus", "On your campus", "en") == "On your campus"


def test_sofia_sees_spanish_labels(client):
    t = client.post("/demo/session", json={"persona": "sofia", "sandbox": True}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    client.post("/me/focus", json={"dimension": "financial", "barriers": ["money"]}, headers=h)
    pick = client.get("/me/next", headers=h).json()["pick"]
    if pick["window_label"]:
        assert not pick["window_label"].startswith(("Fits", "Mostly", "Open", "Any"))
    assert all(f["text"] not in ("Free", "Online", "On your campus") for f in pick["reasons"]["filters"])
