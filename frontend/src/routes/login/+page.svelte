<script>
  import { goto } from "$app/navigation";
  import { login } from "$lib/api";
  import { setToken } from "$lib/auth";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  let email = $state("");
  let password = $state("");
  let totpCode = $state("");
  let step = $state("credentials"); // "credentials" | "totp"
  let busy = $state(false);
  let error = $state("");

  async function onSubmit(e) {
    e.preventDefault();
    busy = true;
    error = "";
    try {
      const { access_token } = await login(
        email,
        password,
        step === "totp" ? totpCode : null,
      );
      setToken(access_token);
      goto("/dashboard");
    } catch (err) {
      if (err.message === "mfa_required") {
        step = "totp";
        totpCode = "";
      } else {
        error = err.message;
      }
    } finally {
      busy = false;
    }
  }

  function backToCredentials() {
    step = "credentials";
    totpCode = "";
    error = "";
  }
</script>

<div class="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-100 px-4">
  <div class="w-full max-w-sm">
    <div class="text-center mb-6">
      <div class="text-4xl">🧾</div>
      <h1 class="text-xl font-semibold mt-2">Receipt Scanner</h1>
      {#if step === "totp"}
        <p class="text-sm text-slate-500 dark:text-slate-400">Enter your authenticator code</p>
      {:else}
        <p class="text-sm text-slate-500 dark:text-slate-400">Sign in to continue</p>
      {/if}
    </div>

    <form onsubmit={onSubmit} class="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 space-y-4">
      {#if error}
        <div class="bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900 rounded-lg p-3 text-sm">
          {error}
        </div>
      {/if}

      {#if step === "credentials"}
        <label class="block text-sm">
          <span class="font-medium">Email</span>
          <input
            type="email"
            bind:value={email}
            required
            autocomplete="username"
            placeholder="Enter email address"
            class="mt-1 block w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2"
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

        <div class="text-center">
          <a href="/forgot-password" class="text-xs text-blue-600 hover:underline">Forgot your password?</a>
        </div>
      {:else}
        <div class="text-sm text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-900 rounded-lg p-3">
          Signed in as <strong>{email}</strong>. Enter the 6-digit code from your authenticator app.
        </div>

        <label class="block text-sm">
          <span class="font-medium">Authenticator code</span>
          <input
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            maxlength="8"
            bind:value={totpCode}
            required
            autocomplete="one-time-code"
            placeholder="000000"
            autofocus
            class="mt-1 block w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 p-2 text-center text-2xl tracking-widest font-mono"
          />
        </label>

        <button
          type="submit"
          disabled={busy || totpCode.length < 6}
          class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? "Verifying…" : "Verify"}
        </button>

        <button
          type="button"
          onclick={backToCredentials}
          class="w-full text-sm text-slate-500 hover:text-slate-700"
        >← Back to sign in</button>
      {/if}
    </form>
  </div>
</div>
