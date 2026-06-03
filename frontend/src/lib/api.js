import { getToken, logout } from "$lib/auth";
import { goto } from "$app/navigation";

const BASE = "/api/receipts";

function authHeaders(extra = {}) {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}

// Centralised fetch: attaches the token and bounces to /login on 401.
async function request(url, options = {}) {
  const res = await fetch(url, { ...options, headers: authHeaders(options.headers) });
  if (res.status === 401) {
    logout();
    goto("/login");
    throw new Error("Session expired — please log in again");
  }
  return res;
}

// --- Auth ---
export async function login(email, password) {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Incorrect email or password");
  return res.json(); // { access_token, token_type }
}

export async function getMe() {
  const res = await request("/api/auth/me");
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

// --- Receipts ---
export async function scanReceipt(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await request(`${BASE}/scan`, { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json()).detail || "Scan failed");
  return res.json();
}

export async function saveReceipt(payload) {
  const res = await request(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Save failed");
  return res.json();
}

export async function listReceipts() {
  const res = await request(BASE);
  if (!res.ok) throw new Error("Could not load receipts");
  return res.json();
}

export async function deleteReceipt(id) {
  const res = await request(`${BASE}/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Delete failed");
}

// Export needs the token in a header, so fetch as a blob and trigger download
// (a plain <a href> can't send the Authorization header).
export async function downloadCsv() {
  const res = await request(`${BASE}/export.csv`);
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "receipts.csv";
  a.click();
  URL.revokeObjectURL(url);
}
