<script>
  import { onMount } from "svelte";
  import {
    scanReceipt,
    saveReceipt,
    listReceipts,
    listCategories,
    deleteReceipt,
    updateReceipt,
    downloadCsv,
    getReceiptImageUrl,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import ReceiptThumb from "$lib/components/ReceiptThumb.svelte";

  let categories = $state([]); // managed category names, from the API
  let view = $state("gallery"); // "table" | "gallery"

  // Filters (all applied client-side over the full loaded list).
  let filter = $state(""); // category filter ("" = all)
  let search = $state(""); // free-text match on merchant
  let sort = $state("date_desc"); // date_desc | date_asc | total_desc | total_asc

  // Pagination.
  const PAGE_SIZE = 12;
  let page = $state(1);

  let receipts = $state([]); // full list from the API
  let scan = $state(null); // { image_path, raw_ocr_text, parsed }
  let busy = $state(false);

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
      if (token === viewerToken)
        toasts.error(
          err instanceof Error ? err.message : "Could not load image",
        );
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

  // Admins/super-admins see everyone's receipts, so show whose each one is.
  const isElevated = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  // --- Filter → sort → paginate (all client-side over the full list) ---
  const filtered = $derived.by(() => {
    const q = search.trim().toLowerCase();
    let list = receipts.filter(
      (r) =>
        (!filter || r.category === filter) &&
        (!q || (r.merchant || "").toLowerCase().includes(q)),
    );
    const num = (r) => Number(r.total) || 0;
    const day = (r) => r.purchase_date || ""; // ISO dates sort lexicographically
    const cmp = {
      date_desc: (a, b) => day(b).localeCompare(day(a)),
      date_asc: (a, b) => day(a).localeCompare(day(b)),
      total_desc: (a, b) => num(b) - num(a),
      total_asc: (a, b) => num(a) - num(b),
    }[sort];
    return [...list].sort(cmp);
  });

  const total = $derived(
    filtered.reduce((sum, r) => sum + (Number(r.total) || 0), 0),
  );

  const pageCount = $derived(
    Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)),
  );

  // Keep the page in range as the result set shrinks (filtering, deletes).
  $effect(() => {
    if (page > pageCount) page = pageCount;
  });

  const paged = $derived(
    filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
  );

  // Windowed page list: numbers + null (= ellipsis gap) for the pagination bar.
  // Always shows page 1, last page, current ±1, with "…" for any gaps.
  const pageWindowed = $derived.by(() => {
    if (pageCount <= 7)
      return Array.from({ length: pageCount }, (_, i) => i + 1);
    const keep = new Set(
      [1, pageCount, page - 1, page, page + 1].filter(
        (p) => p >= 1 && p <= pageCount,
      ),
    );
    const sorted = [...keep].sort((a, b) => a - b);
    /** @type {(number|null)[]} */
    const result = [];
    for (let i = 0; i < sorted.length; i++) {
      if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push(null); // ellipsis
      result.push(sorted[i]);
    }
    return result;
  });

  // Gallery groups the current page by category, sorted by name; "uncategorized" last.
  const grouped = $derived.by(() => {
    const map = new Map();
    for (const r of paged) {
      const key = r.category || "uncategorized";
      (map.get(key) ?? map.set(key, []).get(key)).push(r);
    }
    return [...map.entries()].sort(([a], [b]) => {
      if (a === "uncategorized") return 1;
      if (b === "uncategorized") return -1;
      return a.localeCompare(b);
    });
  });

  // The order the viewer steps through — matches what's shown on the current page.
  const orderedReceipts = $derived(
    view === "gallery" ? grouped.flatMap(([, items]) => items) : paged,
  );

  // Inclusive 1-based range of the current page, e.g. "1–12 of 37".
  const rangeStart = $derived(filtered.length ? (page - 1) * PAGE_SIZE + 1 : 0);
  const rangeEnd = $derived(Math.min(page * PAGE_SIZE, filtered.length));

  async function refresh() {
    try {
      receipts = await listReceipts();
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load receipts");
    }
  }

  function resetPage() {
    page = 1;
  }

  onMount(async () => {
    try {
      categories = (await listCategories()).map((c) => c.name);
    } catch (e) {
      toasts.error(
        e instanceof Error ? e.message : "Could not load categories",
      );
    }
    await refresh();
  });

  async function onExport() {
    try {
      await downloadCsv();
      toasts.success("Receipts exported to CSV");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Export failed");
    }
  }

  // Upload progress: "uploading" tracks real bytes; "processing" is the
  // indeterminate OCR phase (no server-side progress events).
  let uploadPhase = $state("idle"); // "idle" | "uploading" | "processing"
  let uploadPct = $state(0);

  async function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    busy = true;
    uploadPhase = "uploading";
    uploadPct = 0;
    try {
      scan = await scanReceipt(file, (frac) => {
        uploadPct = Math.round(frac * 100);
        if (frac >= 1) uploadPhase = "processing";
      });
      clearPreview();
      previewUrl = URL.createObjectURL(file);
      previewIsPdf = file.type === "application/pdf";
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Scan failed");
    } finally {
      busy = false;
      uploadPhase = "idle";
      uploadPct = 0;
      e.target.value = "";
    }
  }

  async function onSave() {
    busy = true;
    try {
      await saveReceipt(scan.parsed);
      discardScan();
      await refresh();
      toasts.success("Receipt saved");
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not save receipt",
      );
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
      toasts.success("Receipt deleted");
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not delete receipt",
      );
    } finally {
      deleting = false;
    }
  }

  // --- Edit modal ---
  let editReceipt = $state(null); // the receipt being edited (null = closed)
  /** @type {{ merchant: string, purchase_date: string, total: string, currency: string, category: string }} */
  let editDraft = $state({
    merchant: "",
    purchase_date: "",
    total: "",
    currency: "",
    category: "",
  });
  let editSaving = $state(false);

  function openEdit(r) {
    editReceipt = r;
    editDraft = {
      merchant: r.merchant ?? "",
      purchase_date: r.purchase_date ?? "",
      total: r.total != null ? String(r.total) : "",
      currency: r.currency ?? "",
      category: r.category ?? "",
    };
  }

  function closeEdit() {
    editReceipt = null;
    editDraft = {
      merchant: "",
      purchase_date: "",
      total: "",
      currency: "",
      category: "",
    };
  }

  async function onEditSave() {
    if (!editReceipt) return;
    editSaving = true;
    try {
      const patch = {
        merchant: editDraft.merchant || null,
        purchase_date: editDraft.purchase_date || null,
        total: editDraft.total !== "" ? Number(editDraft.total) : null,
        currency: editDraft.currency || null,
        category: editDraft.category || null,
      };
      await updateReceipt(editReceipt.id, patch);
      closeEdit();
      await refresh();
      toasts.success("Receipt updated");
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not update receipt",
      );
    } finally {
      editSaving = false;
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
      <div class="mt-4">
        <div class="flex justify-between text-xs text-slate-500 mb-1.5">
          <span>
            {uploadPhase === "processing"
              ? "Reading receipt…"
              : "Uploading…"}
          </span>
          {#if uploadPhase === "uploading"}
            <span class="tabular-nums">{uploadPct}%</span>
          {/if}
        </div>
        <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
          {#if uploadPhase === "processing"}
            <div class="h-full w-2/5 rounded-full bg-blue-500 indeterminate"></div>
          {:else}
            <div
              class="h-full rounded-full bg-blue-500 transition-[width] duration-200"
              style="width: {uploadPct}%"
            ></div>
          {/if}
        </div>
      </div>
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
        <pre
          class="mt-2 whitespace-pre-wrap bg-slate-50 p-3 rounded-lg text-xs">{scan.raw_ocr_text}</pre>
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
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <h2 class="font-semibold">History ({filtered.length})</h2>
      <!-- Table / Gallery view toggle -->
      <div
        class="inline-flex rounded-lg border border-slate-300 overflow-hidden text-sm"
      >
        <button
          type="button"
          onclick={() => (view = "table")}
          class="px-3 py-1.5 {view === 'table'
            ? 'bg-blue-600 text-white'
            : 'text-slate-600 hover:bg-slate-50'}"
        >
          Table
        </button>
        <button
          type="button"
          onclick={() => (view = "gallery")}
          class="px-3 py-1.5 border-l border-slate-300 {view === 'gallery'
            ? 'bg-blue-600 text-white'
            : 'text-slate-600 hover:bg-slate-50'}"
        >
          Gallery
        </button>
      </div>
    </div>

    <!-- Filter toolbar -->
    <div
      class="flex flex-wrap items-center gap-3 mb-4 pb-4 border-b border-slate-100"
    >
      <input
        type="search"
        placeholder="Search merchant…"
        value={search}
        oninput={(e) => {
          search = e.currentTarget.value;
          resetPage();
        }}
        class="rounded-lg border border-slate-300 p-1.5 text-sm w-48"
      />
      <label class="text-sm text-slate-500 flex items-center gap-2">
        Category
        <select
          value={filter}
          onchange={(e) => {
            filter = e.currentTarget.value;
            resetPage();
          }}
          class="rounded-lg border border-slate-300 p-1.5 text-sm capitalize"
        >
          <option value="">All</option>
          {#each categories as c}
            <option value={c}>{c}</option>
          {/each}
        </select>
      </label>
      <label class="text-sm text-slate-500 flex items-center gap-2">
        Sort
        <select
          value={sort}
          onchange={(e) => {
            sort = e.currentTarget.value;
            resetPage();
          }}
          class="rounded-lg border border-slate-300 p-1.5 text-sm"
        >
          <option value="date_desc">Newest first</option>
          <option value="date_asc">Oldest first</option>
          <option value="total_desc">Highest total</option>
          <option value="total_asc">Lowest total</option>
        </select>
      </label>
      {#if filtered.length}
        <span class="text-sm text-slate-500 ml-auto">
          Total: {total.toLocaleString()}
        </span>
      {/if}
    </div>

    {#if receipts.length === 0}
      <p class="text-sm text-slate-500">No receipts yet — upload one above.</p>
    {:else if filtered.length === 0}
      <p class="text-sm text-slate-500">No receipts match your filters.</p>
    {:else if view === "gallery"}
      <div class="space-y-8">
        {#each grouped as [cat, items] (cat)}
          <div>
            <div class="flex items-center gap-2 mb-3">
              <span
                class="text-xs rounded-full px-2 py-0.5 capitalize {badgeClass(
                  cat,
                )}">{cat}</span
              >
              <span class="text-xs text-slate-400">{items.length}</span>
            </div>
            <div
              class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3"
            >
              {#each items as r (r.id)}
                <ReceiptThumb
                  receipt={r}
                  onopen={openImage}
                  onedit={openEdit}
                  ondelete={(r) => (pendingDelete = r)}
                  showOwner={isElevated}
                />
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
          {#each paged as r (r.id)}
            <tr class="border-b last:border-0 hover:bg-slate-50">
              <td class="py-2">{r.merchant || "—"}</td>
              {#if isElevated}
                <td class="text-slate-500">{r.owner_email || "—"}</td>
              {/if}
              <td>{r.purchase_date || "—"}</td>
              <td>
                <span
                  class="text-xs rounded-full px-2 py-0.5 {badgeClass(
                    r.category,
                  )}"
                >
                  {r.category}
                </span>
              </td>
              <td class="text-right tabular-nums">
                {r.total != null
                  ? `${r.currency || ""} ${Number(r.total).toLocaleString()}`
                  : "—"}
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
                  onclick={() => openEdit(r)}
                  class="text-slate-600 hover:underline text-xs"
                >
                  edit
                </button>
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

    <!-- Pagination -->
    {#if filtered.length > 0}
      <div
        class="flex flex-wrap items-center justify-between gap-3 mt-5 pt-4 border-t border-slate-100"
      >
        <span class="text-sm text-slate-500">
          Showing {rangeStart}–{rangeEnd} of {filtered.length}
        </span>
        {#if pageCount > 1}
          <div class="flex items-center gap-1">
            <button
              type="button"
              onclick={() => (page = Math.max(1, page - 1))}
              disabled={page <= 1}
              class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            {#each pageWindowed as p}
              {#if p === null}
                <span class="px-1.5 text-slate-400 select-none">…</span>
              {:else}
                <button
                  type="button"
                  onclick={() => (page = p)}
                  class="w-8 h-8 text-sm rounded-lg border {page === p
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'border-slate-300 text-slate-600 hover:bg-slate-50'}"
                >
                  {p}
                </button>
              {/if}
            {/each}
            <button
              type="button"
              onclick={() => (page = Math.min(pageCount, page + 1))}
              disabled={page >= pageCount}
              class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        {/if}
      </div>
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
      <div
        class="absolute top-4 left-1/2 -translate-x-1/2 text-white/90 text-sm flex items-center gap-2"
      >
        <span class="tabular-nums"
          >{viewerIndex + 1} / {orderedReceipts.length}</span
        >
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
        onclick={(e) => {
          e.stopPropagation();
          prevReceipt();
        }}
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
        onclick={(e) => {
          e.stopPropagation();
          nextReceipt();
        }}
        class="absolute right-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full
               bg-white/10 hover:bg-white/25 text-white text-3xl leading-none flex items-center justify-center transition"
      >
        ›
      </button>
    {/if}
  </div>
{/if}

<!-- Edit receipt modal -->
{#if editReceipt}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    role="dialog"
    aria-modal="true"
    aria-label="Edit receipt"
    tabindex="-1"
    class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
    onkeydown={(e) => e.key === "Escape" && closeEdit()}
  >
    <div
      role="presentation"
      class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4"
      onclick={(e) => e.stopPropagation()}
    >
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-lg">Edit receipt</h2>
        <button
          type="button"
          aria-label="Close"
          onclick={closeEdit}
          class="text-slate-400 hover:text-slate-700 text-xl leading-none"
          >&times;</button
        >
      </div>

      <div class="grid grid-cols-1 gap-3">
        <label class="text-sm">
          <span class="font-medium block mb-1">Merchant</span>
          <input
            bind:value={editDraft.merchant}
            class="w-full rounded-lg border border-slate-300 p-2"
            placeholder="e.g. Walmart"
          />
        </label>
        <label class="text-sm">
          <span class="font-medium block mb-1">Date</span>
          <input
            type="date"
            bind:value={editDraft.purchase_date}
            class="w-full rounded-lg border border-slate-300 p-2"
          />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-sm">
            <span class="font-medium block mb-1">Total</span>
            <input
              type="number"
              step="0.01"
              bind:value={editDraft.total}
              class="w-full rounded-lg border border-slate-300 p-2"
              placeholder="0.00"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium block mb-1">Currency</span>
            <input
              bind:value={editDraft.currency}
              class="w-full rounded-lg border border-slate-300 p-2"
              placeholder="e.g. USD"
              maxlength="8"
            />
          </label>
        </div>
        <label class="text-sm">
          <span class="font-medium block mb-1">Category</span>
          <select
            bind:value={editDraft.category}
            class="w-full rounded-lg border border-slate-300 p-2 capitalize"
          >
            <option value="">— uncategorized —</option>
            {#each categories as c}
              <option value={c}>{c}</option>
            {/each}
          </select>
        </label>
      </div>

      <div class="flex gap-3 pt-1">
        <button
          type="button"
          onclick={onEditSave}
          disabled={editSaving}
          class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm font-medium
                 hover:bg-blue-700 disabled:opacity-50"
        >
          {editSaving ? "Saving…" : "Save changes"}
        </button>
        <button
          type="button"
          onclick={closeEdit}
          class="px-4 py-2 rounded-lg border text-sm hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </div>
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

<style>
  /* Indeterminate progress: slide the bar across while OCR runs server-side. */
  .indeterminate {
    animation: indeterminate 1.1s ease-in-out infinite;
  }
  @keyframes indeterminate {
    0% {
      margin-left: -40%;
    }
    100% {
      margin-left: 100%;
    }
  }
</style>
