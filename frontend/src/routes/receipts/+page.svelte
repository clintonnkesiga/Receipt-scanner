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
  import ReceiptEditModal from "$lib/components/ReceiptEditModal.svelte";
  import ZoomableImage from "$lib/components/ZoomableImage.svelte";

  let categories = $state([]);
  let view = $state("gallery");

  // ── Server-side filter / sort / page state ───────────────────────────────────
  const PAGE_SIZE = 20;
  let page = $state(1);
  let search = $state("");
  let filter = $state("");
  let sort = $state("date_desc");
  let dateFrom = $state("");
  let dateTo = $state("");
  let amountMin = $state("");
  let amountMax = $state("");

  // Server response state
  let receipts = $state([]);
  let serverTotal = $state(0);
  let serverTotalSum = $state("0");
  let serverNormalizedSum = $state(null);

  const pageCount = $derived(Math.max(1, Math.ceil(serverTotal / PAGE_SIZE)));
  const rangeStart = $derived(serverTotal ? (page - 1) * PAGE_SIZE + 1 : 0);
  const rangeEnd = $derived(Math.min(page * PAGE_SIZE, serverTotal));

  const pageWindowed = $derived.by(() => {
    if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);
    const keep = new Set(
      [1, pageCount, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pageCount),
    );
    const sorted = [...keep].sort((a, b) => a - b);
    /** @type {(number|null)[]} */
    const result = [];
    for (let i = 0; i < sorted.length; i++) {
      if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push(null);
      result.push(sorted[i]);
    }
    return result;
  });

  // Gallery groups the current page by category.
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

  // Viewer navigates within the current page.
  const orderedReceipts = $derived(
    view === "gallery" ? grouped.flatMap(([, items]) => items) : receipts,
  );

  // Sequence guard: only the latest in-flight request is allowed to render,
  // so fast page clicks / filter edits can't land out of order.
  let _reqSeq = 0;

  async function refresh() {
    const seq = ++_reqSeq;
    try {
      const data = await listReceipts({
        q: search,
        category: filter,
        sort,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        date_from: dateFrom,
        date_to: dateTo,
        amount_min: amountMin,
        amount_max: amountMax,
      });
      if (seq !== _reqSeq) return; // superseded by a newer request
      // Clamp: if the current page is now past the end (e.g. after a delete or
      // a narrower filter), step back to the last real page and refetch.
      const lastPage = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
      if (page > lastPage) {
        page = lastPage;
        return refresh();
      }
      receipts = data.items;
      serverTotal = data.total;
      serverTotalSum = data.total_sum;
      serverNormalizedSum = data.normalized_sum ?? null;
    } catch (e) {
      if (seq === _reqSeq)
        toasts.error(e instanceof Error ? e.message : "Could not load receipts");
    }
  }

  // Immediate filter apply (selects, date pickers, clear button).
  function applyFilter(updater) {
    updater();
    page = 1;
    refresh();
  }

  // Debounced apply for free-text/number inputs so we don't fire a request per
  // keystroke.
  let _filterTimer;
  function applyFilterDebounced(updater, delay = 350) {
    updater();
    page = 1;
    clearTimeout(_filterTimer);
    _filterTimer = setTimeout(refresh, delay);
  }

  function goToPage(p) {
    if (p < 1 || p > pageCount || p === page) return;
    page = p;
    refresh();
    // Bring the list back into view — otherwise the page swaps above the fold
    // and it looks like nothing happened.
    document
      .getElementById("receipt-history")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  onMount(async () => {
    try {
      categories = (await listCategories()).map((c) => c.name);
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load categories");
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

  // ── Scan queue (batch upload) ────────────────────────────────────────────────
  let scanQueue = $state([]);
  let _queueCounter = 0;

  const isPdfPath = (path) => !!path && path.toLowerCase().endsWith(".pdf");

  async function processScanItem(item) {
    item.status = "scanning";
    item.uploadPhase = "uploading";
    item.uploadPct = 0;
    try {
      const result = await scanReceipt(item.file, (frac) => {
        item.uploadPct = Math.round(frac * 100);
        if (frac >= 1) item.uploadPhase = "processing";
      });
      item.scan = result;
      item.previewUrl = URL.createObjectURL(item.file);
      item.previewIsPdf = item.file.type === "application/pdf";
      item.status = "done";
    } catch (err) {
      item.status = "error";
      item.error = err instanceof Error ? err.message : "Scan failed";
      toasts.error(item.error);
    } finally {
      item.uploadPhase = "idle";
    }
  }

  async function onUpload(e) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    e.target.value = "";
    const newItems = files.map((file) => ({
      id: ++_queueCounter,
      file,
      status: "pending",
      scan: null,
      previewUrl: null,
      previewIsPdf: false,
      saving: false,
      forceSave: false,
      uploadPhase: "idle",
      uploadPct: 0,
      error: null,
    }));
    scanQueue.push(...newItems);
    // Process the batch with bounded concurrency so several receipts OCR in
    // parallel (the backend runs OCR off-thread) instead of strictly one at a
    // time. Drive the *proxied* queue entries (look up by id) so mutations
    // trigger Svelte reactivity — otherwise the progress bars stay frozen.
    const ids = newItems.map((i) => i.id);
    let cursor = 0;
    const worker = async () => {
      while (cursor < ids.length) {
        const id = ids[cursor++];
        const item = scanQueue.find((i) => i.id === id);
        if (item) await processScanItem(item);
      }
    };
    const SCAN_CONCURRENCY = 3;
    await Promise.all(
      Array.from({ length: Math.min(SCAN_CONCURRENCY, ids.length) }, worker),
    );
  }

  async function saveScanItem(item) {
    if (!item.scan) return;
    item.saving = true;
    try {
      await saveReceipt({ ...item.scan.parsed, force: !!item.forceSave });
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      const idx = scanQueue.findIndex((i) => i.id === item.id);
      if (idx >= 0) scanQueue.splice(idx, 1);
      await refresh();
      toasts.success("Receipt saved");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not save receipt");
      item.saving = false;
    }
  }

  function discardScanItem(item) {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    const idx = scanQueue.findIndex((i) => i.id === item.id);
    if (idx >= 0) scanQueue.splice(idx, 1);
  }

  function reviewOptions(scan) {
    return scan?.parsed?.category && !categories.includes(scan.parsed.category)
      ? [scan.parsed.category, ...categories]
      : categories;
  }

  // ── Image viewer (with rotation) ─────────────────────────────────────────────
  let viewerUrl = $state(null);
  let viewerIsPdf = $state(false);
  let viewerLoading = $state(false);
  let viewerIndex = $state(-1);

  const viewerReceipt = $derived(viewerIndex >= 0 ? orderedReceipts[viewerIndex] : null);
  const canPrev = $derived(viewerIndex > 0);
  const canNext = $derived(viewerIndex >= 0 && viewerIndex < orderedReceipts.length - 1);

  let viewerToken = 0;
  async function openAt(index) {
    if (index < 0 || index >= orderedReceipts.length) return;
    const receipt = orderedReceipts[index];
    const token = ++viewerToken;
    viewerIndex = index;
    viewerIsPdf = isPdfPath(receipt.image_path);
    // URLs come from the shared image cache — never revoke them here.
    viewerUrl = null;
    viewerLoading = true;
    try {
      const url = await getReceiptImageUrl(receipt.id);
      if (token !== viewerToken) return;
      viewerUrl = url;
    } catch (err) {
      if (token === viewerToken)
        toasts.error(err instanceof Error ? err.message : "Could not load image");
    } finally {
      if (token === viewerToken) viewerLoading = false;
    }
  }

  function openImage(receipt) { openAt(orderedReceipts.indexOf(receipt)); }
  function prevReceipt() { if (canPrev) openAt(viewerIndex - 1); }
  function nextReceipt() { if (canNext) openAt(viewerIndex + 1); }

  function closeViewer() {
    viewerToken++;
    viewerUrl = null;
    viewerIndex = -1;
  }

  function onViewerKey(e) {
    if (viewerIndex < 0 && !viewerLoading) return;
    if (e.key === "Escape") closeViewer();
    else if (e.key === "ArrowLeft") prevReceipt();
    else if (e.key === "ArrowRight") nextReceipt();
  }

  let rotatingViewer = $state(false);
  async function rotateViewer(delta) {
    if (!viewerReceipt || rotatingViewer) return;
    const newRotation = (((viewerReceipt.rotation ?? 0) + delta) % 360 + 360) % 360;
    rotatingViewer = true;
    try {
      const updated = await updateReceipt(viewerReceipt.id, { rotation: newRotation });
      const idx = receipts.findIndex((r) => r.id === updated.id);
      if (idx >= 0) receipts[idx] = updated;
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not rotate image");
    } finally {
      rotatingViewer = false;
    }
  }

  const isElevated = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  // ── Delete ───────────────────────────────────────────────────────────────────
  let pendingDelete = $state(null);
  let deleting = $state(false);

  async function confirmDelete() {
    if (!pendingDelete) return;
    deleting = true;
    try {
      await deleteReceipt(pendingDelete.id);
      pendingDelete = null;
      await refresh();
      toasts.success("Moved to trash");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not delete receipt");
    } finally {
      deleting = false;
    }
  }

  // ── Edit modal (the form lives in the shared ReceiptEditModal component) ─────
  let editReceipt = $state(null);
  const openEdit = (r) => (editReceipt = r);
  const closeEdit = () => (editReceipt = null);

  async function onEditSaved() {
    closeEdit();
    await refresh();
  }

  function badgeClass(category) {
    return category === "fuel"
      ? "bg-amber-100 text-amber-800"
      : category === "grocery"
        ? "bg-emerald-100 text-emerald-800"
        : "bg-slate-100 text-slate-700";
  }

  const fmt = (n) => Number(n || 0).toLocaleString();
</script>

<div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-semibold">Receipts</h1>
    <button
      onclick={onExport}
      class="text-sm text-blue-600 hover:underline"
      disabled={serverTotal === 0}
    >Export CSV</button>
  </div>

  <!-- Upload (supports multiple files) + mobile camera capture -->
  <section class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-5">
    <div class="text-sm font-medium mb-2">Add receipts</div>
    <div class="flex flex-col sm:flex-row gap-3">
      <!-- File picker (photos or PDFs) -->
      <label class="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 cursor-pointer transition {scanQueue.some((i) => i.status === 'scanning') ? 'opacity-50 pointer-events-none' : ''}">
        <span>⬆️ Upload photos or PDFs</span>
        <input
          type="file"
          accept="image/*,application/pdf"
          multiple
          onchange={onUpload}
          disabled={scanQueue.some((i) => i.status === "scanning")}
          class="sr-only"
        />
      </label>
      <!-- Camera: opens the device camera directly on phones/tablets -->
      <label class="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2.5 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 cursor-pointer transition {scanQueue.some((i) => i.status === 'scanning') ? 'opacity-50 pointer-events-none' : ''}">
        <span>📷 Take photo</span>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onchange={onUpload}
          disabled={scanQueue.some((i) => i.status === "scanning")}
          class="sr-only"
        />
      </label>
    </div>
    {#each scanQueue.filter((i) => i.status === "scanning") as item (item.id)}
      <div class="mt-4">
        <div class="flex justify-between text-xs text-slate-500 mb-1.5">
          <span class="truncate max-w-xs">{item.file.name}</span>
          <span>{item.uploadPhase === "processing" ? "Reading receipt…" : `${item.uploadPct}%`}</span>
        </div>
        <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
          {#if item.uploadPhase === "processing"}
            <div class="h-full w-2/5 rounded-full bg-blue-500 indeterminate"></div>
          {:else}
            <div class="h-full rounded-full bg-blue-500 transition-[width] duration-200" style="width:{item.uploadPct}%"></div>
          {/if}
        </div>
      </div>
    {/each}
  </section>

  <!-- Scan review panels -->
  {#each scanQueue.filter((i) => i.status === "done") as item (item.id)}
    <section class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-5 space-y-4 border-l-4 border-blue-400">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">Review &amp; correct</h2>
        <span class="text-xs text-slate-400 truncate max-w-xs">{item.file.name}</span>
      </div>

      {#if item.scan.duplicates?.length}
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 space-y-2">
          <div>
            <strong>Possible duplicate{item.scan.duplicates.length > 1 ? "s" : ""} detected</strong>
            — {item.scan.duplicates.length} similar receipt{item.scan.duplicates.length > 1 ? "s" : ""} already saved
            ({item.scan.duplicates.map((d) => d.merchant || "Untitled").join(", ")}).
            Saving is blocked unless you confirm.
          </div>
          <label class="flex items-center gap-2 font-medium">
            <input type="checkbox" bind:checked={item.forceSave} class="rounded border-amber-400" />
            Save anyway
          </label>
        </div>
      {/if}

      {#if item.previewUrl}
        {#if item.previewIsPdf}
          <embed src={item.previewUrl} type="application/pdf" class="w-full h-96 rounded-lg border border-slate-200" />
        {:else}
          <ZoomableImage src={item.previewUrl} alt="Uploaded receipt" thumbClass="max-h-72 rounded-lg border border-slate-200" />
        {/if}
      {/if}

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label class="text-sm"><span class="font-medium">Merchant</span>
          <input bind:value={item.scan.parsed.merchant} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">Date</span>
          <input type="date" bind:value={item.scan.parsed.purchase_date} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">Total</span>
          <input bind:value={item.scan.parsed.total} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">Currency</span>
          <input bind:value={item.scan.parsed.currency} class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">Tax / VAT</span>
          <input bind:value={item.scan.parsed.tax_amount} placeholder="auto-detected" class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">Net amount</span>
          <input bind:value={item.scan.parsed.net_amount} placeholder="total − tax" class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">FX rate</span>
          <input bind:value={item.scan.parsed.fx_rate} placeholder="e.g. 3700 (UGX per USD)" class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm"><span class="font-medium">Category</span>
          <select bind:value={item.scan.parsed.category} class="mt-1 block w-full rounded-lg border border-slate-300 p-2 capitalize">
            {#each reviewOptions(item.scan) as c}<option value={c}>{c}</option>{/each}
          </select>
        </label>
      </div>

      <!-- Editable line items -->
      <div>
        <div class="flex items-center justify-between mb-1">
          <span class="text-sm font-medium">Line items</span>
          <button type="button" onclick={() => item.scan.parsed.line_items.push({ description: "", quantity: null, unit_price: null, amount: null })} class="text-xs text-blue-600 hover:underline">+ Add line</button>
        </div>
        {#if item.scan.parsed.line_items?.length}
          <div class="space-y-1">
            {#each item.scan.parsed.line_items as li, i}
              <div class="grid grid-cols-[1fr_5rem_5rem_5rem_1.5rem] gap-1 items-center">
                <input bind:value={li.description} placeholder="Description" class="rounded border border-slate-300 p-1 text-xs" />
                <input bind:value={li.quantity} placeholder="Qty" class="rounded border border-slate-300 p-1 text-xs text-right" />
                <input bind:value={li.unit_price} placeholder="Unit" class="rounded border border-slate-300 p-1 text-xs text-right" />
                <input bind:value={li.amount} placeholder="Amount" class="rounded border border-slate-300 p-1 text-xs text-right" />
                <button type="button" onclick={() => item.scan.parsed.line_items.splice(i, 1)} class="text-red-400 hover:text-red-600 text-base leading-none text-center" aria-label="Remove">&times;</button>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-slate-400">No line items parsed.</p>
        {/if}
      </div>


      <div class="flex gap-3">
        <button
          onclick={() => saveScanItem(item)}
          disabled={item.saving || (item.scan.duplicates?.length && !item.forceSave)}
          class="bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {item.saving ? "Saving…" : "Save receipt"}
        </button>
        <button onclick={() => discardScanItem(item)} class="px-4 py-2 rounded-lg border hover:bg-slate-50">Discard</button>
      </div>
    </section>
  {/each}

  <!-- History -->
  <section id="receipt-history" class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <h2 class="font-semibold">History ({serverTotal})</h2>
      <div class="inline-flex rounded-lg border border-slate-300 overflow-hidden text-sm">
        <button type="button" onclick={() => (view = "table")} class="px-3 py-1.5 {view==='table'?'bg-blue-600 text-white':'text-slate-600 hover:bg-slate-50'}">Table</button>
        <button type="button" onclick={() => (view = "gallery")} class="px-3 py-1.5 border-l border-slate-300 {view==='gallery'?'bg-blue-600 text-white':'text-slate-600 hover:bg-slate-50'}">Gallery</button>
      </div>
    </div>

    <!-- Filter toolbar -->
    <div class="flex flex-wrap items-center gap-3 mb-4 pb-4 border-b border-slate-100">
      <input
        type="search"
        placeholder="Search merchant…"
        value={search}
        oninput={(e) => applyFilterDebounced(() => (search = e.currentTarget.value))}
        class="rounded-lg border border-slate-300 p-1.5 text-sm w-40"
      />
      <label class="text-sm text-slate-500 flex items-center gap-1">
        Category
        <select value={filter} onchange={(e) => applyFilter(() => (filter = e.currentTarget.value))} class="rounded-lg border border-slate-300 p-1.5 text-sm capitalize">
          <option value="">All</option>
          {#each categories as c}<option value={c}>{c}</option>{/each}
        </select>
      </label>
      <label class="text-sm text-slate-500 flex items-center gap-1">
        Sort
        <select value={sort} onchange={(e) => applyFilter(() => (sort = e.currentTarget.value))} class="rounded-lg border border-slate-300 p-1.5 text-sm">
          <option value="date_desc">Newest first</option>
          <option value="date_asc">Oldest first</option>
          <option value="total_desc">Highest total</option>
          <option value="total_asc">Lowest total</option>
        </select>
      </label>
      <!-- Date range -->
      <label class="text-sm text-slate-500 flex items-center gap-1">
        From
        <input type="date" value={dateFrom} onchange={(e) => applyFilter(() => (dateFrom = e.currentTarget.value))} class="rounded-lg border border-slate-300 p-1.5 text-sm" />
      </label>
      <label class="text-sm text-slate-500 flex items-center gap-1">
        To
        <input type="date" value={dateTo} onchange={(e) => applyFilter(() => (dateTo = e.currentTarget.value))} class="rounded-lg border border-slate-300 p-1.5 text-sm" />
      </label>
      <!-- Amount range -->
      <label class="text-sm text-slate-500 flex items-center gap-1">
        Min
        <input type="number" step="0.01" placeholder="0" value={amountMin} oninput={(e) => applyFilterDebounced(() => (amountMin = e.currentTarget.value))} class="rounded-lg border border-slate-300 p-1.5 text-sm w-24" />
      </label>
      <label class="text-sm text-slate-500 flex items-center gap-1">
        Max
        <input type="number" step="0.01" placeholder="∞" value={amountMax} oninput={(e) => applyFilterDebounced(() => (amountMax = e.currentTarget.value))} class="rounded-lg border border-slate-300 p-1.5 text-sm w-24" />
      </label>
      {#if dateFrom || dateTo || amountMin || amountMax || search || filter}
        <button type="button" onclick={() => applyFilter(() => { search=""; filter=""; dateFrom=""; dateTo=""; amountMin=""; amountMax=""; })} class="text-xs text-slate-400 hover:text-slate-700 underline">Clear filters</button>
      {/if}
      {#if serverTotal > 0}
        <span class="text-sm text-slate-500 ml-auto">
          Total: {fmt(serverTotalSum)}
          {#if serverNormalizedSum && String(serverNormalizedSum) !== String(serverTotalSum)}
            <span class="text-xs text-slate-400">(normalized: {fmt(serverNormalizedSum)})</span>
          {/if}
        </span>
      {/if}
    </div>

    {#if serverTotal === 0 && !search && !filter && !dateFrom && !dateTo && !amountMin && !amountMax}
      <p class="text-sm text-slate-500">No receipts yet — upload one above.</p>
    {:else if receipts.length === 0}
      <p class="text-sm text-slate-500">No receipts match your filters.</p>
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
                <ReceiptThumb receipt={r} onopen={openImage} onedit={openEdit} ondelete={(r) => (pendingDelete = r)} showOwner={isElevated} />
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div class="overflow-x-auto">
      <table class="w-full text-sm min-w-[600px]">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">Merchant</th>
            {#if isElevated}<th>Owner</th>{/if}
            <th>Date</th>
            <th>Category</th>
            <th class="text-right">Total</th>
            <th class="text-right text-xs">Tax</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each receipts as r (r.id)}
            <tr class="border-b last:border-0 hover:bg-slate-50">
              <td class="py-2">
                <a href={`/receipts/${r.id}`} class="text-blue-600 dark:text-blue-400 hover:underline">{r.merchant || "—"}</a>
              </td>
              {#if isElevated}<td class="text-slate-500">{r.owner_email || "—"}</td>{/if}
              <td>{r.purchase_date || "—"}</td>
              <td><span class="text-xs rounded-full px-2 py-0.5 {badgeClass(r.category)}">{r.category}</span></td>
              <td class="text-right tabular-nums">
                {r.total != null ? `${r.currency || ""} ${Number(r.total).toLocaleString()}` : "—"}
              </td>
              <td class="text-right tabular-nums text-xs text-slate-500">
                {r.tax_amount != null ? Number(r.tax_amount).toLocaleString() : "—"}
              </td>
              <td class="text-right space-x-3 whitespace-nowrap">
                {#if r.image_path}
                  <button onclick={() => openImage(r)} class="text-blue-600 hover:underline text-xs">view</button>
                {/if}
                <button onclick={() => openEdit(r)} class="text-slate-600 hover:underline text-xs">edit</button>
                <button onclick={() => (pendingDelete = r)} class="text-red-600 hover:underline text-xs">delete</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      </div>
    {/if}

    <!-- Pagination -->
    {#if serverTotal > 0}
      <div class="flex flex-wrap items-center justify-between gap-3 mt-5 pt-4 border-t border-slate-100">
        <span class="text-sm text-slate-500">Showing {rangeStart}–{rangeEnd} of {serverTotal}</span>
        {#if pageCount > 1}
          <div class="flex items-center gap-1">
            <button type="button" onclick={() => goToPage(Math.max(1, page - 1))} disabled={page <= 1} class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed">Prev</button>
            {#each pageWindowed as p}
              {#if p === null}
                <span class="px-1.5 text-slate-400 select-none">…</span>
              {:else}
                <button type="button" onclick={() => goToPage(p)} class="w-8 h-8 text-sm rounded-lg border {page===p?'bg-blue-600 text-white border-blue-600':'border-slate-300 text-slate-600 hover:bg-slate-50'}">{p}</button>
              {/if}
            {/each}
            <button type="button" onclick={() => goToPage(Math.min(pageCount, page + 1))} disabled={page >= pageCount} class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed">Next</button>
          </div>
        {/if}
      </div>
    {/if}
  </section>
</div>

<svelte:window onkeydown={onViewerKey} />

<!-- Image viewer with rotation -->
{#if viewerUrl || viewerLoading}
  <div role="presentation" class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onclick={closeViewer}>
    {#if viewerReceipt}
      <div class="absolute top-4 left-1/2 -translate-x-1/2 text-white/90 text-sm flex items-center gap-2">
        <span class="tabular-nums">{viewerIndex + 1} / {orderedReceipts.length}</span>
        {#if viewerReceipt.merchant}<span class="text-white/50">·</span><span class="truncate max-w-[40vw]">{viewerReceipt.merchant}</span>{/if}
      </div>
    {/if}

    {#if viewerReceipt && !viewerIsPdf}
      <div class="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-black/50 rounded-full px-4 py-2" role="presentation" onclick={(e) => e.stopPropagation()}>
        <button type="button" aria-label="Rotate counter-clockwise" onclick={() => rotateViewer(-90)} disabled={rotatingViewer} class="text-white/80 hover:text-white text-xl w-8 h-8 flex items-center justify-center disabled:opacity-40">↺</button>
        <span class="text-white/50 text-xs tabular-nums w-8 text-center">{viewerReceipt.rotation ?? 0}°</span>
        <button type="button" aria-label="Rotate clockwise" onclick={() => rotateViewer(90)} disabled={rotatingViewer} class="text-white/80 hover:text-white text-xl w-8 h-8 flex items-center justify-center disabled:opacity-40">↻</button>
      </div>
    {/if}

    {#if canPrev}
      <button type="button" aria-label="Previous" onclick={(e) => { e.stopPropagation(); prevReceipt(); }} class="absolute left-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full bg-white/10 hover:bg-white/25 text-white text-3xl leading-none flex items-center justify-center transition">‹</button>
    {/if}

    {#if viewerLoading}
      <div class="text-white text-sm animate-pulse">Loading…</div>
    {:else if viewerIsPdf}
      <iframe src={viewerUrl} title="Receipt PDF" class="w-[90vw] h-[90vh] rounded-lg shadow-2xl bg-white" onclick={(e) => e.stopPropagation()}></iframe>
    {:else}
      <img src={viewerUrl} alt="Receipt" class="max-h-[85vh] max-w-[75vw] rounded-lg shadow-2xl transition-transform duration-300" style="transform:rotate({viewerReceipt?.rotation??0}deg)" onclick={(e) => e.stopPropagation()} />
    {/if}

    {#if canNext}
      <button type="button" aria-label="Next" onclick={(e) => { e.stopPropagation(); nextReceipt(); }} class="absolute right-4 top-1/2 -translate-y-1/2 z-10 w-12 h-12 rounded-full bg-white/10 hover:bg-white/25 text-white text-3xl leading-none flex items-center justify-center transition">›</button>
    {/if}
  </div>
{/if}

<!-- Edit modal (shared with the receipt detail page) -->
<ReceiptEditModal
  receipt={editReceipt}
  {categories}
  open={editReceipt != null}
  onclose={closeEdit}
  onsaved={onEditSaved}
/>

<ConfirmDialog
  open={pendingDelete != null}
  busy={deleting}
  title="Move this receipt to Trash?"
  message={pendingDelete ? `"${pendingDelete.merchant || "Untitled"}" will be moved to the Trash. You can restore it later.` : ""}
  confirmLabel={deleting ? "Moving…" : "Move to Trash"}
  onconfirm={confirmDelete}
  oncancel={() => (pendingDelete = null)}
/>

<style>
  .indeterminate {
    animation: indeterminate 1.1s ease-in-out infinite;
  }
  @keyframes indeterminate {
    0%   { margin-left: -40%; }
    100% { margin-left: 100%; }
  }
</style>
