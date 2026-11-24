// Reminders ring from the PHONE itself (local notifications), so they come on time even if the
// server is asleep or the app is closed. We ask the server for the next 48 hours of rings and
// schedule each one. Every sync replaces the old alarms, so done / cancelled reminders disappear.
import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { api } from "./api";

const CHANNEL = "reminders";
const EMOJI = { MEDICINE: "💊", APPOINTMENT: "🏥", BIRTHDAY: "🎂", CALL: "📞", TASK: "✅" };

// Show the alert with sound even while the app is open.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function setupNotifications() {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: "Reminders",
      importance: Notifications.AndroidImportance.MAX,
      sound: "default",
      vibrationPattern: [0, 400, 250, 400],
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
    });
  }
  const now = await Notifications.getPermissionsAsync();
  if (now.granted) return true;
  const asked = await Notifications.requestPermissionsAsync();
  return asked.granted;
}

let syncing = false;

// Returns how many alarms are set, or null if the server couldn't be reached (old alarms are kept).
export async function syncAlarms() {
  if (syncing) return null;
  syncing = true;
  try {
    let rings;
    try {
      rings = await api("/reminders/upcoming", { query: { hours: 48 } });
    } catch (e) {
      return null; // offline: keep the alarms we already have
    }
    await Notifications.cancelAllScheduledNotificationsAsync();
    const soon = Date.now() + 5000;
    let count = 0;
    for (const r of rings) {
      const at = new Date(r.ring_at);
      if (at.getTime() < soon) continue; // ringing now: the app's "Ringing now" card handles it
      const time = r.when.split(", ").pop();
      await Notifications.scheduleNotificationAsync({
        content: {
          title: `${EMOJI[r.kind] || "⏰"} ${r.is_main ? "" : "Tomorrow: "}${r.title}`,
          body: [r.is_main ? `It's time (${time})` : `At ${r.when}`, r.notes].filter(Boolean).join(" · "),
          sound: "default",
          data: { alertId: r.alert_id, reminderId: r.reminder_id },
        },
        trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: at, channelId: CHANNEL },
      });
      count += 1;
    }
    return count;
  } finally {
    syncing = false;
  }
}

// "Later": ring again from the phone in a few minutes, even if the server is asleep.
export async function ringAgainIn(minutes, title, notes) {
  await Notifications.scheduleNotificationAsync({
    content: { title: `⏰ ${title}`, body: notes || "Reminder", sound: "default" },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL, seconds: minutes * 60, channelId: CHANNEL },
  });
}
