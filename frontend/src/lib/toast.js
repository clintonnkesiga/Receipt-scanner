import {
    writable
} from "svelte/store";

const store = writable( /** @type {{ id: number; message: string; type: string }[]} */ ([]));
let nextId = 0;

/**
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 * @param {number} duration  ms before auto-dismiss; 0 = permanent until closed
 */
function add(message, type = "info", duration = 3500) {
    const id = ++nextId;
    store.update((all) => [...all, {
        id,
        message,
        type
    }]);
    if (duration > 0) setTimeout(() => remove(id), duration);
}

function remove(id) {
    store.update((all) => all.filter((t) => t.id !== id));
}

export const toasts = {
    subscribe: store.subscribe,
    /** @param {string} msg */
    success: (msg, duration = 3500) => add(msg, "success", duration),
    /** @param {string} msg  — errors stay longer so the user can read them */
    error: (msg, duration = 5000) => add(msg, "error", duration),
    /** @param {string} msg */
    info: (msg, duration = 3500) => add(msg, "info", duration),
    remove,
};