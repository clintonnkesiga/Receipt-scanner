<script>
  import { onMount } from "svelte";
  import {
    getTimeSeries,
    getRecurring,
    getDigestPreview,
    sendDigest,
    downloadCsv,
    downloadExport,
  } from "$lib/api";
  import { toasts } from "$lib/toast.js";
  import { money } from "$lib/format.js";

  // Filters
  let granularity = $state("month"); // day | week | month
  let dateFrom = $state("");
  let dateTo = $state("");

  let series = $state(null);
  let recurring = $state([]);
  let loading = $state(false);
  let exporting = $state(false);

  const fmt = (n) => Number(n || 0).toLocaleString();
  const fmtDate = (s) =>
    s ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—";

  async function loadSeries() {
    loading = true;
    try {
      series = await getTimeSeries({ granularity, date_from: dateFrom, date_to: dateTo });
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load report");
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    await loadSeries();
    try {
      recurring = await getRecurring();
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load recurring");
    }
  });

  // ── SVG line chart geometry ──────────────────────────────────────────────
  const chart = $derived.by(() => {
    const pts = series?.points ?? [];
    const W = 820, H = 300, padL = 64, padR = 18, padT = 16, padB = 40;
    const max = Math.max(1, ...pts.map((p) => Number(p.total) || 0));
    const n = pts.length;
    const innerW = W - padL - padR;
    const x = (i) => (n <= 1 ? padL + innerW / 2 : padL + (i / (n - 1)) * innerW);
    const y = (v) => padT + (1 - (Number(v) || 0) / max) * (H - padT - padB);
    const coords = pts.map((p, i) => ({ ...p, cx: x(i), cy: y(p.total) }));
    const line = coords.map((c, i) => `${i ? "L" : "M"}${c.cx.toFixed(1)},${c.cy.toFixed(1)}`).join(" ");
    const area = coords.length
      ? `${line} L${coords[coords.length - 1].cx.toFixed(1)},${H - padB} L${coords[0].cx.toFixed(1)},${H - padB} Z`
      : "";
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({ v: max * f, y: y(max * f) }));
    // Show at most ~8 x labels to avoid crowding.
    const step = Math.max(1, Math.ceil(n / 8));
    const xlabels = coords.filter((_, i) => i % step === 0 || i === n - 1);
    return { W, H, padB, coords, line, area, ticks, xlabels };
  });

  async function onExport(format) {
    exporting = true;
    try {
      if (format === "csv") await downloadCsv();
      else await downloadExport(format, { date_from: dateFrom, date_to: dateTo });
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Export failed");
    } finally {
      exporting = false;
    }
  }

  // ── Weekly digest ────────────────────────────────────────────────────────
  let digest = $state(null);
  let digestOpen = $state(false);
  let sending = $state(false);

  async function previewDigest() {
    try {
      digest = await getDigestPreview();
      digestOpen = true;
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load digest");
    }
  }

  async function emailDigest() {
    sending = true;
    try {
      await sendDigest();
      toasts.success("Digest emailed to you");
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not send digest");
    } finally {
      sending = false;
    }
  }
</script>

