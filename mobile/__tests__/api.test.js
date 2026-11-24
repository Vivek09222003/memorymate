// The connection to the backend: server address, login, and friendly errors.
jest.mock("expo-secure-store", () => {
  const store = {};
  return {
    getItemAsync: jest.fn(async (k) => store[k] ?? null),
    setItemAsync: jest.fn(async (k, v) => { store[k] = v; }),
    deleteItemAsync: jest.fn(async (k) => { delete store[k]; }),
  };
});
jest.mock("expo-constants", () => ({ __esModule: true, default: { expoConfig: { hostUri: "192.168.1.7:8081" } } }));

import Constants from "expo-constants";
import { api, autoServer, cleanUrl, getBaseUrl, login, saveServer, setOnLoggedOut } from "../src/api";

const reply = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

beforeEach(() => { global.fetch = jest.fn(); });

describe("server address", () => {
  test("cleanUrl adds http:// and removes the trailing slash", () => {
    expect(cleanUrl("192.168.1.5:8000")).toBe("http://192.168.1.5:8000");
    expect(cleanUrl(" http://192.168.1.5:8000/ ")).toBe("http://192.168.1.5:8000");
    expect(cleanUrl("https://memorymate.onrender.com")).toBe("https://memorymate.onrender.com");
  });

  test("autoServer uses the laptop that sent the app, with port 8000", () => {
    expect(autoServer()).toBe("http://192.168.1.7:8000");
  });

  test("autoServer gives up on a non-IP host (e.g. an Expo tunnel)", () => {
    Constants.expoConfig.hostUri = "abc-anonymous.exp.direct";
    expect(autoServer()).toBe("");
    Constants.expoConfig.hostUri = "192.168.1.7:8081";
  });
});

describe("api()", () => {
  beforeAll(() => saveServer("192.168.1.7:8000"));

  test("logs in with a form, then loads the profile with the token", async () => {
    fetch.mockReturnValueOnce(reply(200, { access_token: "T123" }))
         .mockReturnValueOnce(reply(200, { name: "Vivek", role: "ELDER" }));
    const me = await login("vivek@example.com", "test1234");
    expect(me.name).toBe("Vivek");
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe("http://192.168.1.7:8000/auth/login");
    expect(opts.headers["Content-Type"]).toBe("application/x-www-form-urlencoded");
    expect(opts.body).toContain("username=vivek%40example.com");
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe("Bearer T123");
  });

  test("wrong password gives a clear message", async () => {
    fetch.mockReturnValueOnce(reply(401, { detail: "Incorrect" }));
    await expect(login("vivek@example.com", "nope")).rejects.toThrow("Wrong email or password.");
  });

  test("sends JSON and query strings", async () => {
    fetch.mockReturnValueOnce(reply(200, []));
    await api("/reminders/alerts/5/snooze", { method: "POST", query: { minutes: 10 } });
    expect(fetch.mock.calls[0][0]).toBe(`${getBaseUrl()}/reminders/alerts/5/snooze?minutes=10`);
    fetch.mockReturnValueOnce(reply(200, { reply: "Hi" }));
    await api("/chat", { method: "POST", body: { message: "Hello" } });
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ message: "Hello" });
  });

  test("shows the server's error message", async () => {
    fetch.mockReturnValueOnce(reply(404, { detail: "That code isn't valid (or was already used)." }));
    await expect(api("/family/join", { method: "POST", body: { code: "X" } })).rejects.toThrow("That code isn't valid");
  });

  test("an expired login logs out", async () => {
    const loggedOut = jest.fn();
    setOnLoggedOut(loggedOut);
    fetch.mockReturnValueOnce(reply(401, { detail: "expired" }));
    await expect(api("/auth/me")).rejects.toThrow("Please log in again.");
    expect(loggedOut).toHaveBeenCalled();
  });

  test("no connection gives a helpful message, not a crash", async () => {
    fetch.mockImplementationOnce(() => Promise.reject(new TypeError("Network request failed")));
    await expect(api("/reminders/today")).rejects.toThrow(/same Wi-Fi/);
  });
});
