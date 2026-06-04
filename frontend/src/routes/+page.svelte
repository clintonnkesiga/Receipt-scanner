<script>
  import { onMount } from "svelte";
  import {
    scanReceipt,
    saveReceipt,
    listReceipts,
    listCategories,
    deleteReceipt,
    downloadCsv,
    getReceiptImageUrl,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";

  let categories = $state([]); // managed category names, from the API
  let filter = $state(""); // active category filter on the history list ("" = all)

  let receipts = $state([]);
  let scan = $state(null); // { image_path, raw_ocr_text, parsed }
  let busy = $state(false);
  let error = $state("");

  // Options for the review dropdown — include the parsed value even if it's not
  // (or no longer) in the managed list, so an auto-categorised receipt shows it.
  const reviewOptions = $derived(
    scan?.parsed?.category && !categories.includes(scan.parsed.category)
      ? [scan.parsed.category, ...categories]
      : categories,
  );

  // Local preview of the file being reviewed (object URL of the uploaded File).
  let previewUrl = $state(null);
  let previewIsPdf = $state(false);
  // Full-size viewer (modal) for saved receipts.
  let viewerUrl = $state(null);
  let viewerIsPdf = $state(false);
  let viewerLoading = $state(false);

  const isPdfPath = (path) => !!path && path.toLowerCase().endsWith(".pdf");

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    previewIsPdf = false;
  }

  async function openImage(receipt) {
    viewerIsPdf = isPdfPath(receipt.image_path);
    viewerLoading = true;
    try {
      viewerUrl = await getReceiptImageUrl(receipt.id);
    } catch (err) {
      error = err.message;
    } finally {
      viewerLoading = false;
    }
  }

  function closeViewer() {
    if (viewerUrl) URL.revokeObjectURL(viewerUrl);
    viewerUrl = null;
  }

  function discardScan() {
    scan = null;
    clearPreview();
  }

  const total = $derived(
    receipts.reduce((sum, r) => sum + (Number(r.total) || 0), 0),
  );

  // Admins/super-admins see everyone's receipts, so show whose each one is.
  const isElevated = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  async function refresh() {
    try {
      receipts = await listReceipts(filter);
    } catch (e) {
      error = e.message;
    }
  }

  async function setFilter(value) {
    filter = value;
    await refresh();
  }

  onMount(async () => {
    try {
      categories = (await listCategories()).map((c) => c.name);
    } catch (e) {
      error = e.message;
    }
    await refresh();
  });

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
      clearPreview();
      previewUrl = URL.createObjectURL(file);
      previewIsPdf = file.type === "application/pdf";
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
      discardScan();
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

<div class="max-w-4xl mx-auto px-4 py-8 space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-semibold">Receipts</h1>
    <button
      onclick={onExport}
      class="text-sm text-blue-600 hover:underline"
      disabled={receipts.length === 0}
    >
      Export CSV
    </button>
  </div>

  {#if error}
    <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
      {error}
    </div>
  {/if}

  <!-- Upload -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <label class="block">
      <span class="text-sm font-medium">Upload a receipt photo or PDF</span>
      <input
        type="file"
        accept="image/*,application/pdf"
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
      {#if previewUrl}
        {#if previewIsPdf}
          <embed
            src={previewUrl}
            type="application/pdf"
            class="w-full h-96 rounded-lg border border-slate-200"
          />
        {:else}
          <img
            src={previewUrl}
            alt="Uploaded receipt"
            class="max-h-72 rounded-lg border border-slate-200 mx-auto"
          />
        {/if}
      {/if}
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
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2 capitalize"
          >
            {#each reviewOptions as c}
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
          onclick={discardScan}
          class="px-4 py-2 rounded-lg border hover:bg-slate-50"
        >
          Discard
        </button>
      </div>
    </section>
  {/if}

  <!-- History -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
      <h2 class="font-semibold">History ({receipts.length})</h2>
      <div class="flex items-center gap-3">
        <label class="text-sm text-slate-500 flex items-center gap-2">
          Category
          <select
            value={filter}
            onchange={(e) => setFilter(e.currentTarget.value)}
            class="rounded-lg border border-slate-300 p-1.5 text-sm capitalize"
          >
            <option value="">All</option>
            {#each categories as c}
              <option value={c}>{c}</option>
            {/each}
          </select>
        </label>
        {#if receipts.length}
          <span class="text-sm text-slate-500">
            Total: {total.toLocaleString()}
          </span>
        {/if}
      </div>
    </div>
    {#if receipts.length === 0}
      <p class="text-sm text-slate-500">
        {filter ? `No receipts in “${filter}”.` : "No receipts yet — upload one above."}
      </p>
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
              <td class="text-right space-x-3 whitespace-nowrap">
                {#if r.image_path}
                  <button
                    onclick={() => openImage(r)}
                    class="text-blue-600 hover:underline text-xs"
                  >
                    view
                  </button>
                {/if}
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
</div>

<svelte:window onkeydown={(e) => e.key === "Escape" && closeViewer()} />

<!-- Full-size image viewer -->
{#if viewerUrl || viewerLoading}
  <div
    role="presentation"
    class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    onclick={closeViewer}
  >
    {#if viewerLoading}
      <div class="text-white text-sm animate-pulse">Loading…</div>
    {:else if viewerIsPdf}
      <iframe
        src={viewerUrl}
        title="Receipt PDF"
        class="w-[90vw] h-[90vh] rounded-lg shadow-2xl bg-white"
        onclick={(e) => e.stopPropagation()}
      ></iframe>
    {:else}
      <img
        src={viewerUrl}
        alt="Receipt"
        class="max-h-[90vh] max-w-full rounded-lg shadow-2xl"
        onclick={(e) => e.stopPropagation()}
      />
    {/if}
  </div>
{/if}
