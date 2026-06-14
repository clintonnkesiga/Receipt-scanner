<script>
  import "../app.css";
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { getToken, logout, currentUser } from "$lib/auth";
  import { getMe } from "$lib/api";
  import { theme, toggleTheme } from "$lib/theme";
  import Toast from "$lib/components/Toast.svelte";

  let { children } = $props();

  // Routes that render without the app shell (no sidebar, no guard).
  const PUBLIC = new Set(["/login", "/forgot-password", "/reset-password", "/verify-email"]);
  const isPublic = $derived(PUBLIC.has($page.url.pathname));

  // Mobile nav drawer.
  let navOpen = $state(false);

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

  // Close the mobile drawer whenever the route changes.
  $effect(() => {
    $page.url.pathname;
    navOpen = false;
  });

  const links = $derived([
    { href: "/dashboard", label: "Dashboard", icon: "📊" },
    { href: "/receipts", label: "Receipts", icon: "🧾" },
    { href: "/categories", label: "Categories", icon: "🏷️" },
    { href: "/budgets", label: "Budgets", icon: "💰" },
    { href: "/reports", label: "Reports", icon: "📈" },
    { href: "/trash", label: "Trash", icon: "🗑️" },
    ...($currentUser?.role === "superadmin"
      ? [{ href: "/users", label: "Users", icon: "👥" }]
      : []),
    { href: "/account", label: "Account", icon: "⚙️" },
  ]);

  function isActive(href) {
    return $page.url.pathname.startsWith(href);
  }

  function onLogout() {
    logout();
    goto("/login");
  }
</script>

{#if isPublic}
  {@render children()}
{:else if $currentUser}
  <div class="min-h-screen flex bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-100">
    <!-- Mobile top bar -->
    <header
      class="md:hidden fixed top-0 inset-x-0 z-30 h-14 flex items-center gap-3 px-4
             bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700"
    >
      <button
        type="button"
        aria-label="Open menu"
        onclick={() => (navOpen = true)}
        class="text-2xl leading-none text-slate-600 dark:text-slate-300"
      >☰</button>
      <span class="font-semibold flex items-center gap-2"><span>🧾</span> Receipt Scanner</span>
    </header>

    <!-- Backdrop (mobile, when drawer open) -->
    {#if navOpen}
      <button
        type="button"
        aria-label="Close menu"
        onclick={() => (navOpen = false)}
        class="md:hidden fixed inset-0 z-40 bg-black/40"
      ></button>
    {/if}

    <aside
      class="fixed md:sticky inset-y-0 left-0 top-0 z-50 md:z-0 w-60 shrink-0 h-screen
             bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700
             flex flex-col transition-transform duration-200
             {navOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0"
    >
      <div
        class="px-5 py-5 text-lg font-semibold flex items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-700 shrink-0"
      >
        <span class="flex items-center gap-2"><span>🧾</span> Receipt Scanner</span>
        <button
          type="button"
          aria-label="Close menu"
          onclick={() => (navOpen = false)}
          class="md:hidden text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl leading-none"
        >&times;</button>
      </div>
      <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
        {#each links as l}
          <a
            href={l.href}
            class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition
              {isActive(l.href)
              ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
              : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'}"
          >
            <span>{l.icon}</span>
            {l.label}
          </a>
        {/each}
      </nav>
      <div class="border-t border-slate-200 dark:border-slate-700 p-4 shrink-0 space-y-3">
        <button
          type="button"
          onclick={toggleTheme}
          class="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
        >
          <span>{$theme === "dark" ? "☀️" : "🌙"}</span>
          {$theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <div>
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
      </div>
    </aside>

    <div class="flex-1 min-w-0 pt-14 md:pt-0">
      {@render children()}
    </div>
  </div>
{:else}
  <div
    class="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 text-slate-400 text-sm"
  >
    Loading…
  </div>
{/if}

<Toast />
