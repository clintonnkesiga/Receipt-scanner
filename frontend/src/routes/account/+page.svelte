<script>
  import { changePassword } from "$lib/api";
  import { toasts } from "$lib/toast.js";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let current = $state("");
  let next = $state("");
  let confirm = $state("");
  let busy = $state(false);

  async function onSubmit(e) {
    e.preventDefault();
    if (next.length < 8) {
      toasts.error("New password must be at least 8 characters");
      return;
    }
    if (next !== confirm) {
      toasts.error("New passwords do not match");
      return;
    }
    busy = true;
    try {
      await changePassword(current, next);
      current = next = confirm = "";
      toasts.success("Password updated successfully");
    } catch (err) {
      toasts.error(
        err instanceof Error ? err.message : "Could not update password",
      );
    } finally {
      busy = false;
    }
  }
</script>

<div class="max-w-md mx-auto px-4 py-8">
  <h1 class="text-2xl font-semibold mb-6">Account</h1>

  <div class="bg-white rounded-xl shadow-sm p-6">
    <h2 class="font-semibold mb-4">Change password</h2>

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
