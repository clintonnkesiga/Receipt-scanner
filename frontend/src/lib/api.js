const BASE = "/api/receipts";

export async function scanReceipt(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/scan`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).detail || "Scan failed");
  return res.json();
}

export async function saveReceipt(payload) {
  const res = await fetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Save failed");
  return res.json();
}

export async function listReceipts() {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Could not load receipts");
  return res.json();
}

export async function deleteReceipt(id) {
  const res = await fetch(`${BASE}/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Delete failed");
}
