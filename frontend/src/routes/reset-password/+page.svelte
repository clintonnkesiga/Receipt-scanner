<script>
  import { page } from "$app/stores";
  import { goto } from "$app/navigation";
  import { resetPassword } from "$lib/api";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  const token = $derived($page.url.searchParams.get("token") ?? "");

  let newPassword = $state("");
  let confirm = $state("");
  let busy = $state(false);
  let done = $state(false);
  let error = $state("");

  async function onSubmit(e) {
    e.preventDefault();
    if (newPassword.length < 8) { error = "Password must be at least 8 characters"; return; }
    if (newPassword !== confirm) { error = "Passwords do not match"; return; }
    busy = true;
    error = "";
    try {
      await resetPassword(token, newPassword);
      done = true;
      setTimeout(() => goto("/login"), 3000);
    } catch (err) {
      error = err instanceof Error ? err.message : "Reset failed";
    } finally {
      busy = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-6">
      <div class="text-4xl">🧾</div>
      <h1 class="text-xl font-semibold mt-2">Set new password</h1>
    </div>

    {#if !token}
      <div class="bg-white rounded-xl shadow-sm p-6 text-center text-sm text-slate-500">
        Invalid reset link. <a href="/forgot-password" class="text-blue-600 hover:underline">Request a new one.</a>
      </div>
    {:else if done}
      <div class="bg-white rounded-xl shadow-sm p-6 text-center space-y-3">
        <div class="text-3xl">✅</div>
        <p class="font-medium">Password updated!</p>
        <p class="text-sm text-slate-500">Redirecting to sign in…</p>
      </div>
    {:else}
      <form onsubmit={onSubmit} class="bg-white rounded-xl shadow-sm p-6 space-y-4">
        {#if error}
          <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">{error}</div>
        {/if}

        <label class="block text-sm">
          <span class="font-medium">New password</span>
          <PasswordInput bind:value={newPassword} required autocomplete="new-password" class="mt-1" />
        </label>
        <label class="block text-sm">
          <span class="font-medium">Confirm password</span>
          <PasswordInput bind:value={confirm} required autocomplete="new-password" class="mt-1" />
        </label>

        <button type="submit" disabled={busy}
          class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {busy ? "Saving…" : "Set new password"}
        </button>
      </form>
    {/if}
  </div>
</div>
