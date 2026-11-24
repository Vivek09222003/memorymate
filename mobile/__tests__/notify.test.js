// Phone alarms: the app turns the server's upcoming rings into notifications on the phone.
jest.mock("expo-notifications", () => ({
  setNotificationHandler: jest.fn(),
  cancelAllScheduledNotificationsAsync: jest.fn(() => Promise.resolve()),
  scheduleNotificationAsync: jest.fn(() => Promise.resolve("id")),
  SchedulableTriggerInputTypes: { DATE: "date", TIME_INTERVAL: "timeInterval" },
  AndroidImportance: { MAX: 5 },
  AndroidNotificationVisibility: { PUBLIC: 1 },
}));
jest.mock("../src/api", () => ({ api: jest.fn() }));

import * as Notifications from "expo-notifications";
import { api } from "../src/api";
import { ringAgainIn, syncAlarms } from "../src/notify";

const inMinutes = (m) => new Date(Date.now() + m * 60000).toISOString();
const ring = (over) => ({ alert_id: 1, reminder_id: 1, title: "BP medicine", kind: "MEDICINE", notes: "after dinner",
                          when: "Tue 24 Nov, 9:00 PM", ring_at: inMinutes(30), is_main: true, ...over });

beforeEach(() => jest.clearAllMocks());

test("asks the server for the next 48 hours and sets one alarm per ring", async () => {
  api.mockResolvedValueOnce([ring(), ring({ alert_id: null, ring_at: inMinutes(24 * 60 + 30) })]);
  expect(await syncAlarms()).toBe(2);
  expect(api).toHaveBeenCalledWith("/reminders/upcoming", { query: { hours: 48 } });
  expect(Notifications.cancelAllScheduledNotificationsAsync).toHaveBeenCalledTimes(1);
  expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledTimes(2);
});

test("the alarm shows the medicine, the time and the notes, at the right moment", async () => {
  const r = ring();
  api.mockResolvedValueOnce([r]);
  await syncAlarms();
  const { content, trigger } = Notifications.scheduleNotificationAsync.mock.calls[0][0];
  expect(content.title).toBe("💊 BP medicine");
  expect(content.body).toBe("It's time (9:00 PM) · after dinner");
  expect(trigger.type).toBe("date");
  expect(trigger.date.toISOString()).toBe(r.ring_at);
});

test("an 'evening before' alarm says Tomorrow", async () => {
  api.mockResolvedValueOnce([ring({ is_main: false, kind: "APPOINTMENT", title: "Eye check-up", notes: null })]);
  await syncAlarms();
  expect(Notifications.scheduleNotificationAsync.mock.calls[0][0].content.title).toBe("🏥 Tomorrow: Eye check-up");
});

test("skips rings that are already due (the app's Ringing now card handles those)", async () => {
  api.mockResolvedValueOnce([ring({ ring_at: inMinutes(-1) }), ring({ alert_id: 2 })]);
  expect(await syncAlarms()).toBe(1);
});

test("offline: keeps the old alarms instead of deleting them", async () => {
  api.mockRejectedValueOnce(new Error("Can't reach MemoryMate"));
  expect(await syncAlarms()).toBeNull();
  expect(Notifications.cancelAllScheduledNotificationsAsync).not.toHaveBeenCalled();
});

test("nothing planned: clears old alarms", async () => {
  api.mockResolvedValueOnce([]);
  expect(await syncAlarms()).toBe(0);
  expect(Notifications.cancelAllScheduledNotificationsAsync).toHaveBeenCalledTimes(1);
});

test("'Later' rings again from the phone after the given minutes", async () => {
  await ringAgainIn(10, "BP medicine", "after dinner");
  const { trigger } = Notifications.scheduleNotificationAsync.mock.calls[0][0];
  expect(trigger).toMatchObject({ type: "timeInterval", seconds: 600 });
});
