

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export const universal = {
  "ssr": false,
  "prerender": false
};
export const universal_id = "src/routes/+layout.js";
export const imports = ["_app/immutable/nodes/0.BwLaAv2b.js","_app/immutable/chunks/4N7XLCfk.js","_app/immutable/chunks/BOtoKqDl.js","_app/immutable/chunks/C2XbQzNU.js"];
export const stylesheets = ["_app/immutable/assets/0.DoliFtoW.css"];
export const fonts = [];
