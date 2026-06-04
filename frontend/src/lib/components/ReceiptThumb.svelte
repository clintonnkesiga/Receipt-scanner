<script>
  import { getReceiptImageUrl } from "$lib/api";

  // A single gallery card: lazily loads the (auth-protected) receipt image as an
  // object URL and revokes it on cleanup. Clicking calls `onopen(receipt)`.
  let { receipt, onopen, showOwner = false } = $props();

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

<button
  type="button"
  onclick={() => onopen?.(receipt)}
  class="group block text-left bg-white rounded-xl border border-slate-200 overflow-hidden
         hover:shadow-md transition focus:outline-none focus:ring-2 focus:ring-blue-400"
>
  <div class="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
    {#if loading}
      <div class="text-slate-300 text-[10px] animate-pulse">Loading…</div>
    {:else if url}
      <img
        src={url}
        alt={receipt.merchant || "Receipt"}
        class="w-full h-full object-cover object-top group-hover:scale-105 transition"
      />
    {:else}
      <div class="flex flex-col items-center text-slate-300 text-[10px] gap-1">
        <span class="text-2xl">{isPdf ? "📄" : "🧾"}</span>
        {isPdf ? "PDF" : "No image"}
      </div>
    {/if}
  </div>
  <div class="p-2">
    <div class="font-medium text-xs truncate">{receipt.merchant || "—"}</div>
    {#if showOwner}
      <div class="text-[10px] text-slate-400 truncate">{receipt.owner_email || "—"}</div>
    {/if}
    <div class="text-[10px] text-slate-500">{receipt.purchase_date || "—"}</div>
    <div class="text-xs font-semibold tabular-nums">{fmtTotal}</div>
  </div>
</button>
