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
		client: {start:"_app/immutable/entry/start.DAZCw8v0.js",app:"_app/immutable/entry/app.DB59E9EC.js",imports:["_app/immutable/entry/start.DAZCw8v0.js","_app/immutable/chunks/DDNWmOsh.js","_app/immutable/chunks/6YTUu1EM.js","_app/immutable/chunks/BkTOMH4F.js","_app/immutable/entry/app.DB59E9EC.js","_app/immutable/chunks/6YTUu1EM.js","_app/immutable/chunks/DjlLskI5.js","_app/immutable/chunks/Cy_f113a.js","_app/immutable/chunks/BkTOMH4F.js","_app/immutable/chunks/CottM3q7.js","_app/immutable/chunks/DrfYys6d.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js')),
			__memo(() => import('./nodes/3.js')),
			__memo(() => import('./nodes/4.js')),
			__memo(() => import('./nodes/5.js'))
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
				id: "/account",
				pattern: /^\/account\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			},
			{
				id: "/login",
				pattern: /^\/login\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 4 },
				endpoint: null
			},
			{
				id: "/users",
				pattern: /^\/users\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 5 },
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
