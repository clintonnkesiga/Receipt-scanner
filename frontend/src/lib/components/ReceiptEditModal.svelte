<script>
  import { updateReceipt, rescanReceipt } from "$lib/api";
  import { toasts } from "$lib/toast.js";

  // Shared receipt editor used by both the receipts list and the detail page.
  // Controlled component: parent owns `receipt` + `open` and reacts to `onsaved`.
  let { receipt = null, categories = [], open = false, onclose, onsaved } = $props();

  function blankDraft() {
    return {
      merchant: "", purchase_date: "", total: "", currency: "UGX", category: "",
      tax_amount: "", net_amount: "", fx_rate: "", line_items: [],
    };
  }

  let editDraft = $state(blankDraft());
  let editSaving = $state(false);
  let rescanResult = $state(null);
  let rescanning = $state(false);

  // Re-seed the draft whenever the modal opens for a different receipt.
  let lastKey = null;
  $effect(() => {
    if (open && receipt) {
      if (receipt.id !== lastKey) {
        lastKey = receipt.id;
        rescanResult = null;
        editDraft = {
          merchant:      receipt.merchant      ?? "",
          purchase_date: receipt.purchase_date ?? "",
          total:         receipt.total      != null ? String(receipt.total)      : "",
          currency:      receipt.currency      ?? "UGX",
          category:      receipt.category      ?? "",
          tax_amount:    receipt.tax_amount != null ? String(receipt.tax_amount) : "",
          net_amount:    receipt.net_amount != null ? String(receipt.net_amount) : "",
          fx_rate:       receipt.fx_rate    != null ? String(receipt.fx_rate)    : "",
          line_items: (receipt.line_items ?? []).map((li) => ({
            description: li.description  ?? "",
            quantity:    li.quantity   != null ? String(li.quantity)   : "",
            unit_price:  li.unit_price != null ? String(li.unit_price) : "",
            amount:      li.amount     != null ? String(li.amount)     : "",
          })),
        };
      }
    } else if (!open) {
      lastKey = null;
    }
  });

  function addLineItem() {
    editDraft.line_items.push({ description: "", quantity: "", unit_price: "", amount: "" });
  }
  function removeLineItem(i) { editDraft.line_items.splice(i, 1); }

  async function onRescan() {
    if (!receipt) return;
    rescanning = true;
    rescanResult = null;
    try {
      rescanResult = await rescanReceipt(receipt.id);
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
    if (p.tax_amount != null) editDraft.tax_amount = String(p.tax_amount);
    if (p.net_amount != null) editDraft.net_amount = String(p.net_amount);
    if (p.line_items?.length) {
      editDraft.line_items = p.line_items.map((li) => ({
        description: li.description ?? "",
        quantity:    li.quantity   != null ? String(li.quantity)   : "",
        unit_price:  li.unit_price != null ? String(li.unit_price) : "",
        amount:      li.amount     != null ? String(li.amount)     : "",
      }));
    }
    rescanResult = null;
    toasts.success("OCR values applied — review and save");
  }

  async function onEditSave() {
    if (!receipt) return;
    editSaving = true;
    try {
      const patch = {
        merchant:      editDraft.merchant      || null,
        purchase_date: editDraft.purchase_date || null,
        total:         editDraft.total      !== "" ? Number(editDraft.total)      : null,
        currency:      editDraft.currency      || null,
        category:      editDraft.category      || null,
        tax_amount:    editDraft.tax_amount !== "" ? Number(editDraft.tax_amount) : null,
        net_amount:    editDraft.net_amount !== "" ? Number(editDraft.net_amount) : null,
        fx_rate:       editDraft.fx_rate    !== "" ? Number(editDraft.fx_rate)    : null,
        line_items: editDraft.line_items.map((li) => ({
          description: li.description || null,
          quantity:    li.quantity   !== "" ? Number(li.quantity)   : null,
          unit_price:  li.unit_price !== "" ? Number(li.unit_price) : null,
          amount:      li.amount     !== "" ? Number(li.amount)     : null,
        })),
      };
      const updated = await updateReceipt(receipt.id, patch);
      toasts.success("Receipt updated");
      onsaved?.(updated);
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not update receipt");
    } finally {
      editSaving = false;
    }
  }
</script>

{#if open && receipt}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div role="dialog" aria-modal="true" aria-label="Edit receipt" tabindex="-1" class="fixed inset-0 z-50 bg-black/50 flex items-start justify-center p-4 overflow-y-auto" onkeydown={(e) => e.key === "Escape" && onclose?.()}>
    <div role="presentation" class="bg-white dark:bg-slate-800 dark:text-slate-100 rounded-2xl shadow-2xl w-full max-w-lg my-8 p-6 space-y-5" onclick={(e) => e.stopPropagation()}>
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-lg">Edit receipt</h2>
        <button type="button" aria-label="Close" onclick={() => onclose?.()} class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xl leading-none">&times;</button>
      </div>

      <!-- Header fields -->
      <div class="grid grid-cols-1 gap-3">
        <label class="text-sm"><span class="font-medium block mb-1">Merchant</span>
          <input bind:value={editDraft.merchant} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" placeholder="e.g. Walmart" />
        </label>
        <label class="text-sm"><span class="font-medium block mb-1">Date</span>
          <input type="date" bind:value={editDraft.purchase_date} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-sm"><span class="font-medium block mb-1">Total</span>
            <input type="number" step="0.01" bind:value={editDraft.total} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" placeholder="0.00" />
          </label>
          <label class="text-sm"><span class="font-medium block mb-1">Currency</span>
            <input bind:value={editDraft.currency} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" placeholder="UGX" maxlength="8" />
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-sm"><span class="font-medium block mb-1">Tax / VAT</span>
            <input type="number" step="0.01" bind:value={editDraft.tax_amount} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" placeholder="0.00" />
          </label>
          <label class="text-sm"><span class="font-medium block mb-1">Net amount</span>
            <input type="number" step="0.01" bind:value={editDraft.net_amount} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" placeholder="0.00" />
          </label>
        </div>
        <label class="text-sm">
          <span class="font-medium block mb-1">FX rate <span class="font-normal text-slate-400">(to base currency)</span></span>
          <input type="number" step="0.000001" bind:value={editDraft.fx_rate} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2" placeholder="e.g. 3700" />
        </label>
        <label class="text-sm"><span class="font-medium block mb-1">Category</span>
          <select bind:value={editDraft.category} class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2 capitalize">
            <option value="">— uncategorized —</option>
            {#each categories as c}<option value={c}>{c}</option>{/each}
          </select>
        </label>
      </div>

      <!-- Line items -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium">Line items</span>
          <button type="button" onclick={addLineItem} class="text-xs text-blue-600 dark:text-blue-400 hover:underline">+ Add line</button>
        </div>
        {#if editDraft.line_items.length}
          <div class="space-y-1.5">
            <div class="grid grid-cols-[1fr_5rem_5rem_5rem_1.5rem] gap-1 text-xs text-slate-500 dark:text-slate-400 px-1">
              <span>Description</span><span class="text-right">Qty</span><span class="text-right">Unit price</span><span class="text-right">Amount</span><span></span>
            </div>
            {#each editDraft.line_items as li, i}
              <div class="grid grid-cols-[1fr_5rem_5rem_5rem_1.5rem] gap-1 items-center">
                <input bind:value={li.description} placeholder="Description" class="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-1.5 text-sm" />
                <input bind:value={li.quantity} placeholder="—" type="number" step="0.001" class="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-1.5 text-sm text-right" />
                <input bind:value={li.unit_price} placeholder="—" type="number" step="0.01" class="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-1.5 text-sm text-right" />
                <input bind:value={li.amount} placeholder="—" type="number" step="0.01" class="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-1.5 text-sm text-right" />
                <button type="button" onclick={() => removeLineItem(i)} class="text-red-400 hover:text-red-600 text-lg leading-none text-center" aria-label="Remove">&times;</button>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-slate-400">No line items. Click "+ Add line" to add one.</p>
        {/if}
      </div>

      <!-- Re-scan OCR -->
      <div class="border-t dark:border-slate-700 pt-4">
        <div class="flex items-center gap-3">
          <button type="button" onclick={onRescan} disabled={rescanning || !receipt.image_path} class="text-sm px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed">
            {rescanning ? "Scanning…" : "Re-scan OCR"}
          </button>
          <span class="text-xs text-slate-400">Re-reads the stored image</span>
        </div>
        {#if rescanResult}
          <div class="mt-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-900 rounded-lg p-3 space-y-2 text-sm">
            <div class="font-medium text-blue-800 dark:text-blue-300">New OCR result</div>
            <div class="text-slate-700 dark:text-slate-300 text-xs space-y-0.5">
              {#if rescanResult.parsed.merchant}<div>Merchant: <strong>{rescanResult.parsed.merchant}</strong></div>{/if}
              {#if rescanResult.parsed.purchase_date}<div>Date: <strong>{rescanResult.parsed.purchase_date}</strong></div>{/if}
              {#if rescanResult.parsed.total != null}<div>Total: <strong>{rescanResult.parsed.total}</strong></div>{/if}
              {#if rescanResult.parsed.tax_amount != null}<div>Tax: <strong>{rescanResult.parsed.tax_amount}</strong></div>{/if}
              {#if rescanResult.parsed.line_items?.length}<div>{rescanResult.parsed.line_items.length} line item(s) detected</div>{/if}
            </div>
            <div class="flex gap-2">
              <button type="button" onclick={applyRescanResult} class="text-xs bg-blue-600 text-white px-3 py-1 rounded-lg hover:bg-blue-700">Apply values</button>
              <button type="button" onclick={() => (rescanResult = null)} class="text-xs px-3 py-1 rounded-lg border dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700">Dismiss</button>
            </div>
          </div>
        {/if}
      </div>

      <div class="flex gap-3 pt-1">
        <button type="button" onclick={onEditSave} disabled={editSaving} class="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {editSaving ? "Saving…" : "Save changes"}
        </button>
        <button type="button" onclick={() => onclose?.()} class="px-4 py-2 rounded-lg border dark:border-slate-600 text-sm hover:bg-slate-50 dark:hover:bg-slate-700">Cancel</button>
      </div>
    </div>
  </div>
{/if}
