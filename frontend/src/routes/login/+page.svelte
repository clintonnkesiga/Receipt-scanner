<script>
  import { goto } from "$app/navigation";
  import { login } from "$lib/api";
  import { setToken } from "$lib/auth";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let email = $state("");
  let password = $state("");
  let busy = $state(false);
  let error = $state("");

  async function onSubmit(e) {
    e.preventDefault();
    busy = true;
    error = "";
    try {
      const { access_token } = await login(email, password);
      setToken(access_token);
      goto("/");
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-6">
      <div class="text-4xl">🧾</div>
      <h1 class="text-xl font-semibold mt-2">Receipt Manager</h1>
      <p class="text-sm text-slate-500">Sign in to continue</p>
    </div>

    <form onsubmit={onSubmit} class="bg-white rounded-xl shadow-sm p-6 space-y-4">
      {#if error}
        <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg p-3 text-sm">
          {error}
        </div>
      {/if}

      <label class="block text-sm">
        <span class="font-medium">Email</span>
        <input
          type="email"
          bind:value={email}
          required
          autocomplete="username"
          placeholder="Enter email address"
          class="mt-1 block w-full rounded-lg border border-slate-300 p-2"
        />
      </label>

      <label class="block text-sm">
        <span class="font-medium">Password</span>
        <PasswordInput
          bind:value={password}
          required
          placeholder="Enter password"
          autocomplete="current-password"
          class="mt-1"
        />
      </label>

      <button
        type="submit"
        disabled={busy}
        class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  </div>
</div>
