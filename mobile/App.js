// MemoryMate mobile app. Elders get four tabs (Chat, Today, Help, Me); family and doctors get FamilyApp.
// Reminders ring from the phone itself; the app also checks the server every 20 seconds while open.
import { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, Pressable, StyleSheet, AppState, ActivityIndicator } from "react-native";
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
import { C, F } from "./src/theme";

const TABS = [
  ["chat", "💬", "Chat"],
  ["today", "📋", "Today"],
  ["help", "🚨", "Help"],
  ["me", "👤", "Me"],
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
      <View style={s.header}>
        <Text style={s.brand}>🧠 MemoryMate</Text>
        <Text style={s.hello} numberOfLines={1}>Hi, {me.name.split(" ")[0]}</Text>
      </View>

      {alert && tab !== "help" && (
        <Pressable style={s.redBar} onPress={() => setTab("help")}>
          <Text style={s.barText}>🚨 Help alert is on. Tap to see who to call.</Text>
        </Pressable>
      )}
      {ringing.length > 0 && tab !== "today" && (
        <Pressable style={s.ringBar} onPress={() => { setTab("today"); setTodayKey((k) => k + 1); }}>
          <Text style={s.barText}>⏰ {ringing[0].title}{ringing.length > 1 ? ` and ${ringing.length - 1} more` : ""}: tap to answer</Text>
        </Pressable>
      )}

      {/* All tabs stay mounted, so the chat isn't lost when you switch. */}
      <View style={[s.page, tab !== "chat" && s.hidden]}><ChatScreen me={me} onEmergency={onEmergency} /></View>
      <View style={[s.page, tab !== "today" && s.hidden]}><TodayScreen refreshKey={todayKey} /></View>
      <View style={[s.page, tab !== "help" && s.hidden]}><HelpScreen alert={alert} setAlert={setAlert} /></View>
      <View style={[s.page, tab !== "me" && s.hidden]}><MeScreen me={me} setMe={setMe} onLogout={signOut} /></View>

      <View style={s.tabs}>
        {TABS.map(([key, icon, label]) => (
          <Pressable key={key} accessibilityRole="tab" accessibilityState={{ selected: tab === key }}
                     onPress={() => { setTab(key); if (key === "today") setTodayKey((k) => k + 1); }}
                     style={[s.tab, tab === key && s.tabOn, key === "help" && s.tabHelp]}>
            <Text style={s.tabIcon}>{icon}</Text>
            <Text style={[s.tabText, tab === key && { color: C.ink, fontWeight: "800" }, key === "help" && { color: C.red }]}>{label}</Text>
            {key === "today" && ringing.length > 0 && <View style={s.dot} />}
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: C.bg },
  screen: { flex: 1, backgroundColor: C.bg },
  header: { backgroundColor: C.sun, paddingHorizontal: 16, paddingVertical: 12, flexDirection: "row", alignItems: "center" },
  brand: { fontSize: F.big, fontWeight: "800", color: C.ink, flex: 1 },
  hello: { fontSize: F.body, color: C.ink, maxWidth: "45%" },
  redBar: { backgroundColor: C.red, padding: 12 },
  ringBar: { backgroundColor: C.ink, padding: 12 },
  barText: { color: "#fff", fontSize: F.body, fontWeight: "700", textAlign: "center" },
  page: { flex: 1 },
  hidden: { display: "none" },
  tabs: { flexDirection: "row", borderTopWidth: 1, borderColor: C.line, backgroundColor: "#fff" },
  tab: { flex: 1, alignItems: "center", paddingVertical: 8 },
  tabOn: { backgroundColor: C.brandLight },
  tabHelp: {},
  tabIcon: { fontSize: 26 },
  tabText: { fontSize: F.small, color: C.muted, fontWeight: "600" },
  dot: { position: "absolute", top: 6, right: "28%", width: 12, height: 12, borderRadius: 6, backgroundColor: C.red },
  title: { fontSize: F.huge, fontWeight: "800", color: C.ink, marginBottom: 12 },
  body: { fontSize: F.body, color: C.ink, marginBottom: 20, lineHeight: 28 },
});
