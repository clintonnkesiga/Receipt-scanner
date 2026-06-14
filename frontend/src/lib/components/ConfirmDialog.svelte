<script>
  // Reusable confirmation modal — a styled replacement for the native confirm().
  // Controlled via `open`; the parent runs the actual action in `onconfirm` and
  // can pass `busy` to show progress and keep the dialog open until it resolves.
  let {
    open = $bindable(false),
    title = "Are you sure?",
    message = "",
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    danger = false,
    busy = false,
    onconfirm,
    oncancel,
  } = $props();

  function cancel() {
    if (busy) return;
    open = false;
    oncancel?.();
  }

  function confirm() {
    onconfirm?.();
  }
</script>

<svelte:window onkeydown={(e) => open && e.key === "Escape" && cancel()} />

{#if open}
  <div
    role="presentation"
    class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    onclick={cancel}
  >
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      class="w-full max-w-sm bg-white dark:bg-slate-800 dark:text-slate-100 rounded-xl shadow-2xl p-5 space-y-4"
      onclick={(e) => e.stopPropagation()}
    >
      <h2 id="confirm-title" class="font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
      {#if message}
        <p class="text-sm text-slate-600 dark:text-slate-300">{message}</p>
      {/if}
      <div class="flex justify-end gap-3 pt-1">
        <button
          type="button"
          onclick={cancel}
          disabled={busy}
          class="px-4 py-2 rounded-lg border dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onclick={confirm}
          disabled={busy}
          class="px-4 py-2 rounded-lg text-white disabled:opacity-50
                 {danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}"
        >
          {confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}
