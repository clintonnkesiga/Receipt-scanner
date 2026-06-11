<script>
  import { forgotPassword } from "$lib/api";

  let email = $state("");
  let busy = $state(false);
  let sent = $state(false);
  let error = $state("");

  async function onSubmit(e) {
    e.preventDefault();
    busy = true;
    error = "";
    try {
      await forgotPassword(email);
      sent = true;
    } catch (err) {
      error = err instanceof Error ? err.message : "Something went wrong";
    } finally {
      busy = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-6">
      <div class="text-4xl">🧾</div>
      <h1 class="text-xl font-semibold mt-2">Reset password</h1>
      <p class="text-sm text-slate-500">We'll email you a reset link</p>
    </div>

    {#if sent}
      <div class="bg-white rounded-xl shadow-sm p-6 text-center space-y-3">
        <div class="text-3xl">📬</div>
        <p class="font-medium">Check your inbox</p>
        <p class="text-sm text-slate-500">
          If <strong>{email}</strong> is registered, we've sent a password reset link.
          It expires in 1 hour.
        </p>
        <a href="/login" class="block text-sm text-blue-600 hover:underline mt-2">Back to sign in</a>
      </div>
    {:else}
      <form onsubmit={onSubmit} class="bg-white rounded-xl shadow-sm p-6 space-y-4">
        {#if error}
          <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">{error}</div>
        {/if}

        <label class="block text-sm">
          <span class="font-medium">Email address</span>
          <input type="email" bind:value={email} required placeholder="you@example.com"
            class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>

        <button type="submit" disabled={busy}
          class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {busy ? "Sending…" : "Send reset link"}
        </button>

        <div class="text-center">
          <a href="/login" class="text-xs text-slate-500 hover:underline">Back to sign in</a>
        </div>
      </form>
    {/if}
  </div>
</div>
