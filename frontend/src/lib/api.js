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
  let res;
  try {
    res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  } catch {
    // Network/proxy failure — backend almost certainly isn't running.
    throw new Error("Cannot reach the server. Is the backend running on :8000?");
  }
  if (res.status === 401) throw new Error("Incorrect email or password");
  if (!res.ok) {
    throw new Error(`Login failed (server error ${res.status}). Is the backend running?`);
  }
  return res.json(); // { access_token, token_type }
}

export async function getMe() {
  const res = await request("/api/auth/me");
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export async function changePassword(current_password, new_password) {
  const res = await request("/api/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(detail || "Could not change password");
  }
}

// --- User management (super-admin) ---
export async function listUsers() {
  const res = await request("/api/users");
  if (!res.ok) throw new Error("Could not load users");
  return res.json();
}

export async function createUser(payload) {
  const res = await request("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not create user");
  }
  return res.json();
}

export async function updateUser(id, patch) {
  const res = await request(`/api/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update user");
  }
  return res.json();
}

export async function deleteUser(id) {
  const res = await request(`/api/users/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not delete user");
  }
}

export async function resetUserPassword(id, new_password) {
  const res = await request(`/api/users/${id}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_password }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not reset password");
  }
}

// --- Categories ---
export async function listCategories() {
  const res = await request("/api/categories");
  if (!res.ok) throw new Error("Could not load categories");
  return res.json();
}

export async function createCategory(name) {
  const res = await request("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not create category");
  }
  return res.json();
}

export async function updateCategory(id, name) {
  const res = await request(`/api/categories/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update category");
  }
  return res.json();
}

export async function deleteCategory(id) {
  const res = await request(`/api/categories/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not delete category");
  }
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

export async function listReceipts(category) {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  const res = await request(`${BASE}${qs}`);
  if (!res.ok) throw new Error("Could not load receipts");
  return res.json();
}

export async function getStats() {
  const res = await request(`${BASE}/stats`);
  if (!res.ok) throw new Error("Could not load stats");
  return res.json();
}

// Fetch a receipt's image (auth-protected) and return an object URL.
// Caller is responsible for URL.revokeObjectURL when done.
export async function getReceiptImageUrl(id) {
  const res = await request(`${BASE}/${id}/image`);
  if (!res.ok) throw new Error("Could not load image");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
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
