// Light/dark theme store. The initial `dark` class is set before paint by the
// inline script in app.html; this keeps a reactive copy and persists changes.
import { writable } from "svelte/store";
import { browser } from "$app/environment";

function initial() {
  if (!browser) return "light";
  const stored = localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export const theme = writable(initial());

function apply(value) {
  if (!browser) return;
  document.documentElement.classList.toggle("dark", value === "dark");
  localStorage.setItem("theme", value);
}

export function setTheme(value) {
  apply(value);
  theme.set(value);
}

export function toggleTheme() {
  theme.update((t) => {
    const next = t === "dark" ? "light" : "dark";
    apply(next);
    return next;
  });
}