<div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6">
  <h1 class="text-2xl font-semibold">Reports</h1>

  <!-- Controls -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <div class="flex flex-wrap items-end gap-3">
      <label class="text-sm text-slate-500">
        From
        <input
          type="date"
          bind:value={dateFrom}
          class="mt-1 block rounded-lg border border-slate-300 p-1.5 text-sm"
        />
      </label>
      <label class="text-sm text-slate-500">
        To
        <input
          type="date"
          bind:value={dateTo}
          class="mt-1 block rounded-lg border border-slate-300 p-1.5 text-sm"
        />
      </label>
      <label class="text-sm text-slate-500">
        Granularity
        <select
          bind:value={granularity}
          class="mt-1 block rounded-lg border border-slate-300 p-1.5 text-sm"
        >
          <option value="day">Daily</option>
          <option value="week">Weekly</option>
          <option value="month">Monthly</option>
        </select>
      </label>
      <button
        type="button"
        onclick={loadSeries}
        disabled={loading}
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
      >
        {loading ? "Loading…" : "Apply"}
      </button>

      <div class="ml-auto flex items-center gap-2">
        <span class="text-xs text-slate-400">Export:</span>
        <button type="button" onclick={() => onExport("csv")} disabled={exporting}
          class="text-sm px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-50">CSV</button>
        <button type="button" onclick={() => onExport("xlsx")} disabled={exporting}
          class="text-sm px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-50">Excel</button>
        <button type="button" onclick={() => onExport("pdf")} disabled={exporting}
          class="text-sm px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-50">PDF</button>
      </div>
    </div>
  </section>

  <!-- Spend over time -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <div class="flex items-baseline justify-between mb-4">
      <h2 class="font-semibold">Spend over time</h2>
      {#if series}
        <span class="text-sm text-slate-500">Total {money(series.total)}</span>
      {/if}
    </div>

    {#if !series || series.points.length === 0}
      <p class="text-sm text-slate-500">No dated receipts in this range.</p>
    {:else}
      <svg viewBox="0 0 {chart.W} {chart.H}" class="w-full" role="img" aria-label="Spend over time">
        <!-- Y gridlines + labels -->
        {#each chart.ticks as t}
          <line x1="64" x2={chart.W - 18} y1={t.y} y2={t.y} stroke="#f1f5f9" stroke-width="1" />
          <text x="56" y={t.y + 4} text-anchor="end" font-size="11" fill="#94a3b8">{fmt(t.v)}</text>
        {/each}
        <!-- Area + line -->
        <path d={chart.area} fill="#3b82f6" fill-opacity="0.10" />
        <path d={chart.line} fill="none" stroke="#3b82f6" stroke-width="2.5"
          stroke-linejoin="round" stroke-linecap="round" />
        <!-- Points -->
        {#each chart.coords as c}
          <circle cx={c.cx} cy={c.cy} r="3.5" fill="#2563eb">
            <title>{c.period}: {money(c.total)} ({c.count})</title>
          </circle>
        {/each}
        <!-- X labels -->
        {#each chart.xlabels as c}
          <text x={c.cx} y={chart.H - chart.padB + 20} text-anchor="middle" font-size="11" fill="#94a3b8">{c.period}</text>
        {/each}
      </svg>
    {/if}
  </section>

  <!-- Recurring expenses -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <h2 class="font-semibold mb-1">Recurring expenses</h2>
    <p class="text-xs text-slate-400 mb-4">
      Merchants you pay on a regular cadence (weekly to monthly).
    </p>
    {#if recurring.length === 0}
      <p class="text-sm text-slate-500">No recurring patterns detected yet.</p>
    {:else}
      <div class="overflow-x-auto">
      <table class="w-full text-sm min-w-[600px]">
        <thead class="text-left text-slate-500 border-b">
          <tr>
            <th class="py-2">Merchant</th>
            <th>Category</th>
            <th class="text-right">Avg amount</th>
            <th class="text-right">Every</th>
            <th class="text-right">Times</th>
            <th class="text-right">Next (est.)</th>
          </tr>
        </thead>
        <tbody>
          {#each recurring as r (r.merchant)}
            <tr class="border-b last:border-0">
              <td class="py-2 font-medium">{r.merchant}</td>
              <td class="capitalize text-slate-500">{r.category || "—"}</td>
              <td class="text-right tabular-nums">{money(r.avg_amount)}</td>
              <td class="text-right text-slate-500">~{Math.round(r.avg_interval_days)}d</td>
              <td class="text-right">{r.occurrences}</td>
              <td class="text-right text-slate-500">{fmtDate(r.next_estimated)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      </div>
    {/if}
  </section>

  <!-- Weekly digest -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="font-semibold">Weekly email digest</h2>
        <p class="text-xs text-slate-400 mt-1">
          A summary of your last 7 days. Preview it here or email it to yourself.
        </p>
      </div>
      <div class="flex gap-2">
        <button type="button" onclick={previewDigest}
          class="text-sm px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50">Preview</button>
        <button type="button" onclick={emailDigest} disabled={sending}
          class="text-sm px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
          {sending ? "Sending…" : "Email me"}
        </button>
      </div>
    </div>

    {#if digestOpen && digest}
      <div class="mt-4 border border-slate-200 rounded-lg overflow-hidden">
        <div class="flex items-center justify-between bg-slate-50 px-3 py-2 border-b">
          <span class="text-sm text-slate-600 truncate">Subject: {digest.subject}</span>
          <button type="button" onclick={() => (digestOpen = false)}
            class="text-xs text-slate-500 hover:underline">close</button>
        </div>
        <iframe srcdoc={digest.html} title="Digest preview" class="w-full h-96 bg-white"></iframe>
      </div>
    {/if}
  </section>
</div>
