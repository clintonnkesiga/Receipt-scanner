<script>
  import { fly, fade } from "svelte/transition";
  import { flip } from "svelte/animate";
  import { toasts } from "$lib/toast.js";

  /** @type {Record<string, string>} */
  const icons = { success: "✓", error: "✕", info: "ℹ" };
  /** @type {Record<string, string>} */
  const colors = {
    success: "bg-emerald-600 text-white",
    error: "bg-red-600 text-white",
    info: "bg-slate-800 text-white",
  };
</script>

<!-- Rendered outside the page flow so it always sits on top -->
<div
  aria-live="polite"
  aria-atomic="false"
  class="fixed bottom-5 right-5 z-[200] flex flex-col-reverse gap-2 items-end pointer-events-none"
>
  {#each $toasts as toast (toast.id)}
    <div
      role="status"
      animate:flip={{ duration: 200 }}
      in:fly={{ x: 60, duration: 250, opacity: 0 }}
      out:fade={{ duration: 200 }}
      class="pointer-events-auto flex items-start gap-3 rounded-xl shadow-lg
             px-4 py-3 text-sm max-w-sm w-max {colors[toast.type] ??
        colors.info}"
    >
      <span class="shrink-0 font-bold leading-5"
        >{icons[toast.type] ?? icons.info}</span
      >
      <span class="flex-1 leading-5 pr-1">{toast.message}</span>
      <button
        type="button"
        aria-label="Dismiss"
        onclick={() => toasts.remove(toast.id)}
        class="shrink-0 opacity-70 hover:opacity-100 leading-5 text-base"
        >×</button
      >
    </div>
  {/each}
</div>
