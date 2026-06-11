<script>
  import { onMount } from "svelte";
  import { listTrash, restoreReceipt, permanentlyDeleteReceipt } from "$lib/api";
  import { toasts } from "$lib/toast.js";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  let items = $state([]);
  let total = $state(0);
  let loading = $state(true);
  let busyId = $state(null);

  let pendingPurge = $state(null);
  let purging = $state(false);

  async function refresh() {
    loading = true;
    try {
      const data = await listTrash({ limit: 100 });
      items = data.items;
      total = data.total;
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load trash");
    } finally {
      loading = false;
    }
  }

  onMount(refresh);

  async function onRestore(r) {
    busyId = r.id;
    try {
      await restoreReceipt(r.id);
      items = items.filter((i) => i.id !== r.id);
      total -= 1;
      toasts.success("Receipt restored");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not restore receipt");
    } finally {
      busyId = null;
    }
  }

  async function onPurge() {
    if (!pendingPurge) return;
    purging = true;
    try {
      await permanentlyDeleteReceipt(pendingPurge.id);
      items = items.filter((i) => i.id !== pendingPurge.id);
      total -= 1;
      pendingPurge = null;
      toasts.success("Receipt permanently deleted");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not delete receipt");
    } finally {
      purging = false;
    }
  }

  const money = (v, cur) =>
    v != null ? `${cur || ""} ${Number(v).toLocaleString()}`.trim() : "—";
</script>

<div class="w-full px-6 py-8 space-y-6">
  <div>
    <h1 class="text-2xl font-semibold">Trash</h1>
    <p class="text-sm text-slate-500 dark:text-slate-400">
      Deleted receipts are kept here until you restore them or delete them for good.
    </p>
  </div>

  <section class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-5">
    {#if loading}
      <p class="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
    {:else if total === 0}
      <div class="text-center py-10 space-y-2">
        <div class="text-4xl">🗑️</div>
        <p class="text-sm text-slate-500 dark:text-slate-400">The Trash is empty.</p>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left text-slate-500 dark:text-slate-400 border-b dark:border-slate-700">
          <tr>
            <th class="py-2">Merchant</th>
            <th>Date</th>
            <th class="text-right">Total</th>
            <th class="text-right">Deleted</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each items as r (r.id)}
            <tr class="border-b last:border-0 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50">
              <td class="py-2">
                <a href={`/receipts/${r.id}`} class="text-blue-600 dark:text-blue-400 hover:underline">{r.merchant || "Untitled"}</a>
              </td>
              <td class="text-slate-500 dark:text-slate-400">{r.purchase_date || "—"}</td>
              <td class="text-right tabular-nums">{money(r.total, r.currency)}</td>
              <td class="text-right tabular-nums text-xs text-slate-400">
                {r.deleted_at ? new Date(r.deleted_at).toLocaleDateString() : "—"}
              </td>
              <td class="text-right space-x-3 whitespace-nowrap">
                <button onclick={() => onRestore(r)} disabled={busyId === r.id} class="text-emerald-600 dark:text-emerald-400 hover:underline text-xs disabled:opacity-50">restore</button>
                <button onclick={() => (pendingPurge = r)} class="text-red-600 hover:underline text-xs">delete forever</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
</div>

<ConfirmDialog
  open={pendingPurge != null}
  danger
  busy={purging}
  title="Permanently delete this receipt?"
  message={pendingPurge ? `"${pendingPurge.merchant || "Untitled"}" and its image will be deleted for good. This can't be undone.` : ""}
  confirmLabel={purging ? "Deleting…" : "Delete permanently"}
  onconfirm={onPurge}
  oncancel={() => (pendingPurge = null)}
/>
