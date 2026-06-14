def test_login_returns_token_and_me_works(client, make_user):
    make_user(email="alice@example.com", password="hunter2pw")

    resp = client.post(
        "/api/auth/login",
        data={"username": "alice@example.com", "password": "hunter2pw"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_rejects_wrong_password(client, make_user):
    make_user(email="bob@example.com", password="correct-pw")

    resp = client.post(
        "/api/auth/login",
        data={"username": "bob@example.com", "password": "wrong-pw"},
    )
    assert resp.status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/api/auth/me").status_code == 401
