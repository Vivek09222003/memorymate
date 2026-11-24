// MemoryMate mobile app. Elders get four tabs (Chat, Today, Help, Me); family and doctors get FamilyApp.
// Reminders ring from the phone itself; the app also checks the server every 20 seconds while open.
import { useCallback, useEffect, useRef, useState } from "react";
import { View, StyleSheet, AppState, ActivityIndicator } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import * as Notifications from "expo-notifications";
import { api, loadSaved, logout, setOnLoggedOut } from "./src/api";
import { setupNotifications, syncAlarms } from "./src/notify";
import LoginScreen from "./src/screens/LoginScreen";
import ChatScreen from "./src/screens/ChatScreen";
import TodayScreen from "./src/screens/TodayScreen";
import HelpScreen from "./src/screens/HelpScreen";
import MeScreen from "./src/screens/MeScreen";
import FamilyApp from "./src/family/FamilyApp";
import { Banner, Header, TabBar, greeting, todayLine } from "./src/components/Frame";
import { C } from "./src/theme";

const TABS = [
  ["chat", "chatbubble-ellipses", "Talk"],
  ["today", "today", "Today"],
  ["help", "alert-circle", "Help"],
  ["me", "person-circle", "Me"],
];

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <Main />
    </SafeAreaProvider>
  );
}

function Main() {
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState("chat");
  const [alert, setAlert] = useState(null);     // open emergency
  const [ringing, setRinging] = useState([]);   // reminders ringing now
  const [todayKey, setTodayKey] = useState(0);  // bump to reload the Today tab
  const appState = useRef(AppState.currentState);

  const signOut = useCallback(async () => {
    await logout();
    await Notifications.cancelAllScheduledNotificationsAsync();
    setMe(null); setAlert(null); setRinging([]); setTab("chat");
  }, []);

  // Start: saved server + token? Then go straight in.
  useEffect(() => {
    setOnLoggedOut(() => setMe(null));
    (async () => {
      const saved = await loadSaved();
      if (saved.baseUrl && saved.hasToken) {
        try { setMe(await api("/auth/me")); } catch (e) { /* show login */ }
      }
      setReady(true);
    })();
  }, []);

  // Check what's ringing and whether an emergency is open.
  const poll = useCallback(async () => {
    if (!me || me.role !== "ELDER") return;
    try {
      const [due, active] = await Promise.all([api("/reminders/due"), api("/emergency/active")]);
      setRinging(due); setAlert(active);
    } catch (e) { /* offline: the phone alarms still ring */ }
  }, [me]);

  // After login: allow notifications, set the phone alarms, and keep checking every 20 s while open.
  useEffect(() => {
    if (!me || me.role !== "ELDER") return;
    setupNotifications().then(syncAlarms);
    poll();
    const every = setInterval(poll, 20000);
    const sub = AppState.addEventListener("change", (next) => {
      if (appState.current.match(/inactive|background/) && next === "active") { poll(); syncAlarms(); setTodayKey((k) => k + 1); }
      appState.current = next;
    });
    // Tapping a reminder notification opens the Today tab.
    const tap = Notifications.addNotificationResponseReceivedListener(() => { setTab("today"); setTodayKey((k) => k + 1); poll(); });
    return () => { clearInterval(every); sub.remove(); tap.remove(); };
  }, [me, poll]);

  if (!ready) return <View style={s.loading}><ActivityIndicator size="large" color={C.brand} /></View>;
  if (!me) return <SafeAreaView style={s.screen}><LoginScreen onLogin={setMe} /></SafeAreaView>;

  // Family members and doctors get their own screens.
  if (me.role !== "ELDER") {
    return <SafeAreaView style={s.screen}><FamilyApp me={me} onLogout={signOut} /></SafeAreaView>;
  }

  const onEmergency = (a) => { setAlert(a); setTab("help"); };
  return (
    <SafeAreaView style={s.screen} edges={["top", "left", "right", "bottom"]}>
      <Header title={greeting(me.name)} subtitle={todayLine()} />

      {alert && tab !== "help" && (
        <Banner tone="danger" icon="alert-circle" text="Your help alert is on. Tap to see who to call." onPress={() => setTab("help")} />
      )}
      {ringing.length > 0 && tab !== "today" && (
        <Banner tone="warn" icon="alarm-outline"
                text={`Time for: ${ringing[0].title}${ringing.length > 1 ? ` and ${ringing.length - 1} more` : ""}`}
                onPress={() => { setTab("today"); setTodayKey((k) => k + 1); }} />
      )}

      {/* All tabs stay mounted, so the chat isn't lost when you switch. */}
      <View style={[s.page, tab !== "chat" && s.hidden]}><ChatScreen me={me} onEmergency={onEmergency} /></View>
      <View style={[s.page, tab !== "today" && s.hidden]}><TodayScreen refreshKey={todayKey} /></View>
      <View style={[s.page, tab !== "help" && s.hidden]}><HelpScreen alert={alert} setAlert={setAlert} /></View>
      <View style={[s.page, tab !== "me" && s.hidden]}><MeScreen me={me} setMe={setMe} onLogout={signOut} /></View>

      <TabBar tabs={TABS} value={tab} dots={{ today: ringing.length > 0, help: !!alert }}
              onChange={(key) => { setTab(key); if (key === "today") setTodayKey((k) => k + 1); }} />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: C.bg },
  screen: { flex: 1, backgroundColor: C.bg },
  page: { flex: 1 },
  hidden: { display: "none" },
});
