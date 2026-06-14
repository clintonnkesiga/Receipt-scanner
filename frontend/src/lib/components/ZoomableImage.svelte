<script>
  // A thumbnail that opens a full-screen lightbox with zoom (wheel / buttons /
  // double-click) and drag-to-pan. Works with any image URL (incl. object URLs).
  let { src, alt = "", thumbClass = "" } = $props();

  let open = $state(false);
  let scale = $state(1);
  let tx = $state(0);
  let ty = $state(0);

  let dragging = $state(false);
  let startX = 0, startY = 0, originX = 0, originY = 0;

  const MIN = 1, MAX = 6;

  function openLightbox() {
    open = true;
    reset();
  }
  function close() {
    open = false;
  }
  function reset() {
    scale = 1;
    tx = 0;
    ty = 0;
  }
  function zoomBy(delta) {
    scale = Math.min(MAX, Math.max(MIN, +(scale + delta).toFixed(2)));
    if (scale === 1) {
      tx = 0;
      ty = 0;
    }
  }
  function onWheel(e) {
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 0.3 : -0.3);
  }
  function onDoubleClick() {
    if (scale > 1) reset();
    else scale = 2.5;
  }
  function onDown(e) {
    if (scale <= 1) return;
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    originX = tx;
    originY = ty;
  }
  function onMove(e) {
    if (!dragging) return;
    tx = originX + (e.clientX - startX);
    ty = originY + (e.clientY - startY);
  }
  function onUp() {
    dragging = false;
  }
  function onKey(e) {
    if (!open) return;
    if (e.key === "Escape") close();
    else if (e.key === "+" || e.key === "=") zoomBy(0.3);
    else if (e.key === "-" || e.key === "_") zoomBy(-0.3);
    else if (e.key === "0") reset();
  }
</script>

<svelte:window onkeydown={onKey} onmouseup={onUp} onmousemove={onMove} />

<button
  type="button"
  onclick={openLightbox}
  class="block mx-auto cursor-zoom-in focus:outline-none focus:ring-2 focus:ring-blue-400 rounded-lg"
  aria-label="Zoom image"
  title="Click to zoom"
>
  <img {src} {alt} class={thumbClass} />
</button>

{#if open}
  <div
    role="presentation"
    class="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center overflow-hidden"
    onclick={close}
  >
    <!-- Controls -->
    <div
      class="absolute top-4 right-4 z-10 flex items-center gap-1.5 text-white"
      onclick={(e) => e.stopPropagation()}
      role="presentation"
    >
      <button type="button" aria-label="Zoom out" onclick={() => zoomBy(-0.3)}
        class="w-9 h-9 rounded-full bg-white/10 hover:bg-white/25 text-xl leading-none flex items-center justify-center">−</button>
      <button type="button" onclick={reset}
        class="px-3 h-9 rounded-full bg-white/10 hover:bg-white/25 text-sm tabular-nums">{Math.round(scale * 100)}%</button>
      <button type="button" aria-label="Zoom in" onclick={() => zoomBy(0.3)}
        class="w-9 h-9 rounded-full bg-white/10 hover:bg-white/25 text-xl leading-none flex items-center justify-center">+</button>
      <button type="button" aria-label="Close" onclick={close}
        class="w-9 h-9 rounded-full bg-white/10 hover:bg-white/25 text-lg leading-none flex items-center justify-center ml-1">✕</button>
    </div>

    <img
      {src}
      {alt}
      draggable="false"
      onwheel={onWheel}
      onmousedown={onDown}
      ondblclick={onDoubleClick}
      onclick={(e) => e.stopPropagation()}
      style="transform: translate({tx}px, {ty}px) scale({scale}); transition: {dragging ? 'none' : 'transform 0.12s ease-out'}; cursor: {scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in'};"
      class="max-h-[90vh] max-w-[92vw] select-none rounded-lg shadow-2xl"
    />

    <div class="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/60 text-xs">
      scroll or +/− to zoom · drag to pan · double-click to reset
    </div>
  </div>
{/if}
