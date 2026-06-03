import { a4 as attr, e as escape_html, a5 as ensure_array_like, a6 as attr_class, a7 as stringify, a3 as derived } from "../../chunks/index.js";
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let receipts = [];
    let busy = false;
    const total = derived(() => receipts.reduce((sum, r) => sum + (Number(r.total) || 0), 0));
    function badgeClass(category) {
      return category === "fuel" ? "bg-amber-100 text-amber-800" : category === "grocery" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700";
    }
    $$renderer2.push(`<div class="min-h-screen bg-slate-50 text-slate-800"><header class="bg-white border-b sticky top-0 z-10"><div class="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between"><h1 class="text-xl font-semibold flex items-center gap-2"><span>🧾</span> Receipt Scanner</h1> <a href="/api/receipts/export.csv" class="text-sm text-blue-600 hover:underline">Export CSV</a></div></header> <main class="max-w-4xl mx-auto px-4 py-6 space-y-6">`);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--> <section class="bg-white rounded-xl shadow-sm p-5"><label class="block"><span class="text-sm font-medium">Upload a receipt photo</span> <input type="file" accept="image/*"${attr("disabled", busy, true)} class="mt-2 block w-full text-sm file:mr-4 file:rounded-lg file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-white hover:file:bg-blue-700 file:cursor-pointer disabled:opacity-50"/></label> `);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--></section> `);
    {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--> <section class="bg-white rounded-xl shadow-sm p-5"><div class="flex items-center justify-between mb-3"><h2 class="font-semibold">History (${escape_html(receipts.length)})</h2> `);
    if (receipts.length) {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<span class="text-sm text-slate-500">Total: ${escape_html(total().toLocaleString())}</span>`);
    } else {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]--></div> `);
    if (receipts.length === 0) {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<p class="text-sm text-slate-500">No receipts yet — upload one above.</p>`);
    } else {
      $$renderer2.push("<!--[-1-->");
      $$renderer2.push(`<table class="w-full text-sm"><thead class="text-left text-slate-500 border-b"><tr><th class="py-2">Merchant</th><th>Date</th><th>Category</th><th class="text-right">Total</th><th></th></tr></thead><tbody><!--[-->`);
      const each_array_2 = ensure_array_like(receipts);
      for (let $$index_2 = 0, $$length = each_array_2.length; $$index_2 < $$length; $$index_2++) {
        let r = each_array_2[$$index_2];
        $$renderer2.push(`<tr class="border-b last:border-0 hover:bg-slate-50"><td class="py-2">${escape_html(r.merchant || "—")}</td><td>${escape_html(r.purchase_date || "—")}</td><td><span${attr_class(`text-xs rounded-full px-2 py-0.5 ${stringify(badgeClass(r.category))}`)}>${escape_html(r.category)}</span></td><td class="text-right tabular-nums">${escape_html(r.total != null ? `${r.currency || ""} ${Number(r.total).toLocaleString()}` : "—")}</td><td class="text-right"><button class="text-red-600 hover:underline text-xs">delete</button></td></tr>`);
      }
      $$renderer2.push(`<!--]--></tbody></table>`);
    }
    $$renderer2.push(`<!--]--></section></main></div>`);
  });
}
export {
  _page as default
};
