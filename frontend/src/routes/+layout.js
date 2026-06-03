// Single-page app: render entirely on the client, no SSR/prerender needed
// since everything talks to the FastAPI backend at runtime.
export const ssr = false;
export const prerender = false;
