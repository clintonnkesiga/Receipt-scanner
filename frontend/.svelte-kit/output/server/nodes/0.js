

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export const universal = {
  "ssr": false,
  "prerender": false
};
export const universal_id = "src/routes/+layout.js";
export const imports = ["_app/immutable/nodes/0.CcxRoAnI.js","_app/immutable/chunks/Cy_f113a.js","_app/immutable/chunks/6YTUu1EM.js","_app/immutable/chunks/DrfYys6d.js"];
export const stylesheets = ["_app/immutable/assets/0.DkD8ZyCJ.css"];
export const fonts = [];
