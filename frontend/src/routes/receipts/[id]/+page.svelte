<script>
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import {
    getReceipt,
    getReceiptImageUrl,
    listCategories,
    deleteReceipt,
    restoreReceipt,
    permanentlyDeleteReceipt,
    updateReceipt,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import ReceiptEditModal from "$lib/components/ReceiptEditModal.svelte";
  import ZoomableImage from "$lib/components/ZoomableImage.svelte";

  const id = $derived(Number($page.params.id));

  let receipt = $state(null);
  let categories = $state([]);
  let loading = $state(true);
  let loadError = $state("");

  let imageUrl = $state(null);
  let imageIsPdf = $state(false);

  const isElevated = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );
  const isTrashed = $derived(receipt?.deleted_at != null);

  // Load (or reload) the receipt whenever the id changes.
  $effect(() => {
    const rid = id;
    let active = true;
    let objectUrl = null;
    loading = true;
    loadError = "";
    receipt = null;
    imageUrl = null;

    getReceipt(rid)
      .then(async (r) => {
        if (!active) return;
        receipt = r;
        imageIsPdf = !!r.image_path && r.image_path.toLowerCase().endsWith(".pdf");
        if (r.image_path && !imageIsPdf) {
          try {
            const u = await getReceiptImageUrl(r.id);
            if (!active) { URL.revokeObjectURL(u); return; }
            objectUrl = u;
            imageUrl = u;
          } catch {
            /* image is optional on the detail page */
          }
        }
      })
      .catch((e) => {
        if (active) loadError = e instanceof Error ? e.message : "Could not load receipt";
      })
      .finally(() => {
        if (active) loading = false;
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  });

  // Categories are only needed for the edit modal; load once.
  $effect(() => {
    listCategories()
      .then((cs) => (categories = cs.map((c) => c.name)))
      .catch(() => {});
  });

  // ── Edit ──────────────────────────────────────────────────────────────────
  let editing = $state(false);
  function onEditSaved(updated) {
    receipt = updated;
    editing = false;
  }

  // ── Rotate (persisted like the list viewer) ─────────────────────────────────
  let rotating = $state(false);
  async function rotate(delta) {
    if (!receipt || rotating) return;
    const newRotation = ((((receipt.rotation ?? 0) + delta) % 360) + 360) % 360;
    rotating = true;
    try {
      receipt = await updateReceipt(receipt.id, { rotation: newRotation });
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not rotate image");
    } finally {
      rotating = false;
    }
  }

  // ── Delete / restore / purge ────────────────────────────────────────────────
  let pendingTrash = $state(false);
  let pendingPurge = $state(false);
  let busy = $state(false);

  async function doTrash() {
    busy = true;
    try {
      await deleteReceipt(receipt.id);
      toasts.success("Moved to trash");
      goto("/receipts");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not delete receipt");
      busy = false;
      pendingTrash = false;
    }
  }

  async function doRestore() {
    busy = true;
    try {
      receipt = await restoreReceipt(receipt.id);
      toasts.success("Receipt restored");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not restore receipt");
    } finally {
      busy = false;
    }
  }

  async function doPurge() {
    busy = true;
    try {
      await permanentlyDeleteReceipt(receipt.id);
      toasts.success("Receipt permanently deleted");
      goto("/trash");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not delete receipt");
      busy = false;
      pendingPurge = false;
    }
  }

  function badgeClass(category) {
    return category === "fuel"
      ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
      : category === "grocery"
        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
        : "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200";
  }

  const money = (v, cur) =>
    v != null ? `${cur || ""} ${Number(v).toLocaleString()}`.trim() : "—";
</script>

<div class="w-full px-6 py-8 max-w-3xl mx-auto space-y-6">
  <a href="/receipts" class="text-sm text-blue-600 dark:text-blue-400 hover:underline">← Back to receipts</a>

  {#if loading}
    <p class="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
  {:else if loadError}
    <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-8 text-center space-y-3">
      <div class="text-4xl">🧾</div>
      <h1 class="text-lg font-semibold">{loadError}</h1>
      <p class="text-sm text-slate-500 dark:text-slate-400">
        This receipt may have been permanently deleted or never existed.
      </p>
      <a href="/receipts" class="inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline">Go to receipts</a>
    </div>
  {:else if receipt}
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold">{receipt.merchant || "Untitled receipt"}</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          {receipt.purchase_date || "No date"}
          {#if receipt.category}
            · <span class="text-xs rounded-full px-2 py-0.5 capitalize {badgeClass(receipt.category)}">{receipt.category}</span>
          {/if}
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        {#if isTrashed}
          <span class="text-xs rounded-full px-2 py-1 bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">In Trash</span>
          <button onclick={doRestore} disabled={busy} class="text-sm px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">Restore</button>
          <button onclick={() => (pendingPurge = true)} disabled={busy} class="text-sm px-3 py-1.5 rounded-lg border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50">Delete permanently</button>
        {:else}
          <button onclick={() => (editing = true)} class="text-sm px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700">Edit</button>
          <button onclick={() => (pendingTrash = true)} class="text-sm px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-red-600 hover:bg-red-50 dark:hover:bg-red-950">Move to Trash</button>
        {/if}
      </div>
    </div>

    <div class="grid gap-6 md:grid-cols-2">
      <!-- Image -->
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 flex flex-col items-center gap-3">
        {#if imageIsPdf && receipt.image_path}
          <iframe src={`/api/receipts/${receipt.id}/image`} title="Receipt PDF" class="w-full h-96 rounded-lg border border-slate-200 dark:border-slate-700"></iframe>
        {:else if imageUrl}
          <ZoomableImage
            src={imageUrl}
            alt={receipt.merchant || "Receipt"}
            thumbClass="max-h-96 rounded-lg border border-slate-200 dark:border-slate-700"
          />
          <div class="flex items-center gap-2 text-slate-500 dark:text-slate-400">
            <button type="button" aria-label="Rotate counter-clockwise" onclick={() => rotate(-90)} disabled={rotating} class="w-8 h-8 rounded-full hover:bg-slate-100 dark:hover:bg-slate-700 text-lg disabled:opacity-40">↺</button>
            <span class="text-xs tabular-nums w-10 text-center">{receipt.rotation ?? 0}°</span>
            <button type="button" aria-label="Rotate clockwise" onclick={() => rotate(90)} disabled={rotating} class="w-8 h-8 rounded-full hover:bg-slate-100 dark:hover:bg-slate-700 text-lg disabled:opacity-40">↻</button>
          </div>
        {:else}
          <div class="h-48 flex items-center justify-center text-slate-300 text-sm">No image</div>
        {/if}
      </div>

      <!-- Fields -->
      <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-5 space-y-3 text-sm">
        <dl class="grid grid-cols-3 gap-y-2.5">
          <dt class="text-slate-500 dark:text-slate-400">Total</dt>
          <dd class="col-span-2 font-semibold tabular-nums">{money(receipt.total, receipt.currency)}</dd>

          <dt class="text-slate-500 dark:text-slate-400">Tax / VAT</dt>
          <dd class="col-span-2 tabular-nums">{money(receipt.tax_amount, receipt.currency)}</dd>

          <dt class="text-slate-500 dark:text-slate-400">Net</dt>
          <dd class="col-span-2 tabular-nums">{money(receipt.net_amount, receipt.currency)}</dd>

          {#if receipt.fx_rate != null}
            <dt class="text-slate-500 dark:text-slate-400">FX rate</dt>
            <dd class="col-span-2 tabular-nums">{receipt.fx_rate}</dd>
          {/if}

          {#if isElevated}
            <dt class="text-slate-500 dark:text-slate-400">Owner</dt>
            <dd class="col-span-2">{receipt.owner_email || "—"}</dd>
          {/if}

          <dt class="text-slate-500 dark:text-slate-400">Added</dt>
          <dd class="col-span-2">{receipt.created_at ? new Date(receipt.created_at).toLocaleString() : "—"}</dd>
        </dl>

        {#if receipt.line_items?.length}
          <div class="border-t dark:border-slate-700 pt-3">
            <div class="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">Line items</div>
            <table class="w-full text-xs">
              <tbody>
                {#each receipt.line_items as li}
                  <tr class="border-b last:border-0 border-slate-100 dark:border-slate-700">
                    <td class="py-1">{li.description || "—"}</td>
                    <td class="py-1 text-right tabular-nums text-slate-500 dark:text-slate-400">{li.quantity ?? ""}</td>
                    <td class="py-1 text-right tabular-nums">{li.amount != null ? Number(li.amount).toLocaleString() : "—"}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>

    {#if receipt.raw_ocr_text}
      <details class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-5 text-sm">
        <summary class="cursor-pointer text-slate-500 dark:text-slate-400">Raw OCR text</summary>
        <pre class="mt-2 whitespace-pre-wrap bg-slate-50 dark:bg-slate-900 p-3 rounded-lg text-xs">{receipt.raw_ocr_text}</pre>
      </details>
    {/if}
  {/if}
</div>

<ReceiptEditModal
  receipt={editing ? receipt : null}
  {categories}
  open={editing}
  onclose={() => (editing = false)}
  onsaved={onEditSaved}
/>

<ConfirmDialog
  open={pendingTrash}
  busy={busy}
  title="Move this receipt to Trash?"
  message={receipt ? `"${receipt.merchant || "Untitled"}" will be moved to the Trash. You can restore it later.` : ""}
  confirmLabel={busy ? "Moving…" : "Move to Trash"}
  onconfirm={doTrash}
  oncancel={() => (pendingTrash = false)}
/>

<ConfirmDialog
  open={pendingPurge}
  danger
  busy={busy}
  title="Permanently delete this receipt?"
  message={receipt ? `"${receipt.merchant || "Untitled"}" and its image will be deleted for good. This can't be undone.` : ""}
  confirmLabel={busy ? "Deleting…" : "Delete permanently"}
  onconfirm={doPurge}
  oncancel={() => (pendingPurge = false)}
/>
