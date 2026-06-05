<script>
  import "../app.css";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { getToken, logout, currentUser } from "$lib/auth";
  import { getMe } from "$lib/api";
  import Toast from "$lib/components/Toast.svelte";

  let { children } = $props();

  // Routes that render without the app shell (no sidebar, no guard).
  const PUBLIC = new Set(["/login"]);
  const isPublic = $derived(PUBLIC.has($page.url.pathname));

  // Centralized auth: load the user once, redirect to /login when unauthenticated.
  $effect(() => {
    const path = $page.url.pathname;
    if (PUBLIC.has(path)) return;
    if (!getToken()) {
      goto("/login");
      return;
    }
    if (!$currentUser) {
      getMe()
        .then((u) => currentUser.set(u))
        .catch(() => {
          logout();
          goto("/login");
        });
    }
  });

  const isAdmin = $derived(
    $currentUser?.role === "admin" || $currentUser?.role === "superadmin",
  );

  const links = $derived([
    { href: "/dashboard", label: "Dashboard", icon: "📊" },
    { href: "/", label: "Receipts", icon: "🧾" },
    ...(isAdmin
      ? [{ href: "/categories", label: "Categories", icon: "🏷️" }]
      : []),
    ...($currentUser?.role === "superadmin"
      ? [{ href: "/users", label: "Users", icon: "👥" }]
      : []),
    { href: "/account", label: "Account", icon: "⚙️" },
  ]);

  function isActive(href) {
    const path = $page.url.pathname;
    return href === "/" ? path === "/" : path.startsWith(href);
  }

  function onLogout() {
    logout();
    goto("/login");
  }
</script>

{#if isPublic}
  {@render children()}
{:else if $currentUser}
  <div class="min-h-screen flex bg-slate-50 text-slate-800">
    <aside class="w-60 shrink-0 bg-white border-r flex flex-col">
      <div
        class="px-5 py-5 text-lg font-semibold flex items-center gap-2 border-b"
      >
        <span>🧾</span> Receipt Scanner
      </div>
      <nav class="flex-1 p-3 space-y-1">
        {#each links as l}
          <a
            href={l.href}
            class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition
              {isActive(l.href)
              ? 'bg-blue-50 text-blue-700'
              : 'text-slate-600 hover:bg-slate-100'}"
          >
            <span>{l.icon}</span>
            {l.label}
          </a>
        {/each}
      </nav>
      <div class="border-t p-4">
        <div class="text-sm font-medium truncate" title={$currentUser.email}>
          {$currentUser.email}
        </div>
        <div class="text-xs text-slate-400 capitalize mb-2">
          {$currentUser.role}
        </div>
        <button
          onclick={onLogout}
          class="text-sm text-slate-500 hover:text-red-600"
        >
          Logout
        </button>
      </div>
    </aside>

    <div class="flex-1 min-w-0">
      {@render children()}
    </div>
  </div>
{:else}
  <div
    class="min-h-screen flex items-center justify-center text-slate-400 text-sm"
  >
    Loading…
  </div>
{/if}

<Toast />
