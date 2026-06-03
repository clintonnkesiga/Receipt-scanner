<script>
  import { onMount } from "svelte";
  import { getStats } from "$lib/api";
  import { requireUser } from "$lib/guard";

  let user = $state(null);
  let ready = $state(false);
  let stats = $state(null);
  let error = $state("");

  const fmt = (n) => Number(n || 0).toLocaleString();

  // Bar scaling helpers (largest value in a group = full width).
  const maxCategory = $derived(
    Math.max(1, ...(stats?.by_category ?? []).map((c) => Number(c.total) || 0)),
  );
  const maxMonth = $derived(
    Math.max(1, ...(stats?.by_month ?? []).map((m) => Number(m.total) || 0)),
  );
  const multiCurrency = $derived((stats?.by_currency ?? []).length > 1);

  function catColor(category) {
    return category === "fuel"
      ? "bg-amber-400"
      : category === "grocery"
        ? "bg-emerald-400"
        : "bg-slate-400";
  }

  onMount(async () => {
    user = await requireUser();
    if (!user) return;
    try {
      stats = await getStats();
      ready = true;
    } catch (e) {
      error = e.message;
      ready = true;
    }
  });
</script>

{#if ready}
  <div class="min-h-screen bg-slate-50 text-slate-800">
    <header class="bg-white border-b">
      <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
        <a href="/" class="text-sm text-blue-600 hover:underline">← Back</a>
        <h1 class="font-semibold">Dashboard</h1>
        <span class="text-sm text-slate-500">{user?.email}</span>
      </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {#if error}
        <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
          {error}
        </div>
      {/if}

      {#if stats}
        {#if stats.receipt_count === 0}
          <div class="bg-white rounded-xl shadow-sm p-8 text-center text-slate-500">
            No receipts yet — add some to see your spending breakdown.
          </div>
        {:else}
          <!-- Summary cards -->
          <section class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div class="bg-white rounded-xl shadow-sm p-5">
              <div class="text-sm text-slate-500">Total spend</div>
              <div class="text-2xl font-semibold mt-1">{fmt(stats.total_spend)}</div>
              {#if multiCurrency}
                <div class="text-xs text-amber-600 mt-1">mixed currencies — see breakdown</div>
              {/if}
            </div>
            <div class="bg-white rounded-xl shadow-sm p-5">
              <div class="text-sm text-slate-500">Receipts</div>
              <div class="text-2xl font-semibold mt-1">{stats.receipt_count}</div>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-5">
              <div class="text-sm text-slate-500">Avg / receipt</div>
              <div class="text-2xl font-semibold mt-1">
                {fmt(Number(stats.total_spend) / stats.receipt_count)}
              </div>
            </div>
          </section>

          <!-- By currency -->
          <section class="bg-white rounded-xl shadow-sm p-5">
            <h2 class="font-semibold mb-3">By currency</h2>
            <div class="flex flex-wrap gap-3">
              {#each stats.by_currency as c}
                <div class="rounded-lg border border-slate-200 px-3 py-2">
                  <span class="font-medium">{c.currency || "—"}</span>
                  <span class="text-slate-600"> {fmt(c.total)}</span>
                  <span class="text-xs text-slate-400">({c.count})</span>
                </div>
              {/each}
            </div>
          </section>

          <!-- By category -->
          <section class="bg-white rounded-xl shadow-sm p-5">
            <h2 class="font-semibold mb-4">Spend by category</h2>
            <div class="space-y-3">
              {#each stats.by_category as c}
                <div>
                  <div class="flex justify-between text-sm mb-1">
                    <span class="capitalize">{c.category || "uncategorized"}</span>
                    <span class="text-slate-600">{fmt(c.total)} <span class="text-xs text-slate-400">({c.count})</span></span>
                  </div>
                  <div class="h-3 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      class="h-full rounded-full {catColor(c.category)}"
                      style="width: {(Number(c.total) / maxCategory) * 100}%"
                    ></div>
                  </div>
                </div>
              {/each}
            </div>
          </section>

          <!-- By month -->
          <section class="bg-white rounded-xl shadow-sm p-5">
            <h2 class="font-semibold mb-4">Spend by month</h2>
            {#if stats.by_month.length === 0}
              <p class="text-sm text-slate-500">No dated receipts yet.</p>
            {:else}
              <div class="space-y-3">
                {#each stats.by_month as m}
                  <div>
                    <div class="flex justify-between text-sm mb-1">
                      <span>{m.month}</span>
                      <span class="text-slate-600">{fmt(m.total)} <span class="text-xs text-slate-400">({m.count})</span></span>
                    </div>
                    <div class="h-3 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        class="h-full rounded-full bg-blue-400"
                        style="width: {(Number(m.total) / maxMonth) * 100}%"
                      ></div>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </section>
        {/if}
      {/if}
    </main>
  </div>
{/if}
