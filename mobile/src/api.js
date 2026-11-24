// Talks to the MemoryMate backend (FastAPI). Same routes as the /test page.
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";

let baseUrl = "";
let token = "";
let onLoggedOut = () => {};

export const setOnLoggedOut = (fn) => { onLoggedOut = fn; };
export const getBaseUrl = () => baseUrl;

// "192.168.1.5:8000" -> "http://192.168.1.5:8000"
export function cleanUrl(text) {
  let u = (text || "").trim().replace(/\/+$/, "");
  if (u && !/^https?:\/\//i.test(u)) u = "http://" + u;
  return u;
}

// While developing, the phone loads the app from the laptop (Expo, port 8081), and the MemoryMate
// backend runs on the same laptop (port 8000). So we can work out the server address ourselves:
// "192.168.1.7:8081" -> "http://192.168.1.7:8000". No typing the IP, even after changing Wi-Fi.
export function autoServer() {
  const host = Constants.expoConfig?.hostUri || Constants.expoGoConfig?.debuggerHost || "";
  const ip = host.split(":")[0];
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(ip) ? `http://${ip}:8000` : "";
}

// Saved between app starts: the server address and the login token (token in secure storage).
export async function loadSaved() {
  baseUrl = autoServer() || (await SecureStore.getItemAsync("mm_server")) || "";
  token = (await SecureStore.getItemAsync("mm_token")) || "";
  return { baseUrl, hasToken: !!token };
}

export async function saveServer(url) {
  baseUrl = cleanUrl(url);
  await SecureStore.setItemAsync("mm_server", baseUrl);
  return baseUrl;
}

export async function logout() {
  token = "";
  await SecureStore.deleteItemAsync("mm_token");
}

// fetch with a time limit, so a wrong address or a sleeping server doesn't hang forever
async function fetchWithTimeout(url, opts = {}, ms = 30000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } catch (e) {
    throw new Error(`Can't reach MemoryMate at ${baseUrl}. Is the server running, and is this phone on the same Wi-Fi?`);
  } finally {
    clearTimeout(timer);
  }
}

export async function api(path, { method = "GET", body, query } = {}) {
  const qs = query ? "?" + new URLSearchParams(query).toString() : "";
  const r = await fetchWithTimeout(baseUrl + path + qs, {
    method,
    headers: { Authorization: "Bearer " + token, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  }, path === "/chat" ? 60000 : 30000);
  if (r.status === 401) {
    await logout();
    onLoggedOut();
    throw new Error("Please log in again.");
  }
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `Error ${r.status}`);
  }
  return data;
}

// The login route takes a form (OAuth2), not JSON.
export async function login(email, password) {
  const form = `username=${encodeURIComponent(email.trim())}&password=${encodeURIComponent(password)}`;
  const r = await fetchWithTimeout(baseUrl + "/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!r.ok) throw new Error(r.status === 401 ? "Wrong email or password." : `Login failed (${r.status}).`);
  token = (await r.json()).access_token;
  await SecureStore.setItemAsync("mm_token", token);
  return api("/auth/me");
}

// Quick check that the address is right: /docs exists on every MemoryMate server.
export async function ping() {
  const r = await fetchWithTimeout(baseUrl + "/docs", {}, 8000);
  if (!r.ok) throw new Error(`The server answered with ${r.status}. Is this the MemoryMate address?`);
}
