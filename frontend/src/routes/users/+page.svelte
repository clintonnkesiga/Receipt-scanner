<script>
  import { onMount } from "svelte";
  import { listUsers, createUser, updateUser, deleteUser } from "$lib/api";
  import { requireUser } from "$lib/guard";

  const ROLES = ["user", "admin", "superadmin"];

  let me = $state(null);
  let ready = $state(false);
  let users = $state([]);
  let error = $state("");

  // New-user form
  let form = $state({ email: "", full_name: "", password: "", role: "user" });
  let creating = $state(false);

  async function refresh() {
    try {
      users = await listUsers();
    } catch (e) {
      error = e.message;
    }
  }

  onMount(async () => {
    me = await requireUser({ superadmin: true });
    if (me) {
      ready = true;
      await refresh();
    }
  });

  async function onCreate(e) {
    e.preventDefault();
    error = "";
    creating = true;
    try {
      await createUser({ ...form });
      form = { email: "", full_name: "", password: "", role: "user" };
      await refresh();
    } catch (err) {
      error = err.message;
    } finally {
      creating = false;
    }
  }

  async function onRoleChange(u, role) {
    error = "";
    try {
      await updateUser(u.id, { role });
      await refresh();
    } catch (err) {
      error = err.message;
      await refresh();
    }
  }

  async function onToggleActive(u) {
    error = "";
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      await refresh();
    } catch (err) {
      error = err.message;
    }
  }

  async function onDelete(u) {
    if (!confirm(`Delete user ${u.email}?`)) return;
    error = "";
    try {
      await deleteUser(u.id);
      await refresh();
    } catch (err) {
      error = err.message;
    }
  }
</script>

{#if ready}
  <div class="min-h-screen bg-slate-50 text-slate-800">
    <header class="bg-white border-b">
      <div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
        <a href="/" class="text-sm text-blue-600 hover:underline">← Back</a>
        <h1 class="font-semibold">User management</h1>
        <span class="text-sm text-slate-500">{me?.email}</span>
      </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {#if error}
        <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
          {error}
        </div>
      {/if}

      <!-- Create user -->
      <section class="bg-white rounded-xl shadow-sm p-5">
        <h2 class="font-semibold mb-3">Add a user</h2>
        <form onsubmit={onCreate} class="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <label class="text-sm md:col-span-2">
            <span class="font-medium">Email</span>
            <input
              type="email"
              bind:value={form.email}
              required
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Full name</span>
            <input
              bind:value={form.full_name}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Password</span>
            <input
              type="password"
              bind:value={form.password}
              required
              minlength="8"
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="text-sm">
            <span class="font-medium">Role</span>
            <select
              bind:value={form.role}
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            >
              {#each ROLES as r}
                <option value={r}>{r}</option>
              {/each}
            </select>
          </label>
          <button
            type="submit"
            disabled={creating}
            class="md:col-span-5 md:w-auto md:justify-self-start bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? "Adding…" : "Add user"}
          </button>
        </form>
        <p class="text-xs text-slate-400 mt-2">Password must be at least 8 characters.</p>
      </section>

      <!-- User list -->
      <section class="bg-white rounded-xl shadow-sm p-5">
        <h2 class="font-semibold mb-3">Users ({users.length})</h2>
        <table class="w-full text-sm">
          <thead class="text-left text-slate-500 border-b">
            <tr>
              <th class="py-2">Email</th>
              <th>Name</th>
              <th>Role</th>
              <th>Status</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each users as u (u.id)}
              <tr class="border-b last:border-0">
                <td class="py-2">
                  {u.email}
                  {#if u.id === me?.id}<span class="text-xs text-slate-400">(you)</span>{/if}
                </td>
                <td>{u.full_name || "—"}</td>
                <td>
                  <select
                    value={u.role}
                    disabled={u.id === me?.id}
                    onchange={(e) => onRoleChange(u, e.currentTarget.value)}
                    class="rounded border border-slate-300 p-1 text-xs disabled:opacity-50"
                  >
                    {#each ROLES as r}
                      <option value={r}>{r}</option>
                    {/each}
                  </select>
                </td>
                <td>
                  <span
                    class="text-xs rounded-full px-2 py-0.5 {u.is_active
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-slate-200 text-slate-600'}"
                  >
                    {u.is_active ? "active" : "disabled"}
                  </span>
                </td>
                <td class="text-right space-x-3">
                  {#if u.id !== me?.id}
                    <button
                      onclick={() => onToggleActive(u)}
                      class="text-xs text-slate-600 hover:underline"
                    >
                      {u.is_active ? "disable" : "enable"}
                    </button>
                    <button
                      onclick={() => onDelete(u)}
                      class="text-xs text-red-600 hover:underline"
                    >
                      delete
                    </button>
                  {:else}
                    <span class="text-xs text-slate-300">—</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    </main>
  </div>
{/if}
