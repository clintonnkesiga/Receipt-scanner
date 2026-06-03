export const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.BXZnAJMa.js",app:"_app/immutable/entry/app.D8QEaZoD.js",imports:["_app/immutable/entry/start.BXZnAJMa.js","_app/immutable/chunks/C2RqP4yt.js","_app/immutable/chunks/BxNR4gM4.js","_app/immutable/chunks/lbMZIK1k.js","_app/immutable/entry/app.D8QEaZoD.js","_app/immutable/chunks/BxNR4gM4.js","_app/immutable/chunks/D3jBbB0x.js","_app/immutable/chunks/DJeD3Vjr.js","_app/immutable/chunks/lbMZIK1k.js","_app/immutable/chunks/jEXtb3ww.js","_app/immutable/chunks/B26VIPKz.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js')),
			__memo(() => import('./nodes/3.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			},
			{
				id: "/login",
				pattern: /^\/login\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();
