<script>
  import { getReceiptImageUrl } from "$lib/api";

  // A single gallery card: lazily loads the (auth-protected) receipt image as an
  // object URL and revokes it on cleanup. Clicking calls `onopen(receipt)`.
  let { receipt, onopen, onedit, ondelete, showOwner = false } = $props();

  let url = $state(null);
  let loading = $state(true);
  let failed = $state(false);

  const isPdf = $derived(
    !!receipt.image_path && receipt.image_path.toLowerCase().endsWith(".pdf"),
  );

  // Re-runs if the receipt changes; cleanup revokes the previous object URL.
  $effect(() => {
    let active = true;
    let objectUrl = null;
    loading = true;
    failed = false;
    url = null;

    if (receipt.image_path && !isPdf) {
      getReceiptImageUrl(receipt.id)
        .then((u) => {
          if (!active) {
            URL.revokeObjectURL(u);
            return;
          }
          objectUrl = u;
          url = u;
        })
        .catch(() => {
          if (active) failed = true;
        })
        .finally(() => {
          if (active) loading = false;
        });
    } else {
      loading = false;
    }

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  });

  const fmtTotal = $derived(
    receipt.total != null
      ? `${receipt.currency || ""} ${Number(receipt.total).toLocaleString()}`
      : "—",
  );
</script>

<div
  class="group relative bg-white rounded-xl border border-slate-200 overflow-hidden
         hover:shadow-md transition focus-within:ring-2 focus-within:ring-blue-400"
>
  <button
    type="button"
    onclick={() => onopen?.(receipt)}
    class="block w-full text-left focus:outline-none"
  >
    <div
      class="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden"
    >
      {#if loading}
        <div class="text-slate-300 text-[10px] animate-pulse">Loading…</div>
      {:else if url}
        <img
          src={url}
          alt={receipt.merchant || "Receipt"}
          class="w-full h-full object-cover object-top group-hover:scale-105 transition"
        />
      {:else}
        <div
          class="flex flex-col items-center text-slate-300 text-[10px] gap-1"
        >
          <span class="text-2xl">{isPdf ? "📄" : "🧾"}</span>
          {isPdf ? "PDF" : "No image"}
        </div>
      {/if}
    </div>
    <div class="p-2">
      <div class="font-medium text-xs truncate">{receipt.merchant || "—"}</div>
      {#if showOwner}
        <div class="text-[10px] text-slate-400 truncate">
          {receipt.owner_email || "—"}
        </div>
      {/if}
      <div class="text-[10px] text-slate-500">
        {receipt.purchase_date || "—"}
      </div>
      <div class="text-xs font-semibold tabular-nums">{fmtTotal}</div>
    </div>
  </button>

  {#if onedit}
    <button
      type="button"
      aria-label="Edit receipt"
      title="Edit receipt"
      onclick={(e) => {
        e.stopPropagation();
        onedit(receipt);
      }}
      class="absolute top-1.5 left-1.5 w-7 h-7 rounded-full bg-white/90 text-blue-600 shadow-sm
             flex items-center justify-center opacity-0 group-hover:opacity-100 focus:opacity-100
             hover:bg-blue-600 hover:text-white transition"
    >
      <svg
        viewBox="0 0 24 24"
        class="w-3.5 h-3.5"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4Z" />
      </svg>
    </button>
  {/if}

  {#if ondelete}
    <button
      type="button"
      aria-label="Delete receipt"
      title="Delete receipt"
      onclick={(e) => {
        e.stopPropagation();
        ondelete(receipt);
      }}
      class="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-white/90 text-red-600 shadow-sm
             flex items-center justify-center opacity-0 group-hover:opacity-100 focus:opacity-100
             hover:bg-red-600 hover:text-white transition"
    >
      <svg
        viewBox="0 0 24 24"
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6"
        />
        <path d="M10 11v6M14 11v6" />
      </svg>
    </button>
  {/if}
</div>
