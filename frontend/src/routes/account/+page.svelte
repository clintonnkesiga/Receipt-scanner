<script>
  import { changePassword } from "$lib/api";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let current = $state("");
  let next = $state("");
  let confirm = $state("");
  let busy = $state(false);
  let error = $state("");
  let success = $state("");

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

<div class="max-w-md mx-auto px-4 py-8">
  <h1 class="text-2xl font-semibold mb-6">Account</h1>

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
        <PasswordInput
          bind:value={current}
          required
          autocomplete="current-password"
          class="mt-1"
        />
      </label>
      <label class="block text-sm">
        <span class="font-medium">New password</span>
        <PasswordInput
          bind:value={next}
          required
          autocomplete="new-password"
          class="mt-1"
        />
      </label>
      <label class="block text-sm">
        <span class="font-medium">Confirm new password</span>
        <PasswordInput
          bind:value={confirm}
          required
          autocomplete="new-password"
          class="mt-1"
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
</div>
