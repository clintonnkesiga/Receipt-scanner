"""Soft-delete / Trash behaviour for receipts."""


def test_delete_moves_receipt_to_trash(client, make_user, make_receipt, login):
    user = make_user(email="t1@example.com", password="password1")
    receipt = make_receipt(user, merchant="Cafe")
    headers = login("t1@example.com", "password1")

    # Visible in the active list to start.
    assert client.get("/api/receipts", headers=headers).json()["total"] == 1

    # Soft delete -> 204.
    assert client.delete(f"/api/receipts/{receipt.id}", headers=headers).status_code == 204

    # Gone from the active list...
    assert client.get("/api/receipts", headers=headers).json()["total"] == 0

    # ...but present in the Trash, flagged with deleted_at.
    trash = client.get("/api/receipts/trash", headers=headers).json()
    assert trash["total"] == 1
    assert trash["items"][0]["id"] == receipt.id
    assert trash["items"][0]["deleted_at"] is not None


def test_restore_returns_receipt_to_active_list(client, make_user, make_receipt, login):
    user = make_user(email="t2@example.com", password="password1")
    receipt = make_receipt(user)
    headers = login("t2@example.com", "password1")
    client.delete(f"/api/receipts/{receipt.id}", headers=headers)

    restored = client.post(f"/api/receipts/{receipt.id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    assert client.get("/api/receipts", headers=headers).json()["total"] == 1
    assert client.get("/api/receipts/trash", headers=headers).json()["total"] == 0


def test_restore_of_active_receipt_is_conflict(client, make_user, make_receipt, login):
    user = make_user(email="t3@example.com", password="password1")
    receipt = make_receipt(user)
    headers = login("t3@example.com", "password1")
    assert client.post(f"/api/receipts/{receipt.id}/restore", headers=headers).status_code == 409


def test_permanent_delete_requires_trash_first(client, make_user, make_receipt, login):
    user = make_user(email="t4@example.com", password="password1")
    receipt = make_receipt(user)
    headers = login("t4@example.com", "password1")

    # Not trashed yet -> refused.
    assert client.delete(f"/api/receipts/{receipt.id}/permanent", headers=headers).status_code == 409

    # Trash, then purge for good.
    client.delete(f"/api/receipts/{receipt.id}", headers=headers)
    assert client.delete(f"/api/receipts/{receipt.id}/permanent", headers=headers).status_code == 204

    # Fully gone: not in trash, detail 404s.
    assert client.get("/api/receipts/trash", headers=headers).json()["total"] == 0
    assert client.get(f"/api/receipts/{receipt.id}", headers=headers).status_code == 404


def test_trashed_receipts_excluded_from_stats(client, make_user, make_receipt, login):
    user = make_user(email="t5@example.com", password="password1")
    make_receipt(user, total="40.00")
    trashed = make_receipt(user, total="60.00")
    headers = login("t5@example.com", "password1")
    client.delete(f"/api/receipts/{trashed.id}", headers=headers)

    stats = client.get("/api/receipts/stats", headers=headers).json()
    assert stats["receipt_count"] == 1
    assert float(stats["total_spend"]) == 40.0


def test_trashed_receipt_not_editable_but_viewable(client, make_user, make_receipt, login):
    user = make_user(email="t6@example.com", password="password1")
    receipt = make_receipt(user)
    headers = login("t6@example.com", "password1")
    client.delete(f"/api/receipts/{receipt.id}", headers=headers)

    # Editing a trashed receipt 404s (active-only guard)...
    patched = client.patch(f"/api/receipts/{receipt.id}", json={"merchant": "X"}, headers=headers)
    assert patched.status_code == 404

    # ...but the detail GET still works so the detail page can offer "Restore".
    assert client.get(f"/api/receipts/{receipt.id}", headers=headers).status_code == 200
