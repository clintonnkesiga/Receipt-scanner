<script>
  import { onMount } from "svelte";
  import { listAuditLog } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";

  const PAGE_SIZE = 50;
  let items = $state([]);
  let total = $state(0);
  let page = $state(1);
  let loading = $state(true);

  const pageCount = $derived(Math.max(1, Math.ceil(total / PAGE_SIZE)));
  const isElevated = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  async function load() {
    loading = true;
    try {
      const data = await listAuditLog({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE });
      items = data.items;
      total = data.total;
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load audit log");
    } finally {
      loading = false;
    }
  }

  function goPage(p) { page = p; load(); }

  onMount(load);

  const ACTION_ICONS = {
    "auth.login": "🔑",
    "auth.password_change": "🔒",
    "auth.password_reset": "🔓",
    "auth.email_verified": "✅",
    "auth.2fa_enabled": "🛡️",
    "auth.2fa_disabled": "⚠️",
    "receipt.create": "🧾",
    "receipt.delete": "🗑️",
    "budget.create": "💰",
    "budget.delete": "🗑️",
  };

  const fmtDate = (s) =>
    new Date(s).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });

  function actionLabel(action) {
    return action
      .replace("auth.", "")
      .replace("receipt.", "Receipt ")
      .replace("budget.", "Budget ")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
</script>

<div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6">
  <div class="flex items-center justify-between">
    <h1 class="text-2xl font-semibold">Activity log</h1>
    {#if total > 0}
      <span class="text-sm text-slate-500">{total} event{total !== 1 ? "s" : ""}</span>
    {/if}
  </div>

  {#if isElevated}
    <p class="text-xs text-slate-400">Showing all users' activity (admin view).</p>
  {/if}

  <section class="bg-white rounded-xl shadow-sm overflow-hidden">
    {#if loading}
      <div class="p-8 text-center text-sm text-slate-400">Loading…</div>
    {:else if items.length === 0}
      <div class="p-8 text-center text-sm text-slate-500">No activity recorded yet.</div>
    {:else}
      <div class="overflow-x-auto">
      <table class="w-full text-sm min-w-[600px]">
        <thead class="text-left text-slate-500 border-b bg-slate-50">
          <tr>
            <th class="py-2 px-4">Event</th>
            {#if isElevated}<th class="py-2 px-4">User</th>{/if}
            <th class="py-2 px-4">Detail</th>
            <th class="py-2 px-4 text-right">When</th>
          </tr>
        </thead>
        <tbody>
          {#each items as entry (entry.id)}
            <tr class="border-b last:border-0 hover:bg-slate-50">
              <td class="py-2.5 px-4 whitespace-nowrap">
                <span class="mr-1.5">{ACTION_ICONS[entry.action] ?? "📋"}</span>
                {actionLabel(entry.action)}
              </td>
              {#if isElevated}
                <td class="py-2.5 px-4 text-slate-500 text-xs">{entry.user_email ?? "—"}</td>
              {/if}
              <td class="py-2.5 px-4 text-slate-500 text-xs">{entry.detail ?? "—"}</td>
              <td class="py-2.5 px-4 text-right text-xs text-slate-400 whitespace-nowrap">
                {fmtDate(entry.created_at)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      </div>

      {#if pageCount > 1}
        <div class="flex items-center justify-between px-4 py-3 border-t text-sm">
          <span class="text-slate-500">Page {page} of {pageCount}</span>
          <div class="flex gap-2">
            <button type="button" onclick={() => goPage(page - 1)} disabled={page <= 1}
              class="px-3 py-1 rounded border hover:bg-slate-50 disabled:opacity-40">Prev</button>
            <button type="button" onclick={() => goPage(page + 1)} disabled={page >= pageCount}
              class="px-3 py-1 rounded border hover:bg-slate-50 disabled:opacity-40">Next</button>
          </div>
        </div>
      {/if}
    {/if}
  </section>
</div>
