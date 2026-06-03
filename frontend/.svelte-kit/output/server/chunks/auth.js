import { w as writable } from "./exports.js";
const initial = null;
const token = writable(initial);
token.subscribe((value) => {
  return;
});
