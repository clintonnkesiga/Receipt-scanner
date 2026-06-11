def test_default_categories_are_seeded(client, make_user, login):
    make_user(email="cat@example.com", password="password1")
    headers = login("cat@example.com", "password1")

    resp = client.get("/api/categories", headers=headers)
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()}
    assert {"grocery", "fuel", "other"} <= names


def test_create_then_delete_own_category(client, make_user, login):
    make_user(email="cat2@example.com", password="password1")
    headers = login("cat2@example.com", "password1")

    created = client.post("/api/categories", json={"name": "coffee"}, headers=headers)
    assert created.status_code == 201, created.text
    category_id = created.json()["id"]

    duplicate = client.post("/api/categories", json={"name": "coffee"}, headers=headers)
    assert duplicate.status_code == 409

    deleted = client.delete(f"/api/categories/{category_id}", headers=headers)
    assert deleted.status_code == 204


def test_users_cannot_see_each_others_categories(client, make_user, login):
    make_user(email="owner@example.com", password="password1")
    owner_headers = login("owner@example.com", "password1")
    made = client.post("/api/categories", json={"name": "secret"}, headers=owner_headers)
    assert made.status_code == 201

    make_user(email="intruder@example.com", password="password1")
    intruder_headers = login("intruder@example.com", "password1")
    visible = {c["name"] for c in client.get("/api/categories", headers=intruder_headers).json()}
    assert "secret" not in visible
