import {
  getToken,
  logout
} from "$lib/auth";
import {
  goto
} from "$app/navigation";

const BASE = "/api/receipts";

function authHeaders(extra = {}) {
  const t = getToken();
  return t ? {
    ...extra,
    Authorization: `Bearer ${t}`
  } : extra;
}

// Centralised fetch: attaches the token and bounces to /login on 401.
async function request(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers)
  });
  if (res.status === 401) {
    logout();
    goto("/login");
    throw new Error("Session expired — please log in again");
  }
  return res;
}

// --- Auth ---
export async function login(email, password, totp_code = null) {
  const body = new URLSearchParams({ username: email, password });
  if (totp_code) body.set("totp_code", totp_code);
  let res;
  try {
    res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running on :8000?");
  }
  if (res.status === 403) {
    const data = await res.json().catch(() => ({}));
    if (data.detail === "mfa_required") throw new Error("mfa_required");
    throw new Error(data.detail || "Account is disabled");
  }
  if (res.status === 401) throw new Error("Incorrect email or password");
  if (!res.ok) throw new Error(`Login failed (server error ${res.status}). Is the backend running?`);
  return res.json();
}

export async function getMe() {
  const res = await request("/api/auth/me");
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

export async function changePassword(current_password, new_password) {
  const res = await request("/api/auth/change-password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      current_password,
      new_password
    }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(detail || "Could not change password");
  }
}

export async function updateProfile(patch) {
  const res = await request("/api/auth/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update profile");
  }
  return res.json();
}

export async function forgotPassword(email) {
  const res = await fetch("/api/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
}

export async function resetPassword(token, new_password) {
  const res = await fetch("/api/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Reset failed");
  }
}

export async function sendVerification() {
  const res = await request("/api/auth/send-verification", { method: "POST" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not send verification");
  }
}

export async function verifyEmail(token) {
  const params = new URLSearchParams({ token });
  const res = await fetch(`/api/auth/verify-email?${params}`, { method: "POST" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Verification failed");
  }
}

// --- 2FA ---
export async function get2FASetup() {
  const res = await request("/api/2fa/setup");
  if (!res.ok) throw new Error("Could not start 2FA setup");
  return res.json();
}

export async function enable2FA(code) {
  const res = await request("/api/2fa/enable", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not enable 2FA");
  }
}

export async function disable2FA(code) {
  const res = await request("/api/2fa/disable", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not disable 2FA");
  }
}

// --- Audit log ---
export async function listAuditLog({ limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const res = await request(`/api/audit?${params}`);
  if (!res.ok) throw new Error("Could not load audit log");
  return res.json();
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
    headers: {
      "Content-Type": "application/json"
    },
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
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update user");
  }
  return res.json();
}

export async function deleteUser(id) {
  const res = await request(`/api/users/${id}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not delete user");
  }
}

export async function resetUserPassword(id, new_password) {
  const res = await request(`/api/users/${id}/reset-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      new_password
    }),
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
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      name
    }),
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
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      name
    }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update category");
  }
  return res.json();
}

