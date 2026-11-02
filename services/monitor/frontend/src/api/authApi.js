import { postJson } from "./client";
import { endpoints } from "./endpoints";

/** Resolves to { name } on success; throws ApiError (client.js) on a wrong username/password (401). The
 * backend's login response carries only the display name — never an id the frontend has any use for. */
export async function login(username, password) {
  const body = await postJson(endpoints.login(), { username, password });
  return { name: String(body?.name ?? "") };
}

export async function logout() {
  await postJson(endpoints.logout());
}
