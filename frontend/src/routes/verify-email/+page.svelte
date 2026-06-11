<script>
  import { page } from "$app/stores";
  import { onMount } from "svelte";
  import { verifyEmail } from "$lib/api";

  const token = $derived($page.url.searchParams.get("token") ?? "");

  let status = $state("verifying"); // verifying | success | error
  let errorMsg = $state("");

  onMount(async () => {
    if (!token) { status = "error"; errorMsg = "No verification token found."; return; }
    try {
      await verifyEmail(token);
      status = "success";
    } catch (err) {
      status = "error";
      errorMsg = err instanceof Error ? err.message : "Verification failed";
    }
  });
</script>

<div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
  <div class="w-full max-w-sm">
    <div class="bg-white rounded-xl shadow-sm p-8 text-center space-y-4">
      {#if status === "verifying"}
        <div class="text-3xl animate-pulse">📬</div>
        <p class="text-slate-600">Verifying your email…</p>
      {:else if status === "success"}
        <div class="text-4xl">✅</div>
        <p class="font-semibold text-lg">Email verified!</p>
        <p class="text-sm text-slate-500">Your email address has been confirmed.</p>
        <a href="/account" class="inline-block bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">
          Go to account
        </a>
      {:else}
        <div class="text-4xl">❌</div>
        <p class="font-semibold">Verification failed</p>
        <p class="text-sm text-red-600">{errorMsg}</p>
        <a href="/account" class="text-sm text-blue-600 hover:underline">
          Request a new verification email from Account settings
        </a>
      {/if}
    </div>
  </div>
</div>
