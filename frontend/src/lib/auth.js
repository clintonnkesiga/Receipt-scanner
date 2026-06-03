import { writable } from "svelte/store";
import { browser } from "$app/environment";

const KEY = "rs_token";

const initial = browser ? localStorage.getItem(KEY) : null;
export const token = writable(initial);

// Persist token changes to localStorage so sessions survive refreshes.
token.subscribe((value) => {
  if (!browser) return;
  if (value) localStorage.setItem(KEY, value);
  else localStorage.removeItem(KEY);
});

export function getToken() {
  return browser ? localStorage.getItem(KEY) : null;
}

export function setToken(value) {
  token.set(value);
}

export function logout() {
  token.set(null);
}
