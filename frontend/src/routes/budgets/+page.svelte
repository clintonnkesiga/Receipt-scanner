<script>
  import { onMount } from "svelte";
  import { listBudgets, createBudget, updateBudget, deleteBudget, listCategories, getBudgetUsage } from "$lib/api";
  import { toasts } from "$lib/toast.js";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

  let budgets = $state([]);
  let usageMap = $state({});
  let categories = $state([]);
  let loading = $state(true);

  // Month picker — defaults to current YYYY-MM
  const todayYM = new Date().toISOString().slice(0, 7);
  let selectedMonth = $state(todayYM);
  const isCurrentMonth = $derived(selectedMonth === todayYM);

  const ALL_KEY = "__all__";

  async function load() {
    loading = true;
    try {
      const [bs, cats, usage] = await Promise.all([
        listBudgets(),
        listCategories(),
        getBudgetUsage(selectedMonth),
      ]);
      budgets = bs;
      categories = cats.map((c) => c.name);
      const map = {};
      for (const u of usage) {
        const key = u.budget.category ?? ALL_KEY;
        map[key] = { spent: u.spent, pct: u.pct ?? 0 };
      }
      usageMap = map;
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load budgets");
    } finally {
      loading = false;
    }
  }

  async function changeMonth(delta) {
    const [y, m] = selectedMonth.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    const next = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    // Don't go into the future
    if (next > todayYM) return;
    selectedMonth = next;
    await load();
  }

  onMount(load);

  // ── Create form ──────────────────────────────────────────────────────────────
  let showCreate = $state(false);
  let creating = $state(false);
  let newBudget = $state({ category: "", monthly_limit: "", currency: "" });

  async function onCreateSave() {
    if (!newBudget.monthly_limit || Number(newBudget.monthly_limit) <= 0) {
      toasts.error("Monthly limit must be greater than 0");
      return;
    }
    creating = true;
    try {
      await createBudget({
        category: newBudget.category || null,
        monthly_limit: Number(newBudget.monthly_limit),
        currency: newBudget.currency || null,
      });
      newBudget = { category: "", monthly_limit: "", currency: "" };
      showCreate = false;
      await load();
      toasts.success("Budget created");
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not create budget");
    } finally {
      creating = false;
    }
  }

  // ── Edit ─────────────────────────────────────────────────────────────────────
  let editId = $state(null);
  let editDraft = $state({ monthly_limit: "", currency: "" });
  let editSaving = $state(false);

  function startEdit(b) {
    editId = b.id;
    editDraft = {
      monthly_limit: String(b.monthly_limit),
      currency: b.currency ?? "",
    };
  }

  function cancelEdit() { editId = null; }

  async function onEditSave() {
    if (!editDraft.monthly_limit || Number(editDraft.monthly_limit) <= 0) {
      toasts.error("Monthly limit must be greater than 0");
      return;
    }
    editSaving = true;
    try {
      await updateBudget(editId, {
        monthly_limit: Number(editDraft.monthly_limit),
        currency: editDraft.currency || null,
      });
      editId = null;
      await load();
      toasts.success("Budget updated");
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not update budget");
    } finally {
      editSaving = false;
    }
  }

  // ── Delete ───────────────────────────────────────────────────────────────────
  let pendingDelete = $state(null);
  let deleting = $state(false);

  async function confirmDelete() {
    if (!pendingDelete) return;
    deleting = true;
    try {
      await deleteBudget(pendingDelete.id);
      pendingDelete = null;
      await load();
      toasts.success("Budget deleted");
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not delete budget");
    } finally {
      deleting = false;
    }
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────
  const fmt = (n) => Number(n || 0).toLocaleString();

  function usageFor(b) {
    const key = b.category ?? ALL_KEY;
    return usageMap[key] ?? { spent: 0, pct: 0 };
  }

  function barColor(pct) {
    if (pct >= 100) return "bg-red-500";
    if (pct >= 80)  return "bg-amber-400";
    return "bg-emerald-400";
  }

  // Categories not yet covered by a budget
  const usedCategories = $derived(
    new Set(budgets.filter((b) => b.category != null).map((b) => b.category)),
  );
  const availableCategories = $derived(
    categories.filter((c) => !usedCategories.has(c)),
  );
  const hasOverallBudget = $derived(budgets.some((b) => b.category == null));
</script>

<div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl font-semibold">Budgets</h1>
    <div class="flex items-center gap-2">
      <!-- Month navigator -->
      <div class="flex items-center gap-1 bg-white border rounded-lg px-2 py-1 text-sm">
        <button
          type="button"
          onclick={() => changeMonth(-1)}
          class="px-1.5 py-0.5 rounded hover:bg-slate-100 text-slate-500"
          aria-label="Previous month"
        >‹</button>
        <span class="font-medium w-24 text-center tabular-nums">
          {new Date(selectedMonth + "-15").toLocaleDateString(undefined, { month: "short", year: "numeric" })}
        </span>
        <button
          type="button"
          onclick={() => changeMonth(1)}
          disabled={isCurrentMonth}
          class="px-1.5 py-0.5 rounded hover:bg-slate-100 text-slate-500 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Next month"
        >›</button>
      </div>
      {#if !isCurrentMonth}
        <button
          type="button"
          onclick={async () => { selectedMonth = todayYM; await load(); }}
          class="text-xs text-blue-600 hover:underline"
        >Back to current</button>
      {/if}
      {#if !showCreate}
        <button
          type="button"
          onclick={() => (showCreate = true)}
          class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
        >+ New budget</button>
      {/if}
    </div>
  </div>

  <!-- New budget form -->
  {#if showCreate}
    <section class="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-400">
      <h2 class="font-semibold mb-4">New budget</h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <label class="text-sm">
          <span class="font-medium block mb-1">Category <span class="font-normal text-slate-400">(blank = all spending)</span></span>
          <select bind:value={newBudget.category} class="w-full rounded-lg border border-slate-300 p-2 capitalize">
            {#if !hasOverallBudget}<option value="">— all categories —</option>{/if}
            {#each availableCategories as c}<option value={c}>{c}</option>{/each}
          </select>
        </label>
        <label class="text-sm">
          <span class="font-medium block mb-1">Monthly limit</span>
          <input type="number" step="0.01" min="0.01" bind:value={newBudget.monthly_limit} placeholder="e.g. 500" class="w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="text-sm">
          <span class="font-medium block mb-1">Currency</span>
          <input bind:value={newBudget.currency} placeholder="e.g. USD" maxlength="8" class="w-full rounded-lg border border-slate-300 p-2" />
        </label>
      </div>
      <div class="flex gap-3 mt-4">
        <button type="button" onclick={onCreateSave} disabled={creating} class="bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-emerald-700 disabled:opacity-50">
          {creating ? "Saving…" : "Save budget"}
        </button>
        <button type="button" onclick={() => { showCreate = false; newBudget = { category: "", monthly_limit: "", currency: "" }; }} class="px-4 py-2 rounded-lg border text-sm hover:bg-slate-50">Cancel</button>
      </div>
    </section>
  {/if}

  <!-- Budget list -->
  {#if loading}
    <div class="text-sm text-slate-400">Loading…</div>
  {:else if budgets.length === 0}
    <div class="bg-white rounded-xl shadow-sm p-8 text-center text-slate-500">
      No budgets yet. Create one above to start tracking your spending against limits.
    </div>
  {:else}
    <section class="bg-white rounded-xl shadow-sm divide-y">
      {#each budgets as b (b.id)}
        {@const usage = usageFor(b)}
        {@const pct = Math.min(100, Number(usage.pct ?? 0))}
        {@const over = Number(usage.spent) > Number(b.monthly_limit)}
        <div class="p-5">
          {#if editId === b.id}
            <!-- Inline edit -->
            <div class="flex flex-wrap items-end gap-3">
              <div class="text-sm font-medium capitalize min-w-[8rem]">
                {b.category ?? "All categories"}
              </div>
              <label class="text-sm">
                <span class="font-medium block mb-1">Monthly limit</span>
                <input type="number" step="0.01" bind:value={editDraft.monthly_limit} class="rounded-lg border border-slate-300 p-1.5 w-32" />
              </label>
              <label class="text-sm">
                <span class="font-medium block mb-1">Currency</span>
                <input bind:value={editDraft.currency} maxlength="8" placeholder="e.g. USD" class="rounded-lg border border-slate-300 p-1.5 w-24" />
              </label>
              <div class="flex gap-2 pb-0.5">
                <button type="button" onclick={onEditSave} disabled={editSaving} class="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
                  {editSaving ? "Saving…" : "Save"}
                </button>
                <button type="button" onclick={cancelEdit} class="px-3 py-1.5 rounded-lg border text-sm hover:bg-slate-50">Cancel</button>
              </div>
            </div>
          {:else}
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-medium capitalize">{b.category ?? "All categories"}</span>
                  {#if b.currency}<span class="text-xs text-slate-400 uppercase">{b.currency}</span>{/if}
                  {#if over}<span class="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full font-medium">Over budget</span>{/if}
                </div>
                <div class="flex items-baseline gap-1 text-sm mb-2">
                  <span class="{over ? 'text-red-600 font-semibold' : 'text-slate-700'}">{fmt(usage.spent)}</span>
                  <span class="text-slate-400">/ {fmt(b.monthly_limit)}
                    {isCurrentMonth ? "this month" : new Date(selectedMonth + "-15").toLocaleDateString(undefined, { month: "short", year: "numeric" })}
                  </span>
                  <span class="text-xs text-slate-400 ml-1">({pct.toFixed(0)}%)</span>
                </div>
                <div class="h-3 rounded-full bg-slate-100 overflow-hidden w-full max-w-sm">
                  <div class="h-full rounded-full transition-[width] duration-500 {barColor(pct)}" style="width:{pct}%"></div>
                </div>
              </div>
              <div class="flex gap-3 text-sm shrink-0">
                <button type="button" onclick={() => startEdit(b)} class="text-slate-600 hover:underline">Edit</button>
                <button type="button" onclick={() => (pendingDelete = b)} class="text-red-600 hover:underline">Delete</button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </section>
  {/if}
</div>

<ConfirmDialog
  open={pendingDelete != null}
  danger
  busy={deleting}
  title="Delete this budget?"
  message={pendingDelete ? `The "${pendingDelete.category ?? "all categories"}" budget will be removed. Your receipts are not affected.` : ""}
  confirmLabel={deleting ? "Deleting…" : "Delete"}
  onconfirm={confirmDelete}
  oncancel={() => (pendingDelete = null)}
/>
