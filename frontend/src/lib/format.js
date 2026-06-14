// App-wide formatting helpers.
//
// Most data in this app is in Ugandan Shillings, so UGX is the default
// currency: users don't have to type it, and aggregate figures (dashboard,
// reports) are shown in UGX.
export const BASE_CURRENCY = "UGX";

/** Format a number with a currency prefix (defaults to UGX). */
export function money(n, currency = BASE_CURRENCY) {
  return `${currency || BASE_CURRENCY} ${Number(n || 0).toLocaleString()}`;
}

/** Format a plain number (no currency). */
export function num(n) {
  return Number(n || 0).toLocaleString();
}
