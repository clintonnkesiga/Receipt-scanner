<script>
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import {
    listUsers,
    createUser,
    updateUser,
    deleteUser,
    resetUserPassword,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  const ROLES = ["user", "admin", "superadmin"];

  let users = $state([]);

  // Inline password-reset state (which row is open + its new value).
  let resetId = $state(null);
  let resetValue = $state("");

  // New-user form
  let form = $state({ email: "", full_name: "", password: "", role: "user" });
  let creating = $state(false);

  async function refresh() {
    try {
      users = await listUsers();
    } catch (e) {
      toasts.error(e instanceof Error ? e.message : "Could not load users");
    }
  }

  onMount(async () => {
    if ($currentUser?.role !== "superadmin") {
      goto("/receipts");
      return;
    }
    await refresh();
  });

  async function onCreate(e) {
    e.preventDefault();
    creating = true;
    try {
      await createUser({ ...form });
      form = { email: "", full_name: "", password: "", role: "user" };
      await refresh();
      toasts.success("User created");
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not create user",
      );
    } finally {
      creating = false;
    }
  }

  async function onRoleChange(u, role) {
    try {
      await updateUser(u.id, { role });
      await refresh();
      toasts.success(`Role updated to ${role}`);
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not update role",
      );
      await refresh();
    }
  }

  async function onToggleActive(u) {
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      await refresh();
      toasts.success(u.is_active ? "User deactivated" : "User activated");
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not update user",
      );
    }
  }

  async function onDelete(u) {
    if (!confirm(`Delete user ${u.email}?`)) return;
    try {
      await deleteUser(u.id);
      await refresh();
      toasts.success(`User ${u.email} deleted`);
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not delete user",
      );
    }
  }

  function startReset(u) {
    resetId = u.id;
    resetValue = "";
  }

  function cancelReset() {
    resetId = null;
    resetValue = "";
  }

  async function submitReset(u) {
    if (resetValue.length < 8) {
      toasts.error("New password must be at least 8 characters");
      return;
    }
    try {
      await resetUserPassword(u.id, resetValue);
      toasts.success(`Password reset for ${u.email}`);
      cancelReset();
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not reset password",
      );
    }
  }
</script>

<div class="w-full px-6 py-8 space-y-6">
  <h1 class="text-2xl font-semibold">User management</h1>

  <!-- Create user -->
  <section class="bg-white rounded-xl shadow-sm p-5">
    <h2 class="font-semibold mb-3">Add a user</h2>
    <form
      onsubmit={onCreate}
      class="grid grid-cols-1 md:grid-cols-5 gap-3 items-end"
    >
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
        <PasswordInput
          bind:value={form.password}
          required
          minlength="8"
          class="mt-1"
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
    <p class="text-xs text-slate-400 mt-2">
      Password must be at least 8 characters.
    </p>
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
              {#if u.id === $currentUser?.id}<span
                  class="text-xs text-slate-400">(you)</span
                >{/if}
            </td>
            <td>{u.full_name || "—"}</td>
            <td>
              <select
                value={u.role}
                disabled={u.id === $currentUser?.id}
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
            <td class="text-right space-x-3 whitespace-nowrap">
              <button
                onclick={() => startReset(u)}
                class="text-xs text-blue-600 hover:underline"
              >
                reset pw
              </button>
              {#if u.id !== $currentUser?.id}
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
              {/if}
            </td>
          </tr>
          {#if resetId === u.id}
            <tr class="bg-slate-50">
              <td colspan="5" class="px-2 py-3">
                <div class="flex flex-wrap items-center gap-2 text-sm">
                  <span class="font-medium">New password for {u.email}:</span>
                  <div class="flex-1 min-w-[12rem]">
                    <PasswordInput
                      bind:value={resetValue}
                      placeholder="min. 8 characters"
                      autocomplete="new-password"
                    />
                  </div>
                  <button
                    onclick={() => submitReset(u)}
                    class="bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700"
                  >
                    Set password
                  </button>
                  <button
                    onclick={cancelReset}
                    class="px-3 py-2 rounded-lg border hover:bg-white"
                  >
                    Cancel
                  </button>
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </section>
</div>
