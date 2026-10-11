"""The judge's example: low sleep -> why? -> coursework -> tutoring. The reason must name the cause, plainly."""


def test_priya_pick_names_the_cause(client):
    t = client.post("/demo/session", json={"persona": "priya", "sandbox": True}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    client.post("/me/focus", json={"dimension": "physical", "barriers": ["coursework"]}, headers=h)
    pick = client.get("/me/next", headers=h).json()["pick"]
    assert pick["item"]["title"] == "Busch Learning Center"
    why = pick["why"].lower()
    assert "coursework" in why and "night" in why
    assert "cutting into your sleep" not in why
