import "clsx";
import "@sveltejs/kit/internal";
import "../../chunks/exports.js";
import "../../chunks/utils2.js";
import "@sveltejs/kit/internal/server";
import "../../chunks/root.js";
import "../../chunks/state.svelte.js";
import "../../chunks/auth.js";
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<div class="min-h-screen flex items-center justify-center text-slate-400 text-sm">Loading…</div>`);
    }
    $$renderer2.push(`<!--]-->`);
  });
}
export {
  _page as default
};
