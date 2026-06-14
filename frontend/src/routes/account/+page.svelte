<script>
  import {
    changePassword, updateProfile, sendVerification,
    get2FASetup, enable2FA, disable2FA,
  } from "$lib/api";
  import { currentUser } from "$lib/auth";
  import { toasts } from "$lib/toast.js";
  import PasswordInput from "$lib/components/PasswordInput.svelte";

  // ── Profile ──────────────────────────────────────────────────────────────────
  let profileName = $state($currentUser?.full_name ?? "");
  let profileAvatar = $state($currentUser?.avatar_url ?? "");
  let profileBusy = $state(false);

  $effect(() => {
    profileName = $currentUser?.full_name ?? "";
    profileAvatar = $currentUser?.avatar_url ?? "";
  });

  async function onProfileSave(e) {
    e.preventDefault();
    profileBusy = true;
    try {
      const updated = await updateProfile({ full_name: profileName, avatar_url: profileAvatar });
      currentUser.set(updated);
      toasts.success("Profile updated");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not update profile");
    } finally {
      profileBusy = false;
    }
  }

  // ── Email verification ───────────────────────────────────────────────────────
  let verifyBusy = $state(false);
  async function onSendVerification() {
    verifyBusy = true;
    try {
      await sendVerification();
      toasts.success("Verification email sent — check your inbox");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not send verification email");
    } finally {
      verifyBusy = false;
    }
  }

  // ── Password change ──────────────────────────────────────────────────────────
  let current = $state("");
  let next = $state("");
  let confirm = $state("");
  let pwBusy = $state(false);

  async function onPasswordSubmit(e) {
    e.preventDefault();
    if (next.length < 8) { toasts.error("New password must be at least 8 characters"); return; }
    if (next !== confirm) { toasts.error("New passwords do not match"); return; }
    pwBusy = true;
    try {
      await changePassword(current, next);
      current = next = confirm = "";
      toasts.success("Password updated successfully");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not update password");
    } finally {
      pwBusy = false;
    }
  }

  // ── 2FA ──────────────────────────────────────────────────────────────────────
  let twoFAStep = $state("idle"); // idle | setup | confirm_disable
  let twoFASetupData = $state(null);
  let twoFACode = $state("");
  let twoFABusy = $state(false);

  async function startSetup2FA() {
    twoFABusy = true;
    try {
      twoFASetupData = await get2FASetup();
      twoFAStep = "setup";
      twoFACode = "";
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not start 2FA setup");
    } finally {
      twoFABusy = false;
    }
  }

  async function onEnable2FA() {
    if (twoFACode.length < 6) return;
    twoFABusy = true;
    try {
      await enable2FA(twoFACode);
      currentUser.update((u) => u ? { ...u, totp_enabled: true } : u);
      twoFAStep = "idle";
      twoFASetupData = null;
      twoFACode = "";
      toasts.success("Two-factor authentication enabled");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not enable 2FA");
    } finally {
      twoFABusy = false;
    }
  }

  async function onDisable2FA() {
    if (twoFACode.length < 6) return;
    twoFABusy = true;
    try {
      await disable2FA(twoFACode);
      currentUser.update((u) => u ? { ...u, totp_enabled: false } : u);
      twoFAStep = "idle";
      twoFACode = "";
      toasts.success("Two-factor authentication disabled");
    } catch (err) {
      toasts.error(err instanceof Error ? err.message : "Could not disable 2FA");
    } finally {
      twoFABusy = false;
    }
  }
</script>

