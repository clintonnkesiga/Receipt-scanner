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
    rescanReceipt,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import ReceiptThumb from "$lib/components/ReceiptThumb.svelte";

  let categories = $state([]);
  let view = $state("gallery");

  let filter = $state("");
  let search = $state("");
  let sort = $state("date_desc");

  const PAGE_SIZE = 12;
  let page = $state(1);

  let receipts = $state([]);

  // ── Scan queue (batch upload) ────────────────────────────────────────────────
  // Each item: { id, file, status, scan, previewUrl, previewIsPdf,
  //              saving, uploadPhase, uploadPct, error }
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
      uploadPhase: "idle",
      uploadPct: 0,
      error: null,
    }));
    scanQueue.push(...newItems);

    // Scan sequentially to avoid hammering the OCR server.
    for (const item of newItems) {
      await processScanItem(item);
    }
  }

  async function saveScanItem(item) {
    if (!item.scan) return;
    item.saving = true;
    try {
      await saveReceipt(item.scan.parsed);
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

  // Category options for a scan review panel.
  function reviewOptions(scan) {
    return scan?.parsed?.category && !categories.includes(scan.parsed.category)
      ? [scan.parsed.category, ...categories]
      : categories;
  }

  // ── Full-size image viewer (with rotation) ───────────────────────────────────
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
    if (viewerUrl) { URL.revokeObjectURL(viewerUrl); viewerUrl = null; }
    viewerLoading = true;
    try {
      const url = await getReceiptImageUrl(receipt.id);
      if (token !== viewerToken) { URL.revokeObjectURL(url); return; }
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
    if (viewerUrl) URL.revokeObjectURL(viewerUrl);
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

  // ── Receipt list (filter / sort / paginate) ──────────────────────────────────
  const isElevated = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  const filtered = $derived.by(() => {
    const q = search.trim().toLowerCase();
    let list = receipts.filter(
      (r) =>
        (!filter || r.category === filter) &&
        (!q || (r.merchant || "").toLowerCase().includes(q)),
    );
    const num = (r) => Number(r.total) || 0;
    const day = (r) => r.purchase_date || "";
    const cmp = {
      date_desc:  (a, b) => day(b).localeCompare(day(a)),
      date_asc:   (a, b) => day(a).localeCompare(day(b)),
      total_desc: (a, b) => num(b) - num(a),
      total_asc:  (a, b) => num(a) - num(b),
    }[sort];
    return [...list].sort(cmp);
  });

  const total = $derived(filtered.reduce((sum, r) => sum + (Number(r.total) || 0), 0));
  const pageCount = $derived(Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
  $effect(() => { if (page > pageCount) page = pageCount; });
  const paged = $derived(filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE));

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

  const orderedReceipts = $derived(
    view === "gallery" ? grouped.flatMap(([, items]) => items) : paged,
  );

  const rangeStart = $derived(filtered.length ? (page - 1) * PAGE_SIZE + 1 : 0);
  const rangeEnd = $derived(Math.min(page * PAGE_SIZE, filtered.length));

  async function refresh() {
    try {
      receipts = await listReceipts();
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load receipts");
    }
  }

  function resetPage() { page = 1; }

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
      toasts.success("Receipt deleted");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not delete receipt");
    } finally {
      deleting = false;
    }
  }

  // ── Edit modal (header fields + line items + rescan) ─────────────────────────
  let editReceipt = $state(null);
  let editDraft = $state({
    merchant: "", purchase_date: "", total: "", currency: "", category: "",
    line_items: [],
  });
  let editSaving = $state(false);

  let rescanResult = $state(null);
  let rescanning = $state(false);

  function openEdit(r) {
    editReceipt = r;
    rescanResult = null;
    editDraft = {
      merchant:      r.merchant      ?? "",
      purchase_date: r.purchase_date ?? "",
      total:         r.total != null ? String(r.total) : "",
      currency:      r.currency      ?? "",
      category:      r.category      ?? "",
      line_items: (r.line_items ?? []).map((li) => ({
        description: li.description  ?? "",
        quantity:    li.quantity   != null ? String(li.quantity)   : "",
        unit_price:  li.unit_price != null ? String(li.unit_price) : "",
        amount:      li.amount     != null ? String(li.amount)     : "",
      })),
    };
  }

  function closeEdit() {
    editReceipt = null;
    rescanResult = null;
    editDraft = { merchant: "", purchase_date: "", total: "", currency: "", category: "", line_items: [] };
  }

  function addLineItem() {
    editDraft.line_items.push({ description: "", quantity: "", unit_price: "", amount: "" });
  }

  function removeLineItem(i) {
    editDraft.line_items.splice(i, 1);
  }

  async function onRescan() {
    if (!editReceipt) return;
    rescanning = true;
    rescanResult = null;
    try {
      rescanResult = await rescanReceipt(editReceipt.id);
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Rescan failed");
    } finally {
      rescanning = false;
    }
  }

  function applyRescanResult() {
    if (!rescanResult) return;
    const p = rescanResult.parsed;
    if (p.merchant)      editDraft.merchant      = p.merchant;
    if (p.purchase_date) editDraft.purchase_date = p.purchase_date;
    if (p.total != null) editDraft.total         = String(p.total);
    if (p.currency)      editDraft.currency      = p.currency;
    if (p.category)      editDraft.category      = p.category;
    if (p.line_items?.length) {
      editDraft.line_items = p.line_items.map((li) => ({
        description: li.description  ?? "",
        quantity:    li.quantity   != null ? String(li.quantity)   : "",
        unit_price:  li.unit_price != null ? String(li.unit_price) : "",
        amount:      li.amount     != null ? String(li.amount)     : "",
      }));
    }
    rescanResult = null;
    toasts.success("OCR values applied — review and save");
  }

  async function onEditSave() {
    if (!editReceipt) return;
    editSaving = true;
    try {
      const patch = {
        merchant:      editDraft.merchant      || null,
        purchase_date: editDraft.purchase_date || null,
        total:         editDraft.total !== ""  ? Number(editDraft.total) : null,
        currency:      editDraft.currency      || null,
        category:      editDraft.category      || null,
        line_items: editDraft.line_items.map((li) => ({
          description: li.description || null,
          quantity:    li.quantity   !== "" ? Number(li.quantity)   : null,
          unit_price:  li.unit_price !== "" ? Number(li.unit_price) : null,
          amount:      li.amount     !== "" ? Number(li.amount)     : null,
        })),
      };
      await updateReceipt(editReceipt.id, patch);
      closeEdit();
      await refresh();
      toasts.success("Receipt updated");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not update receipt");
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

  <!-- Upload (supports multiple files) -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <label class="block">
      <span class="text-sm font-medium">Upload receipt photos or PDFs</span>
      <input
        type="file"
        accept="image/*,application/pdf"
        multiple
        onchange={onUpload}
        disabled={scanQueue.some((i) => i.status === "scanning")}
        class="mt-2 block w-full text-sm file:mr-4 file:rounded-lg file:border-0
               file:bg-blue-600 file:px-4 file:py-2 file:text-white
               hover:file:bg-blue-700 file:cursor-pointer disabled:opacity-50"
      />
    </label>

    <!-- Per-file progress bars while scanning -->
    {#each scanQueue.filter((i) => i.status === "scanning") as item (item.id)}
      <div class="mt-4">
        <div class="flex justify-between text-xs text-slate-500 mb-1.5">
          <span class="truncate max-w-xs">{item.file.name}</span>
          <span>
            {item.uploadPhase === "processing"
              ? "Reading receipt…"
              : item.uploadPhase === "uploading"
                ? `${item.uploadPct}%`
                : ""}
          </span>
        </div>
        <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
          {#if item.uploadPhase === "processing"}
            <div class="h-full w-2/5 rounded-full bg-blue-500 indeterminate"></div>
          {:else}
            <div
              class="h-full rounded-full bg-blue-500 transition-[width] duration-200"
              style="width: {item.uploadPct}%"
            ></div>
          {/if}
        </div>
      </div>
    {/each}
  </section>

  <!-- Review panels — one per successfully scanned file -->
  {#each scanQueue.filter((i) => i.status === "done") as item (item.id)}
    <section class="bg-white rounded-xl shadow-sm p-5 space-y-4 border-l-4 border-blue-400">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">Review &amp; correct</h2>
        <span class="text-xs text-slate-400 truncate max-w-xs">{item.file.name}</span>
      </div>

      <!-- Duplicate warning -->
      {#if item.scan.duplicates?.length}
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
          <strong>Possible duplicate{item.scan.duplicates.length > 1 ? "s" : ""} detected</strong>
          — {item.scan.duplicates.length} similar receipt{item.scan.duplicates.length > 1 ? "s" : ""} already saved
          ({item.scan.duplicates.map((d) => d.merchant || "Untitled").join(", ")}).
          Review before saving.
        </div>
      {/if}

      <!-- Image preview -->
      {#if item.previewUrl}
        {#if item.previewIsPdf}
          <embed
            src={item.previewUrl}
            type="application/pdf"
            class="w-full h-96 rounded-lg border border-slate-200"
          />
        {:else}
          <img
            src={item.previewUrl}
            alt="Uploaded receipt"
            class="max-h-72 rounded-lg border border-slate-200 mx-auto"
          />
        {/if}
      {/if}

      <!-- Header fields -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label class="text-sm">
          <span class="font-medium">Merchant</span>
          <input
            bind:value={item.scan.parsed.merchant}
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
          />
        </label>
        <label class="text-sm">
          <span class="font-medium">Date</span>
          <input
            type="date"
            bind:value={item.scan.parsed.purchase_date}
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
          />
        </label>
        <label class="text-sm">
          <span class="font-medium">Total</span>
          <input
            bind:value={item.scan.parsed.total}
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
          />
        </label>
        <label class="text-sm">
          <span class="font-medium">Currency</span>
          <input
            bind:value={item.scan.parsed.currency}
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
          />
        </label>
        <label class="text-sm">
          <span class="font-medium">Category</span>
          <select
            bind:value={item.scan.parsed.category}
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2 capitalize"
          >
            {#each reviewOptions(item.scan) as c}
              <option value={c}>{c}</option>
            {/each}
          </select>
        </label>
      </div>

      <!-- Line items (editable in scan review) -->
      <div>
        <div class="flex items-center justify-between mb-1">
          <span class="text-sm font-medium">Line items</span>
          <button
            type="button"
            onclick={() => item.scan.parsed.line_items.push({ description: "", quantity: null, unit_price: null, amount: null })}
            class="text-xs text-blue-600 hover:underline"
          >+ Add line</button>
        </div>
        {#if item.scan.parsed.line_items?.length}
          <div class="space-y-1">
            {#each item.scan.parsed.line_items as li, i}
              <div class="grid grid-cols-[1fr_5rem_5rem_5rem_1.5rem] gap-1 items-center">
                <input
                  bind:value={li.description}
                  placeholder="Description"
                  class="rounded border border-slate-300 p-1 text-xs"
                />
                <input
                  bind:value={li.quantity}
                  placeholder="Qty"
                  class="rounded border border-slate-300 p-1 text-xs text-right"
                />
                <input
                  bind:value={li.unit_price}
                  placeholder="Unit"
                  class="rounded border border-slate-300 p-1 text-xs text-right"
                />
                <input
                  bind:value={li.amount}
                  placeholder="Amount"
                  class="rounded border border-slate-300 p-1 text-xs text-right"
                />
                <button
                  type="button"
                  onclick={() => item.scan.parsed.line_items.splice(i, 1)}
                  class="text-red-400 hover:text-red-600 text-base leading-none text-center"
                  aria-label="Remove"
                >&times;</button>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-slate-400">No line items parsed.</p>
        {/if}
      </div>

      <details class="text-sm">
        <summary class="cursor-pointer text-slate-500">Raw OCR text</summary>
        <pre class="mt-2 whitespace-pre-wrap bg-slate-50 p-3 rounded-lg text-xs">{item.scan.raw_ocr_text}</pre>
      </details>

      <div class="flex gap-3">
        <button
          onclick={() => saveScanItem(item)}
          disabled={item.saving}
          class="bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
        >
          {item.saving ? "Saving…" : "Save receipt"}
        </button>
        <button
          onclick={() => discardScanItem(item)}
          class="px-4 py-2 rounded-lg border hover:bg-slate-50"
        >
          Discard
        </button>
      </div>
    </section>
  {/each}

  <!-- History -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <h2 class="font-semibold">History ({filtered.length})</h2>
      <div class="inline-flex rounded-lg border border-slate-300 overflow-hidden text-sm">
        <button
          type="button"
          onclick={() => (view = "table")}
          class="px-3 py-1.5 {view === 'table' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'}"
        >Table</button>
        <button
          type="button"
          onclick={() => (view = "gallery")}
          class="px-3 py-1.5 border-l border-slate-300 {view === 'gallery' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'}"
        >Gallery</button>
      </div>
    </div>

    <!-- Filter toolbar -->
    <div class="flex flex-wrap items-center gap-3 mb-4 pb-4 border-b border-slate-100">
      <input
        type="search"
        placeholder="Search merchant…"
        value={search}
        oninput={(e) => { search = e.currentTarget.value; resetPage(); }}
        class="rounded-lg border border-slate-300 p-1.5 text-sm w-48"
      />
      <label class="text-sm text-slate-500 flex items-center gap-2">
        Category
        <select
          value={filter}
          onchange={(e) => { filter = e.currentTarget.value; resetPage(); }}
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
          onchange={(e) => { sort = e.currentTarget.value; resetPage(); }}
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
              <span class="text-xs rounded-full px-2 py-0.5 capitalize {badgeClass(cat)}">{cat}</span>
              <span class="text-xs text-slate-400">{items.length}</span>
            </div>
            <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
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
                  >view</button>
                {/if}
                <button
                  onclick={() => openEdit(r)}
                  class="text-slate-600 hover:underline text-xs"
                >edit</button>
                <button
                  onclick={() => (pendingDelete = r)}
                  class="text-red-600 hover:underline text-xs"
                >delete</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}

    <!-- Pagination -->
    {#if filtered.length > 0}
      <div class="flex flex-wrap items-center justify-between gap-3 mt-5 pt-4 border-t border-slate-100">
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
            >Prev</button>
            {#each pageWindowed as p}
              {#if p === null}
                <span class="px-1.5 text-slate-400 select-none">…</span>
              {:else}
                <button
                  type="button"
                  onclick={() => (page = p)}
                  class="w-8 h-8 text-sm rounded-lg border {page === p ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-300 text-slate-600 hover:bg-slate-50'}"
                >{p}</button>
              {/if}
            {/each}
            <button
              type="button"
              onclick={() => (page = Math.min(pageCount, page + 1))}
              disabled={page >= pageCount}
              class="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >Next</button>
          </div>
        {/if}
      </div>
    {/if}
  </section>
</div>

<svelte:window onkeydown={onViewerKey} />

<!-- Full-size image viewer with rotation controls -->
{#if viewerUrl || viewerLoading}
  <div
    role="presentation"
    class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    onclick={closeViewer}
  >
    <!-- Caption -->
    {#if viewerReceipt}
      <div class="absolute top-4 left-1/2 -translate-x-1/2 text-white/90 text-sm flex items-center gap-2">
        <span class="tabular-nums">{viewerIndex + 1} / {orderedReceipts.length}</span>
        {#if viewerReceipt.merchant}
          <span class="text-white/50">·</span>
          <span class="truncate max-w-[40vw]">{viewerReceipt.merchant}</span>
        {/if}
      </div>
    {/if}

    <!-- Rotation controls (images only) -->
    {#if viewerReceipt && !viewerIsPdf}
      <div
        class="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-black/50 rounded-full px-4 py-2"
        role="presentation"
        onclick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          aria-label="Rotate counter-clockwise"
          onclick={() => rotateViewer(-90)}
          disabled={rotatingViewer}
          class="text-white/80 hover:text-white text-xl w-8 h-8 flex items-center justify-center disabled:opacity-40 transition"
        >↺</button>
        <span class="text-white/50 text-xs tabular-nums w-8 text-center">
          {viewerReceipt.rotation ?? 0}°
        </span>
        <button
          type="button"
          aria-label="Rotate clockwise"
          onclick={() => rotateViewer(90)}
          disabled={rotatingViewer}
          class="text-white/80 hover:text-white text-xl w-8 h-8 flex items-center justify-center disabled:opacity-40 transition"
        >↻</button>
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
      >‹</button>
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
        class="max-h-[85vh] max-w-[75vw] rounded-lg shadow-2xl transition-transform duration-300"
        style="transform: rotate({viewerReceipt?.rotation ?? 0}deg)"
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
      >›</button>
    {/if}
  </div>
{/if}

<!-- Edit receipt modal (header + line items + rescan OCR) -->
{#if editReceipt}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    role="dialog"
    aria-modal="true"
    aria-label="Edit receipt"
    tabindex="-1"
    class="fixed inset-0 z-50 bg-black/50 flex items-start justify-center p-4 overflow-y-auto"
    onkeydown={(e) => e.key === "Escape" && closeEdit()}
  >
    <div
      role="presentation"
      class="bg-white rounded-2xl shadow-2xl w-full max-w-lg my-8 p-6 space-y-5"
      onclick={(e) => e.stopPropagation()}
    >
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-lg">Edit receipt</h2>
        <button
          type="button"
          aria-label="Close"
          onclick={closeEdit}
          class="text-slate-400 hover:text-slate-700 text-xl leading-none"
        >&times;</button>
      </div>

      <!-- Header fields -->
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

      <!-- Line items -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium">Line items</span>
          <button
            type="button"
            onclick={addLineItem}
            class="text-xs text-blue-600 hover:underline"
          >+ Add line</button>
        </div>
        {#if editDraft.line_items.length}
          <div class="space-y-1.5">
            <div class="grid grid-cols-[1fr_5rem_5rem_5rem_1.5rem] gap-1 text-xs text-slate-500 px-1">
              <span>Description</span>
              <span class="text-right">Qty</span>
              <span class="text-right">Unit price</span>
              <span class="text-right">Amount</span>
              <span></span>
            </div>
            {#each editDraft.line_items as li, i}
              <div class="grid grid-cols-[1fr_5rem_5rem_5rem_1.5rem] gap-1 items-center">
                <input
                  bind:value={li.description}
                  placeholder="Description"
                  class="rounded border border-slate-300 p-1.5 text-sm"
                />
                <input
                  bind:value={li.quantity}
                  placeholder="—"
                  type="number"
                  step="0.001"
                  class="rounded border border-slate-300 p-1.5 text-sm text-right"
                />
                <input
                  bind:value={li.unit_price}
                  placeholder="—"
                  type="number"
                  step="0.01"
                  class="rounded border border-slate-300 p-1.5 text-sm text-right"
                />
                <input
                  bind:value={li.amount}
                  placeholder="—"
                  type="number"
                  step="0.01"
                  class="rounded border border-slate-300 p-1.5 text-sm text-right"
                />
                <button
                  type="button"
                  onclick={() => removeLineItem(i)}
                  class="text-red-400 hover:text-red-600 text-lg leading-none text-center"
                  aria-label="Remove line item"
                >&times;</button>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-slate-400">No line items. Click "+ Add line" to add one.</p>
        {/if}
      </div>

      <!-- Re-scan OCR -->
      <div class="border-t pt-4">
        <div class="flex items-center gap-3">
          <button
            type="button"
            onclick={onRescan}
            disabled={rescanning || !editReceipt.image_path}
            class="text-sm px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50
                   disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {rescanning ? "Scanning…" : "Re-scan OCR"}
          </button>
          <span class="text-xs text-slate-400">Re-reads the stored image</span>
        </div>

        {#if rescanResult}
          <div class="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-2 text-sm">
            <div class="font-medium text-blue-800">New OCR result</div>
            <div class="text-slate-700 text-xs space-y-0.5">
              {#if rescanResult.parsed.merchant}
                <div>Merchant: <strong>{rescanResult.parsed.merchant}</strong></div>
              {/if}
              {#if rescanResult.parsed.purchase_date}
                <div>Date: <strong>{rescanResult.parsed.purchase_date}</strong></div>
              {/if}
              {#if rescanResult.parsed.total != null}
                <div>Total: <strong>{rescanResult.parsed.total}</strong></div>
              {/if}
              {#if rescanResult.parsed.currency}
                <div>Currency: <strong>{rescanResult.parsed.currency}</strong></div>
              {/if}
              {#if rescanResult.parsed.line_items?.length}
                <div>{rescanResult.parsed.line_items.length} line item(s) detected</div>
              {/if}
            </div>
            <div class="flex gap-2">
              <button
                type="button"
                onclick={applyRescanResult}
                class="text-xs bg-blue-600 text-white px-3 py-1 rounded-lg hover:bg-blue-700"
              >Apply values</button>
              <button
                type="button"
                onclick={() => (rescanResult = null)}
                class="text-xs px-3 py-1 rounded-lg border hover:bg-slate-50"
              >Dismiss</button>
            </div>
          </div>
        {/if}
      </div>

      <!-- Save / cancel -->
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
        >Cancel</button>
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
    ? `"${pendingDelete.merchant || "Untitled"}" will be permanently removed. This can't be undone.`
    : ""}
  confirmLabel={deleting ? "Deleting…" : "Delete"}
  onconfirm={confirmDelete}
  oncancel={() => (pendingDelete = null)}
/>

<style>
  /* Indeterminate progress bar while OCR runs server-side. */
  .indeterminate {
    animation: indeterminate 1.1s ease-in-out infinite;
  }
  @keyframes indeterminate {
    0%   { margin-left: -40%; }
    100% { margin-left: 100%; }
  }
</style>
