<script>
  import { onMount } from "svelte";
  import { getStats } from "$lib/api";

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
  const maxMerchant = $derived(
    Math.max(
      1,
      ...(stats?.top_merchants ?? []).map((m) => Number(m.total) || 0),
    ),
  );
  const multiCurrency = $derived((stats?.by_currency ?? []).length > 1);

  const trend = $derived(stats?.month_trend ?? null);

  const fmtDate = (s) =>
    s
      ? new Date(s).toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : "—";

  function catColor(category) {
    return category === "fuel"
      ? "bg-amber-400"
      : category === "grocery"
        ? "bg-emerald-400"
        : "bg-slate-400";
  }

  onMount(async () => {
    try {
      stats = await getStats();
    } catch (e) {
      error = e.message;
    }
  });
</script>

<div class="w-full px-6 py-8 space-y-6">
  <h1 class="text-2xl font-semibold">Dashboard</h1>

  {#if error}
    <div
      class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm"
    >
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
        <div class="rounded-xl shadow-sm p-5 bg-blue-50 border border-blue-100">
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-blue-700">Total spend</div>
            <span class="text-lg">💰</span>
          </div>
          <div class="text-2xl font-semibold mt-1 text-blue-900">
            {fmt(stats.total_spend)}
          </div>
          {#if multiCurrency}
            <div class="text-xs text-amber-600 mt-1">
              mixed currencies — see breakdown
            </div>
          {/if}
        </div>
        <div
          class="rounded-xl shadow-sm p-5 bg-emerald-50 border border-emerald-100"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-emerald-700">Receipts</div>
            <span class="text-lg">🧾</span>
          </div>
          <div class="text-2xl font-semibold mt-1 text-emerald-900">
            {stats.receipt_count}
          </div>
        </div>
        <div
          class="rounded-xl shadow-sm p-5 bg-violet-50 border border-violet-100"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-violet-700">Avg / receipt</div>
            <span class="text-lg">📊</span>
          </div>
          <div class="text-2xl font-semibold mt-1 text-violet-900">
            {fmt(Number(stats.total_spend) / stats.receipt_count)}
          </div>
        </div>
      </section>

      <!-- Secondary cards: trend + recent activity -->
      <section class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="rounded-xl shadow-sm p-5 bg-amber-50 border border-amber-100">
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-amber-700">This month</div>
            <span class="text-lg">📅</span>
          </div>
          <div class="text-2xl font-semibold mt-1 text-amber-900">
            {fmt(trend?.current)}
          </div>
          {#if trend && trend.change_pct != null}
            <div
              class="text-xs mt-1 {trend.change_pct > 0
                ? 'text-red-600'
                : trend.change_pct < 0
                  ? 'text-emerald-600'
                  : 'text-slate-400'}"
            >
              {trend.change_pct > 0 ? "▲" : trend.change_pct < 0 ? "▼" : ""}
              {Math.abs(trend.change_pct).toFixed(0)}% vs last month
            </div>
          {:else}
            <div class="text-xs text-slate-400 mt-1">
              no prior month to compare
            </div>
          {/if}
        </div>
        <div class="rounded-xl shadow-sm p-5 bg-cyan-50 border border-cyan-100">
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-cyan-700">
              Added (last 30 days)
            </div>
            <span class="text-lg">➕</span>
          </div>
          <div class="text-2xl font-semibold mt-1 text-cyan-900">
            {stats.recent_count}
          </div>
        </div>
        <div class="rounded-xl shadow-sm p-5 bg-rose-50 border border-rose-100">
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-rose-700">Last receipt</div>
            <span class="text-lg">🕒</span>
          </div>
          <div class="text-2xl font-semibold mt-1 text-rose-900">
            {fmtDate(stats.last_receipt_date)}
          </div>
        </div>
      </section>

      <!-- Largest receipt -->
      {#if stats.largest_receipt}
        {@const lr = stats.largest_receipt}
        <section
          class="rounded-xl shadow-sm p-5 bg-gradient-to-r from-indigo-500 to-violet-500 text-white"
        >
          <h2 class="font-semibold mb-1 flex items-center gap-2">
            <span>🏆</span> Largest receipt
          </h2>
          <div class="flex items-baseline justify-between flex-wrap gap-2">
            <div class="text-indigo-100">
              {lr.merchant || "Unknown merchant"}
              <span class="text-indigo-200 text-sm"
                >· {fmtDate(lr.purchase_date)}</span
              >
            </div>
            <div class="text-xl font-semibold">
              {lr.currency || ""}
              {fmt(lr.total)}
            </div>
          </div>
        </section>
      {/if}

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

      <!-- Charts: 1-col on mobile, 2-col on large screens -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- By category -->
        <section class="bg-white rounded-xl shadow-sm p-5">
          <h2 class="font-semibold mb-4">Spend by category</h2>
          <div class="space-y-3">
            {#each stats.by_category as c}
              <div>
                <div class="flex justify-between text-sm mb-1">
                  <span class="capitalize">{c.category || "uncategorized"}</span
                  >
                  <span class="text-slate-600"
                    >{fmt(c.total)}
                    <span class="text-xs text-slate-400">({c.count})</span
                    ></span
                  >
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

        <!-- Top merchants -->
        {#if stats.top_merchants.length > 0}
          <section class="bg-white rounded-xl shadow-sm p-5">
            <h2 class="font-semibold mb-4">Top merchants</h2>
            <div class="space-y-3">
              {#each stats.top_merchants as m}
                <div>
                  <div class="flex justify-between text-sm mb-1">
                    <span class="truncate pr-2">{m.merchant || "—"}</span>
                    <span class="text-slate-600 whitespace-nowrap"
                      >{fmt(m.total)}
                      <span class="text-xs text-slate-400">({m.count})</span
                      ></span
                    >
                  </div>
                  <div class="h-3 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      class="h-full rounded-full bg-violet-400"
                      style="width: {(Number(m.total) / maxMerchant) * 100}%"
                    ></div>
                  </div>
                </div>
              {/each}
            </div>
          </section>
        {/if}

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
                    <span class="text-slate-600"
                      >{fmt(m.total)}
                      <span class="text-xs text-slate-400">({m.count})</span
                      ></span
                    >
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
      </div>
      <!-- end charts grid -->
    {/if}
  {/if}
</div>
