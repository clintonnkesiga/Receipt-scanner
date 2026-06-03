<script>
  import { onMount } from "svelte";
  import { changePassword } from "$lib/api";
  import { requireUser } from "$lib/guard";

  let user = $state(null);
  let ready = $state(false);

  let current = $state("");
  let next = $state("");
  let confirm = $state("");
  let busy = $state(false);
  let error = $state("");
  let success = $state("");

  onMount(async () => {
    user = await requireUser();
    if (user) ready = true;
  });

  async function onSubmit(e) {
    e.preventDefault();
    error = "";
    success = "";
    if (next.length < 8) {
      error = "New password must be at least 8 characters";
      return;
    }
    if (next !== confirm) {
      error = "New passwords do not match";
      return;
    }
    busy = true;
    try {
      await changePassword(current, next);
      success = "Password updated successfully.";
      current = next = confirm = "";
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }
</script>

{#if ready}
  <div class="min-h-screen bg-slate-50 text-slate-800">
    <header class="bg-white border-b">
      <div class="max-w-2xl mx-auto px-4 py-4 flex items-center justify-between">
        <a href="/" class="text-sm text-blue-600 hover:underline">← Back</a>
        <h1 class="font-semibold">Account</h1>
        <span class="text-sm text-slate-500">{user?.email}</span>
      </div>
    </header>

    <main class="max-w-md mx-auto px-4 py-8">
      <div class="bg-white rounded-xl shadow-sm p-6">
        <h2 class="font-semibold mb-4">Change password</h2>

        {#if error}
          <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm mb-4">
            {error}
          </div>
        {/if}
        {#if success}
          <div class="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg p-3 text-sm mb-4">
            {success}
          </div>
        {/if}

        <form onsubmit={onSubmit} class="space-y-4">
          <label class="block text-sm">
            <span class="font-medium">Current password</span>
            <input
              type="password"
              bind:value={current}
              required
              autocomplete="current-password"
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="block text-sm">
            <span class="font-medium">New password</span>
            <input
              type="password"
              bind:value={next}
              required
              autocomplete="new-password"
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <label class="block text-sm">
            <span class="font-medium">Confirm new password</span>
            <input
              type="password"
              bind:value={confirm}
              required
              autocomplete="new-password"
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Saving…" : "Update password"}
          </button>
        </form>
      </div>
    </main>
  </div>
{/if}