<div class="max-w-lg mx-auto px-4 py-8 space-y-6">
  <h1 class="text-2xl font-semibold">Account</h1>

  {#if $currentUser}

    <!-- Profile -->
    <section class="bg-white rounded-xl shadow-sm p-6">
      <h2 class="font-semibold mb-4">Profile</h2>

      <div class="flex items-center gap-4 mb-5">
        {#if $currentUser.avatar_url}
          <img src={$currentUser.avatar_url} alt="Avatar" class="w-16 h-16 rounded-full object-cover border" />
        {:else}
          <div class="w-16 h-16 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-2xl font-semibold select-none">
            {($currentUser.full_name || $currentUser.email).charAt(0).toUpperCase()}
          </div>
        {/if}
        <div>
          <div class="font-medium">{$currentUser.full_name || $currentUser.email}</div>
          <div class="text-sm text-slate-500">{$currentUser.email}</div>
          <div class="flex items-center gap-2 mt-0.5">
            <span class="text-xs capitalize bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{$currentUser.role}</span>
            {#if $currentUser.is_verified}
              <span class="text-xs text-emerald-600">✓ verified</span>
            {:else}
              <span class="text-xs text-amber-600">email unverified</span>
            {/if}
          </div>
        </div>
      </div>

      <form onsubmit={onProfileSave} class="space-y-3">
        <label class="block text-sm">
          <span class="font-medium">Display name</span>
          <input bind:value={profileName} placeholder="Your name" class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <label class="block text-sm">
          <span class="font-medium">Avatar URL <span class="font-normal text-slate-400">(any public image link)</span></span>
          <input bind:value={profileAvatar} placeholder="https://…/photo.jpg" class="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
        </label>
        <button type="submit" disabled={profileBusy} class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
          {profileBusy ? "Saving…" : "Save profile"}
        </button>
      </form>

      {#if !$currentUser.is_verified}
        <div class="mt-4 pt-4 border-t flex items-center justify-between text-sm">
          <span class="text-amber-700">Email address is not verified.</span>
          <button type="button" onclick={onSendVerification} disabled={verifyBusy} class="text-blue-600 hover:underline disabled:opacity-50">
            {verifyBusy ? "Sending…" : "Send verification email"}
          </button>
        </div>
      {/if}
    </section>

    <!-- Two-factor authentication -->
    <section class="bg-white rounded-xl shadow-sm p-6">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="font-semibold">Two-factor authentication</h2>
          <p class="text-xs text-slate-500 mt-0.5">
            {#if $currentUser.totp_enabled}
              Your account requires an authenticator code on every sign-in.
            {:else}
              Add an extra layer of security with Google Authenticator, Authy, or any TOTP app.
            {/if}
          </p>
        </div>
        {#if $currentUser.totp_enabled}
          <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium shrink-0">Enabled</span>
        {:else}
          <span class="text-xs bg-slate-100 text-slate-400 px-2 py-0.5 rounded-full shrink-0">Disabled</span>
        {/if}
      </div>

      {#if twoFAStep === "idle"}
        {#if $currentUser.totp_enabled}
          <button type="button" onclick={() => { twoFAStep = "confirm_disable"; twoFACode = ""; }} class="text-sm text-red-600 hover:underline">
            Disable 2FA…
          </button>
        {:else}
          <button type="button" onclick={startSetup2FA} disabled={twoFABusy} class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
            {twoFABusy ? "Loading…" : "Set up 2FA"}
          </button>
        {/if}

      {:else if twoFAStep === "setup" && twoFASetupData}
        <div class="space-y-4">
          <p class="text-sm">Scan this QR code with your authenticator app, then enter the 6-digit code below to confirm.</p>
          <img src={twoFASetupData.qr_data_uri} alt="2FA QR code" class="w-44 h-44 border rounded-lg mx-auto" />
          <details class="text-xs text-slate-400">
            <summary class="cursor-pointer">Show setup key (manual entry)</summary>
            <code class="block mt-1 break-all bg-slate-50 rounded p-2 select-all">{twoFASetupData.secret}</code>
          </details>
          <label class="block text-sm">
            <span class="font-medium">Confirmation code</span>
            <input type="text" inputmode="numeric" maxlength="8" bind:value={twoFACode} placeholder="000000"
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2 text-center text-xl tracking-widest font-mono" />
          </label>
          <div class="flex gap-3">
            <button type="button" onclick={onEnable2FA} disabled={twoFABusy || twoFACode.length < 6}
              class="bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-emerald-700 disabled:opacity-50">
              {twoFABusy ? "Enabling…" : "Enable 2FA"}
            </button>
            <button type="button" onclick={() => { twoFAStep = "idle"; twoFASetupData = null; twoFACode = ""; }}
              class="px-4 py-2 rounded-lg border text-sm hover:bg-slate-50">Cancel</button>
          </div>
        </div>

      {:else if twoFAStep === "confirm_disable"}
        <div class="space-y-3">
          <p class="text-sm text-slate-600">Enter your current authenticator code to confirm.</p>
          <label class="block text-sm">
            <span class="font-medium">Authenticator code</span>
            <input type="text" inputmode="numeric" maxlength="8" bind:value={twoFACode} placeholder="000000"
              class="mt-1 block w-full rounded-lg border border-slate-300 p-2 text-center text-xl tracking-widest font-mono" />
          </label>
          <div class="flex gap-3">
            <button type="button" onclick={onDisable2FA} disabled={twoFABusy || twoFACode.length < 6}
              class="bg-red-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-red-700 disabled:opacity-50">
              {twoFABusy ? "Disabling…" : "Disable 2FA"}
            </button>
            <button type="button" onclick={() => { twoFAStep = "idle"; twoFACode = ""; }}
              class="px-4 py-2 rounded-lg border text-sm hover:bg-slate-50">Cancel</button>
          </div>
        </div>
      {/if}
    </section>

    <!-- Change password -->
    <section class="bg-white rounded-xl shadow-sm p-6">
      <h2 class="font-semibold mb-4">Change password</h2>
      <form onsubmit={onPasswordSubmit} class="space-y-4">
        <label class="block text-sm">
          <span class="font-medium">Current password</span>
          <PasswordInput bind:value={current} required autocomplete="current-password" class="mt-1" />
        </label>
        <label class="block text-sm">
          <span class="font-medium">New password</span>
          <PasswordInput bind:value={next} required autocomplete="new-password" class="mt-1" />
        </label>
        <label class="block text-sm">
          <span class="font-medium">Confirm new password</span>
          <PasswordInput bind:value={confirm} required autocomplete="new-password" class="mt-1" />
        </label>
        <button type="submit" disabled={pwBusy} class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {pwBusy ? "Saving…" : "Update password"}
        </button>
      </form>
    </section>

    <!-- Activity log link -->
    <div class="text-right">
      <a href="/audit" class="text-sm text-blue-600 hover:underline">View activity log →</a>
    </div>

  {/if}
</div>
