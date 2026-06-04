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
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import ReceiptThumb from "$lib/components/ReceiptThumb.svelte";

  let categories = $state([]); // managed category names, from the API
  let filter = $state(""); // active category filter on the history list ("" = all)
  let view = $state("table"); // "table" | "gallery"

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
  let viewerIndex = $state(-1); // index into orderedReceipts; -1 = closed

  const isPdfPath = (path) => !!path && path.toLowerCase().endsWith(".pdf");

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    previewIsPdf = false;
  }

  // Load the receipt at `index` in the displayed order into the viewer.
  // A token guards against out-of-order responses when stepping quickly.
  let viewerToken = 0;
  async function openAt(index) {
    if (index < 0 || index >= orderedReceipts.length) return;
    const receipt = orderedReceipts[index];
    const token = ++viewerToken;
    viewerIndex = index;
    viewerIsPdf = isPdfPath(receipt.image_path);
    if (viewerUrl) {
      URL.revokeObjectURL(viewerUrl);
      viewerUrl = null;
    }
    viewerLoading = true;
    try {
      const url = await getReceiptImageUrl(receipt.id);
      if (token !== viewerToken) {
        URL.revokeObjectURL(url); // a newer navigation superseded this load
        return;
      }
      viewerUrl = url;
    } catch (err) {
      if (token === viewerToken) error = err.message;
    } finally {
      if (token === viewerToken) viewerLoading = false;
    }
  }

  function openImage(receipt) {
    openAt(orderedReceipts.indexOf(receipt));
  }

  const canPrev = $derived(viewerIndex > 0);
  const canNext = $derived(
    viewerIndex >= 0 && viewerIndex < orderedReceipts.length - 1,
  );
  const viewerReceipt = $derived(
    viewerIndex >= 0 ? orderedReceipts[viewerIndex] : null,
  );

  function prevReceipt() {
    if (canPrev) openAt(viewerIndex - 1);
  }
  function nextReceipt() {
    if (canNext) openAt(viewerIndex + 1);
  }

  function onViewerKey(e) {
    if (viewerIndex < 0 && !viewerLoading) return;
    if (e.key === "Escape") closeViewer();
    else if (e.key === "ArrowLeft") prevReceipt();
    else if (e.key === "ArrowRight") nextReceipt();
  }

  function closeViewer() {
    viewerToken++; // invalidate any in-flight load
    if (viewerUrl) URL.revokeObjectURL(viewerUrl);
    viewerUrl = null;
    viewerIndex = -1;
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

  // Gallery view groups receipts by category, sorted by name; "uncategorized" last.
  const grouped = $derived.by(() => {
    const map = new Map();
    for (const r of receipts) {
      const key = r.category || "uncategorized";
      (map.get(key) ?? map.set(key, []).get(key)).push(r);
    }
    return [...map.entries()].sort(([a], [b]) => {
      if (a === "uncategorized") return 1;
      if (b === "uncategorized") return -1;
      return a.localeCompare(b);
    });
  });

  // The order the viewer steps through: grouped order in gallery, list order
  // in the table — so prev/next matches what the user sees on screen.
  const orderedReceipts = $derived(
    view === "gallery" ? grouped.flatMap(([, items]) => items) : receipts,
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

  // Receipt pending deletion (drives the confirmation dialog); null = closed.
  let pendingDelete = $state(null);
  let deleting = $state(false);

  async function confirmDelete() {
    if (!pendingDelete) return;
    deleting = true;
    try {
      await deleteReceipt(pendingDelete.id);
      pendingDelete = null;
      await refresh();
    } catch (err) {
      error = err.message;
    } finally {
      deleting = false;
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

<div class="w-full px-6 py-8 space-y-6">
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
        <!-- Table / Gallery view toggle -->
        <div class="inline-flex rounded-lg border border-slate-300 overflow-hidden text-sm">
          <button
            type="button"
            onclick={() => (view = "table")}
            class="px-3 py-1.5 {view === 'table' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'}"
          >
            Table
          </button>
          <button
            type="button"
            onclick={() => (view = "gallery")}
            class="px-3 py-1.5 border-l border-slate-300 {view === 'gallery' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'}"
          >
            Gallery
          </button>
        </div>
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
    {:else if view === "gallery"}
      <div class="space-y-8">
        {#each grouped as [cat, items] (cat)}
          <div>
            <div class="flex items-center gap-2 mb-3">
              <span class="text-xs rounded-full px-2 py-0.5 capitalize {badgeClass(cat)}">{cat}</span>
              <span class="text-xs text-slate-400">{items.length}</span>
            </div>
            <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
              {#each items as r (r.id)}
                <ReceiptThumb receipt={r} onopen={openImage} showOwner={isElevated} />
              {/each}
            </div>
          </div>
        {/each}
      </div>
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
                  onclick={() => (pendingDelete = r)}
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

<svelte:window onkeydown={onViewerKey} />

<!-- Full-size image viewer -->
{#if viewerUrl || viewerLoading}
  <div
    role="presentation"
    class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    onclick={closeViewer}
  >
    <!-- Caption: position + merchant -->
    {#if viewerReceipt}
      <div class="absolute top-4 left-1/2 -translate-x-1/2 text-white/90 text-sm flex items-center gap-2">
        <span class="tabular-nums">{viewerIndex + 1} / {orderedReceipts.length}</span>
        {#if viewerReceipt.merchant}
          <span class="text-white/50">·</span>
          <span class="truncate max-w-[40vw]">{viewerReceipt.merchant}</span>
        {/if}
      </div>
    {/if}

    <!-- Previous -->
    {#if canPrev}
      <button
        type="button"
        aria-label="Previous receipt"
        onclick={(e) => { e.stopPropagation(); prevReceipt(); }}
        class="absolute left-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full
               bg-white/10 hover:bg-white/25 text-white text-3xl leading-none flex items-center justify-center transition"
      >
        ‹
      </button>
    {/if}

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
        class="max-h-[90vh] max-w-[80vw] rounded-lg shadow-2xl"
        onclick={(e) => e.stopPropagation()}
      />
    {/if}

    <!-- Next -->
    {#if canNext}
      <button
        type="button"
        aria-label="Next receipt"
        onclick={(e) => { e.stopPropagation(); nextReceipt(); }}
        class="absolute right-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full
               bg-white/10 hover:bg-white/25 text-white text-3xl leading-none flex items-center justify-center transition"
      >
        ›
      </button>
    {/if}
  </div>
{/if}

<!-- Delete confirmation -->
<ConfirmDialog
  open={pendingDelete != null}
  danger
  busy={deleting}
  title="Delete this receipt?"
  message={pendingDelete
    ? `“${pendingDelete.merchant || "Untitled"}” will be permanently removed. This can’t be undone.`
    : ""}
  confirmLabel={deleting ? "Deleting…" : "Delete"}
  onconfirm={confirmDelete}
  oncancel={() => (pendingDelete = null)}
/>
