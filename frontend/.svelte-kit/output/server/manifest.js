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
		client: {start:"_app/immutable/entry/start.DuPr_Goa.js",app:"_app/immutable/entry/app.D1LTSvCu.js",imports:["_app/immutable/entry/start.DuPr_Goa.js","_app/immutable/chunks/BE0Nx0Y5.js","_app/immutable/chunks/BOtoKqDl.js","_app/immutable/chunks/pbeopv4P.js","_app/immutable/entry/app.D1LTSvCu.js","_app/immutable/chunks/BOtoKqDl.js","_app/immutable/chunks/D-D8j0bk.js","_app/immutable/chunks/4N7XLCfk.js","_app/immutable/chunks/pbeopv4P.js","_app/immutable/chunks/BzyA1_3j.js","_app/immutable/chunks/C2XbQzNU.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js'))
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
