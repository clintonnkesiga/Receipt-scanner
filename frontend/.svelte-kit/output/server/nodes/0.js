

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export const universal = {
  "ssr": false,
  "prerender": false
};
export const universal_id = "src/routes/+layout.js";
export const imports = ["_app/immutable/nodes/0.Ba34ziYH.js","_app/immutable/chunks/DJeD3Vjr.js","_app/immutable/chunks/BxNR4gM4.js","_app/immutable/chunks/B26VIPKz.js"];
export const stylesheets = ["_app/immutable/assets/0.BUvwN7iR.css"];
export const fonts = [];
