import { goto } from "$app/navigation";
import { getToken } from "$lib/auth";
import { getMe } from "$lib/api";

/**
 * Client-side route guard. Returns the current user, or redirects and
 * returns null. Pass { superadmin: true } to require the super-admin role.
 */
export async function requireUser({ superadmin = false } = {}) {
  if (!getToken()) {
    goto("/login");
    return null;
  }
  try {
    const user = await getMe();
    if (superadmin && user.role !== "superadmin") {
      goto("/");
      return null;
    }
    return user;
  } catch {
    goto("/login");
    return null;
  }
}
