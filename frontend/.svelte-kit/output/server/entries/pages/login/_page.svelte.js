import { a as attr, e as escape_html } from "../../../chunks/root.js";
import "@sveltejs/kit/internal";
import "../../../chunks/exports.js";
import "../../../chunks/utils2.js";
import "@sveltejs/kit/internal/server";
import "../../../chunks/state.svelte.js";
import "../../../chunks/auth.js";
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let email = "";
    let password = "";
    let busy = false;
    $$renderer2.push(`<div class="min-h-screen flex items-center justify-center bg-slate-50 px-4"><div class="w-full max-w-sm"><div class="text-center mb-6"><div class="text-4xl">🧾</div> <h1 class="text-xl font-semibold mt-2">Receipt Scanner</h1> <p class="text-sm text-slate-500">Sign in to continue</p></div> <form class="bg-white rounded-xl shadow-sm p-6 space-y-4">`);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--> <label class="block text-sm"><span class="font-medium">Email</span> <input type="email"${attr("value", email)} required="" autocomplete="username" class="mt-1 block w-full rounded-lg border border-slate-300 p-2"/></label> <label class="block text-sm"><span class="font-medium">Password</span> <input type="password"${attr("value", password)} required="" autocomplete="current-password" class="mt-1 block w-full rounded-lg border border-slate-300 p-2"/></label> <button type="submit"${attr("disabled", busy, true)} class="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">${escape_html("Sign in")}</button></form></div></div>`);
  });
}
export {
  _page as default
};