export async function deleteCategory(id) {
  const res = await request(`/api/categories/${id}`, {
    method: "DELETE"
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not delete category");
  }
}

// --- Receipts ---
// Uses XHR (not fetch) so we can report upload progress. `onProgress` receives
// a fraction 0..1 while the file uploads; once it hits 1 the server is doing
// OCR, for which there's no progress event (caller shows an indeterminate bar).
export function scanReceipt(file, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/scan`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status === 401) {
        logout();
        goto("/login");
        reject(new Error("Session expired — please log in again"));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Scan failed"));
        }
        return;
      }
      let detail = "Scan failed";
      try {
        detail = JSON.parse(xhr.responseText).detail || detail;
      } catch {
        /* non-JSON error body */
      }
      reject(new Error(detail));
    };
    xhr.onerror = () =>
      reject(new Error("Cannot reach the server. Is the backend running?"));
    xhr.send(form);
  });
}

export async function saveReceipt(payload) {
  const res = await request(BASE, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
  });
  if (res.status === 409) {
    // Duplicate guard tripped — surface a clear message (caller can re-send
    // with force: true to override).
    const detail = (await res.json().catch(() => ({}))).detail;
    const msg = detail && typeof detail === "object" ? detail.message : detail;
    throw new Error(msg || "This looks like a duplicate receipt.");
  }
  if (!res.ok) throw new Error("Save failed");
  return res.json();
}

// Server-side paged list. Returns { items, total, total_sum, normalized_sum, limit, offset }.
export async function listReceipts({
  q = "",
  category = "",
  sort = "date_desc",
  limit = 20,
  offset = 0,
  date_from = "",
  date_to = "",
  amount_min = "",
  amount_max = "",
} = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  if (sort) params.set("sort", sort);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (date_from) params.set("date_from", date_from);
  if (date_to) params.set("date_to", date_to);
  if (amount_min !== "") params.set("amount_min", String(amount_min));
  if (amount_max !== "") params.set("amount_max", String(amount_max));
  const res = await request(`${BASE}?${params}`);
  if (!res.ok) throw new Error("Could not load receipts");
  return res.json();
}

export async function getStats() {
  const res = await request(`${BASE}/stats`);
  if (!res.ok) throw new Error("Could not load stats");
  return res.json();
}

// Single receipt by id (for the deep-linkable detail page).
export async function getReceipt(id) {
  const res = await request(`${BASE}/${id}`);
  if (res.status === 404) throw new Error("Receipt not found");
  if (!res.ok) throw new Error("Could not load receipt");
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

// Soft-delete: moves the receipt to the Trash (recoverable via restoreReceipt).
export async function deleteReceipt(id) {
  const res = await request(`${BASE}/${id}`, {
    method: "DELETE"
  });
  if (!res.ok) throw new Error("Delete failed");
}

// --- Trash (soft-deleted receipts) ---
export async function listTrash({ limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const res = await request(`${BASE}/trash?${params}`);
  if (!res.ok) throw new Error("Could not load trash");
  return res.json();
}

export async function restoreReceipt(id) {
  const res = await request(`${BASE}/${id}/restore`, { method: "POST" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not restore receipt");
  }
  return res.json();
}

export async function permanentlyDeleteReceipt(id) {
  const res = await request(`${BASE}/${id}/permanent`, { method: "DELETE" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not delete receipt");
  }
}

export async function updateReceipt(id, patch) {
  const res = await request(`${BASE}/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update receipt");
  }
  return res.json();
}

// --- Budgets ---
export async function listBudgets() {
  const res = await request("/api/budgets");
  if (!res.ok) throw new Error("Could not load budgets");
  return res.json();
}

export async function createBudget(payload) {
  const res = await request("/api/budgets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not create budget");
  }
  return res.json();
}

export async function updateBudget(id, patch) {
  const res = await request(`/api/budgets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not update budget");
  }
  return res.json();
}

export async function deleteBudget(id) {
  const res = await request(`/api/budgets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Could not delete budget");
}

export async function getBudgetUsage(month = null) {
  const url = month ? `/api/budgets/usage?month=${month}` : "/api/budgets/usage";
  const res = await request(url);
  if (!res.ok) throw new Error("Could not load budget usage");
  return res.json();
}

export async function rescanReceipt(id) {
  const res = await request(`${BASE}/${id}/rescan`, { method: "POST" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Rescan failed");
  }
  return res.json();
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

// --- Reports / analytics ---
function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== "" && v != null) p.set(k, v);
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function getTimeSeries({ granularity = "month", date_from = "", date_to = "" } = {}) {
  const res = await request(`/api/reports/timeseries${qs({ granularity, date_from, date_to })}`);
  if (!res.ok) throw new Error("Could not load time series");
  return res.json();
}

export async function getRecurring() {
  const res = await request("/api/reports/recurring");
  if (!res.ok) throw new Error("Could not load recurring expenses");
  return res.json();
}

export async function getDigestPreview() {
  const res = await request("/api/reports/digest/preview");
  if (!res.ok) throw new Error("Could not load digest preview");
  return res.json();
}

export async function sendDigest() {
  const res = await request("/api/reports/digest/send", { method: "POST" });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : "Could not send digest");
  }
}

// Download an export (xlsx | pdf), honoring an optional date range.
export async function downloadExport(format, { date_from = "", date_to = "" } = {}) {
  const res = await request(`/api/reports/export.${format}${qs({ date_from, date_to })}`);
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `receipts.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}