<script>
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import {
    scanReceipt,
    saveReceipt,
    listReceipts,
    deleteReceipt,
    downloadCsv,
    getMe,
  } from "$lib/api";
  import { getToken, logout } from "$lib/auth";

  const CATEGORIES = ["grocery", "fuel", "other"];

  let user = $state(null);
  let ready = $state(false);
  let receipts = $state([]);
  let scan = $state(null); // { image_path, raw_ocr_text, parsed }
  let busy = $state(false);
  let error = $state("");

  const total = $derived(
    receipts.reduce((sum, r) => sum + (Number(r.total) || 0), 0),
  );

  // Admins/super-admins see everyone's receipts, so show whose each one is.
  const isElevated = $derived(
    user?.role === "admin" || user?.role === "superadmin",
  );

  async function refresh() {
    try {
      receipts = await listReceipts();
    } catch (e) {
      error = e.message;
    }
  }

  // Route guard: no token or invalid session -> bounce to /login.
  onMount(async () => {
    if (!getToken()) {
      goto("/login");
      return;
    }
    try {
      user = await getMe();
      ready = true;
      await refresh();
    } catch {
      goto("/login");
    }
  });

  function onLogout() {
    logout();
    goto("/login");
  }

  async function onExport() {
    try {
      await downloadCsv();
    } catch (err) {
      error = err.message;
    }
  }

  async function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    busy = true;
    error = "";
    try {
      scan = await scanReceipt(file);
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
      e.target.value = "";
    }
  }

  async function onSave() {
    busy = true;
    error = "";
    try {
      await saveReceipt(scan.parsed);
      scan = null;
      await refresh();
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }

  async function onDelete(id) {
    if (!confirm("Delete this receipt?")) return;
    try {
      await deleteReceipt(id);
      await refresh();
    } catch (err) {
      error = err.message;
    }
  }

  function badgeClass(category) {
    return category === "fuel"
      ? "bg-amber-100 text-amber-800"
      : category === "grocery"
        ? "bg-emerald-100 text-emerald-800"
        : "bg-slate-100 text-slate-700";
  }
</script>

{#if !ready}
  <div class="min-h-screen flex items-center justify-center text-slate-400 text-sm">
    Loading…
  </div>
{:else}
<div class="min-h-screen bg-slate-50 text-slate-800">
  <header class="bg-white border-b sticky top-0 z-10">
    <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
      <h1 class="text-xl font-semibold flex items-center gap-2">
        <span>🧾</span> Receipt Scanner
      </h1>
      <div class="flex items-center gap-4 text-sm">
        <a href="/dashboard" class="text-slate-600 hover:underline">Dashboard</a>
        <button onclick={onExport} class="text-blue-600 hover:underline">
          Export CSV
        </button>
        {#if user?.role === "superadmin"}
          <a href="/users" class="text-slate-600 hover:underline">Users</a>
        {/if}
        <a href="/account" class="text-slate-600 hover:underline">Account</a>
        <span class="text-slate-400">|</span>
        <span class="text-slate-600 hidden sm:inline" title={user?.role}>
          {user?.email}
        </span>
        <button onclick={onLogout} class="text-slate-500 hover:text-red-600">
          Logout
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-4xl mx-auto px-4 py-6 space-y-6">
    {#if error}
      <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
        {error}
      </div>
    {/if}

    <!-- Upload -->
    <section class="bg-white rounded-xl shadow-sm p-5">
      <label class="block">
        <span class="text-sm font-medium">Upload a receipt photo</span>
        <input
          type="file"
          accept="image/*"
          onchange={onUpload}
          disabled={busy}
          class="mt-2 block w-full text-sm file:mr-4 file:rounded-lg file:border-0
                 file:bg-blue-600 file:px-4 file:py-2 file:text-white
                 hover:file:bg-blue-700 file:cursor-pointer disabled:opacity-50"
        />
      </label>
      {#if busy && !scan}
        <p class="mt-3 text-sm text-slate-500 animate-pulse">Scanning…</p>
      {/if}
    </section>

    <!-- Review parsed result -->
    {#if scan}
      <section class="bg-white rounded-xl shadow-sm p-5 space-y-4">
        <h2 class="font-semibold">Review &amp; correct</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label class="text-sm">
            <span class="font-medium">Merchant</span>
            <input
              bind:value={scan.parsed.merchant}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Date</span>
            <input
              type="date"
              bind:value={scan.parsed.purchase_date}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Total</span>
            <input
              bind:value={scan.parsed.total}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Currency</span>
            <input
              bind:value={scan.parsed.currency}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Category</span>
            <select
              bind:value={scan.parsed.category}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            >
              {#each CATEGORIES as c}
                <option value={c}>{c}</option>
              {/each}
            </select>
          </label>
        </div>

        {#if scan.parsed.line_items?.length}
          <details class="text-sm">
            <summary class="cursor-pointer font-medium">
              {scan.parsed.line_items.length} line items
            </summary>
            <ul class="mt-2 space-y-1">
              {#each scan.parsed.line_items as li}
                <li class="flex justify-between border-b py-1">
                  <span>{li.description}</span>
                  <span>{li.amount}</span>
                </li>
              {/each}
            </ul>
          </details>
        {/if}

        <details class="text-sm">
          <summary class="cursor-pointer text-slate-500">Raw OCR text</summary>
          <pre class="mt-2 whitespace-pre-wrap bg-slate-50 p-3 rounded-lg text-xs">{scan.raw_ocr_text}</pre>
        </details>

        <div class="flex gap-3">
          <button
            onclick={onSave}
            disabled={busy}
            class="bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
          >
            Save receipt
          </button>
          <button
            onclick={() => (scan = null)}
            class="px-4 py-2 rounded-lg border hover:bg-slate-50"
          >
            Discard
          </button>
        </div>
      </section>
    {/if}

    <!-- History -->
    <section class="bg-white rounded-xl shadow-sm p-5">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-semibold">History ({receipts.length})</h2>
        {#if receipts.length}
          <span class="text-sm text-slate-500">
            Total: {total.toLocaleString()}
          </span>
        {/if}
      </div>
      {#if receipts.length === 0}
        <p class="text-sm text-slate-500">No receipts yet — upload one above.</p>
      {:else}
        <table class="w-full text-sm">
          <thead class="text-left text-slate-500 border-b">
            <tr>
              <th class="py-2">Merchant</th>
              {#if isElevated}<th>Owner</th>{/if}
              <th>Date</th>
              <th>Category</th>
              <th class="text-right">Total</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each receipts as r (r.id)}
              <tr class="border-b last:border-0 hover:bg-slate-50">
                <td class="py-2">{r.merchant || "—"}</td>
                {#if isElevated}
                  <td class="text-slate-500">{r.owner_email || "—"}</td>
                {/if}
                <td>{r.purchase_date || "—"}</td>
                <td>
                  <span class="text-xs rounded-full px-2 py-0.5 {badgeClass(r.category)}">
                    {r.category}
                  </span>
                </td>
                <td class="text-right tabular-nums">
                  {r.total != null ? `${r.currency || ""} ${Number(r.total).toLocaleString()}` : "—"}
                </td>
                <td class="text-right">
                  <button
                    onclick={() => onDelete(r.id)}
                    class="text-red-600 hover:underline text-xs"
                  >
                    delete
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>
  </main>
</div>
{/if}
