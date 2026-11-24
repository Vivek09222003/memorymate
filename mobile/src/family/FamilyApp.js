// Family / doctor side of the app. Three tabs:
//   Home    – urgent alerts first, then everyone you look after (most urgent first); tap one for details
//   Connect – enter a code from a relative or patient
//   Me      – account and log out
// While the app is open it checks every 20 seconds and pops up a notification for anything new.
// (Alerts while the app is fully closed need push notifications: a later step with Firebase.)
import { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, TextInput, ScrollView, StyleSheet, Pressable, AppState, RefreshControl } from "react-native";
import * as Notifications from "expo-notifications";
import { api, getBaseUrl } from "../api";
import { setupNotifications } from "../notify";
import { BigButton, Heading } from "../components/Big";
import AlertsBox from "./AlertsBox";
import ElderDetail from "./ElderDetail";
import { call, isDoctorLink, loadIds, roleFor, saveIds, timeOf } from "./common";
import { C, F, card } from "../theme";

const TAG = { emergency: "🚨 Needs help now", attention: "⚠️ Missed medicine", ok: "✅ All good" };
const EDGE = { emergency: C.red, attention: "#d9861a", ok: "#2e9e5b" };

const popNow = (title, body) =>
  Notifications.scheduleNotificationAsync({ content: { title, body, sound: "default" }, trigger: null }).catch(() => {});

export default function FamilyApp({ me, onLogout }) {
  const [tab, setTab] = useState("home");
  const [rows, setRows] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [missed, setMissed] = useState([]);
  const [open, setOpen] = useState(null);         // the elder whose details are shown
  const [detailKey, setDetailKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const seen = useRef({ alerts: new Set(), missed: new Set(), first: true });
  const hiddenMissed = useRef([]);

  const doctor = me.role === "DOCTOR" || rows.some((r) => isDoctorLink(r.relation));

  const refresh = useCallback(async () => {
    try {
      const [ov, al, mi] = await Promise.all([api("/family/overview"), api("/emergency/alerts"), api("/family/missed-medicines")]);
      const showMissed = mi.filter((m) => !hiddenMissed.current.includes(m.id));
      setRows(ov); setAlerts(al); setMissed(showMissed); setErr("");
      // Pop up anything new (not on the very first load, so opening the app doesn't buzz for old things).
      for (const a of al) {
        if (!seen.current.alerts.has(a.id) && !seen.current.first) popNow(`🚨 EMERGENCY: ${a.elder_name} needs help`, a.source === "button" ? "Pressed the Help button" : a.message || "");
        seen.current.alerts.add(a.id);
      }
      for (const m of showMissed) {
        if (!seen.current.missed.has(m.id) && !seen.current.first) popNow(`⚠️ Missed medicine: ${m.elder_name}`, `${m.title} · due ${timeOf(m.when)}`);
        seen.current.missed.add(m.id);
      }
      seen.current.first = false;
    } catch (e) { setErr(e.message); }
  }, []);

  useEffect(() => {
    (async () => { hiddenMissed.current = await loadIds("mm_missed_ok"); setupNotifications(); refresh(); })();
    const every = setInterval(refresh, 20000);
    // The open dashboard refreshes every minute (each view is logged for the elder, so not more often).
    const detail = setInterval(() => setDetailKey((k) => k + 1), 60000);
    const sub = AppState.addEventListener("change", (s) => { if (s === "active") refresh(); });
    const tap = Notifications.addNotificationResponseReceivedListener(() => { setTab("home"); setOpen(null); refresh(); });
    return () => { clearInterval(every); clearInterval(detail); sub.remove(); tap.remove(); };
  }, [refresh]);

  async function pull() { setLoading(true); await refresh(); setLoading(false); }

  async function handled(a) {
    try { await api(`/emergency/${a.id}/resolve`, { method: "POST" }); } catch (e) { setErr(e.message); }
    refresh();
  }
  async function missedOk(m) {
    hiddenMissed.current = [...hiddenMissed.current, m.id];
    await saveIds("mm_missed_ok", hiddenMissed.current);
    setMissed((list) => list.filter((x) => x.id !== m.id));
  }

  return (
    <View style={{ flex: 1 }}>
      <View style={s.header}>
        <Text style={s.brand}>🧠 MemoryMate</Text>
        <Text style={s.hello} numberOfLines={1}>{doctor ? "Doctor" : "Family"} · {me.name.split(" ")[0]}</Text>
      </View>

      <View style={[s.page, tab !== "home" && s.hidden]}>
        {open ? (
          <ElderDetail row={open} me={me} onBack={() => { setOpen(null); refresh(); }} refreshKey={detailKey} />
        ) : (
          <ScrollView contentContainerStyle={{ padding: 12 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={pull} />}>
            {!!err && <Text style={s.err}>{err}</Text>}
            <AlertsBox alerts={alerts} missed={missed} onHandled={handled} onMissedOk={missedOk} />
            <Heading>{doctor ? "My patients" : "My family"}</Heading>
            {rows.length === 0 && (
              <View style={card}>
                <Text style={s.body}>You're not connected to anyone yet. Ask your {doctor ? "patient" : "relative"} to tell MemoryMate "let {me.name.split(" ")[0]} see my information", then enter their code in the Connect tab.</Text>
              </View>
            )}
            {rows.map((r) => (
              <Pressable key={r.elder_id} onPress={() => setOpen(r)} style={({ pressed }) => [s.ov, { borderLeftColor: EDGE[r.status] }, r.status === "emergency" && { backgroundColor: "#fff0f2" }, r.status === "attention" && { backgroundColor: "#fffaf0" }, pressed && { opacity: 0.8 }]}>
                <Text style={s.ovName}>{r.elder_name}</Text>
                <Text style={s.muted}>{roleFor(r.relation)}</Text>
                <Text style={s.tag}>{TAG[r.status]}{r.emergency_since ? ` · since ${timeOf(r.emergency_since)}` : ""}</Text>
                {r.medicines_total !== null && (
                  <Text style={s.line}>Medicines today: {r.medicines_taken}/{r.medicines_total} taken{r.medicines_missed ? <Text style={{ color: C.red, fontWeight: "800" }}>{`, ${r.medicines_missed} missed`}</Text> : null}</Text>
                )}
                {r.next_appointment && <Text style={s.line}>Next: {r.next_appointment}, {r.next_appointment_when}</Text>}
                {r.my_suggestions_waiting > 0 && <Text style={s.muted}>{r.my_suggestions_waiting} of your suggestion{r.my_suggestions_waiting > 1 ? "s" : ""} waiting for an answer</Text>}
                <View style={s.row}>
                  <BigButton small title="Open" kind="light" onPress={() => setOpen(r)} style={{ flex: 1 }} />
                  {r.elder_phone && <BigButton small title="📞 Call" kind={r.status === "emergency" ? "red" : "redLight"} onPress={() => call(r.elder_phone)} style={{ flex: 1 }} />}
                </View>
              </Pressable>
            ))}
            <Text style={[s.muted, { textAlign: "center", marginTop: 6 }]}>Pull down to refresh · updates every 20 seconds</Text>
          </ScrollView>
        )}
      </View>

      <View style={[s.page, tab !== "connect" && s.hidden]}>
        <Connect doctor={doctor} onJoined={() => { refresh(); setTab("home"); }} />
      </View>

      <View style={[s.page, tab !== "me" && s.hidden]}>
        <ScrollView contentContainerStyle={{ padding: 12 }}>
          <View style={card}>
            <Text style={s.ovName}>{me.name}</Text>
            <Text style={s.muted}>{me.email} · {me.role === "DOCTOR" ? "Doctor" : "Family"} account</Text>
          </View>
          <View style={card}>
            <Text style={s.muted}>Alerts pop up while this app is open (or in the background for a short while). Keep it open on the phone you check most.</Text>
          </View>
          <View style={card}>
            <Text style={s.muted}>Connected to {getBaseUrl()}</Text>
            <BigButton small title="Log out" kind="redLight" onPress={onLogout} style={{ marginTop: 10 }} />
          </View>
        </ScrollView>
      </View>

      <View style={s.tabs}>
        {[["home", "🏠", "Home"], ["connect", "🔗", "Connect"], ["me", "👤", "Me"]].map(([key, icon, label]) => (
          <Pressable key={key} accessibilityRole="tab" accessibilityState={{ selected: tab === key }}
                     onPress={() => { setTab(key); if (key === "home") refresh(); }} style={[s.tab, tab === key && s.tabOn]}>
            <Text style={s.tabIcon}>{icon}</Text>
            <Text style={[s.tabText, tab === key && { color: C.ink, fontWeight: "800" }]}>{label}</Text>
            {key === "home" && (alerts.length > 0 || missed.length > 0) && <View style={s.dot} />}
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function Connect({ doctor, onJoined }) {
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  async function join() {
    setMsg("");
    try {
      const l = await api("/family/join", { method: "POST", body: { code: code.trim().toUpperCase() } });
      setMsg(`✅ Connected to ${l.elder_name}.`); setCode(""); onJoined();
    } catch (e) { setMsg(e.message); }
  }
  return (
    <ScrollView contentContainerStyle={{ padding: 12 }} keyboardShouldPersistTaps="handled">
      <View style={card}>
        <Heading>Got a code from a {doctor ? "patient" : "relative"}?</Heading>
        <Text style={s.muted}>They get it by telling MemoryMate, for example, "let Priya see my medicines".</Text>
        <TextInput style={s.input} value={code} onChangeText={setCode} placeholder="e.g. K7M2Q9RD" autoCapitalize="characters" autoCorrect={false} />
        <BigButton title="Connect" onPress={join} disabled={code.trim().length < 4} />
        {!!msg && <Text style={[s.body, { marginTop: 10 }]}>{msg}</Text>}
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  header: { backgroundColor: C.sun, paddingHorizontal: 16, paddingVertical: 12, flexDirection: "row", alignItems: "center" },
  brand: { fontSize: F.big, fontWeight: "800", color: C.ink, flex: 1 },
  hello: { fontSize: F.body - 2, color: C.ink, maxWidth: "50%" },
  page: { flex: 1 },
  hidden: { display: "none" },
  err: { fontSize: F.small, color: C.redDark, backgroundColor: C.redLight, padding: 12, borderRadius: 12, marginBottom: 12 },
  body: { fontSize: F.body - 2, color: C.ink, lineHeight: 26 },
  muted: { fontSize: F.small, color: C.muted },
  ov: { backgroundColor: "#f7f8fd", borderWidth: 2, borderColor: C.brandLight, borderLeftWidth: 10, borderRadius: 16, padding: 14, marginBottom: 10 },
  ovName: { fontSize: F.big, fontWeight: "800", color: C.ink },
  tag: { fontSize: F.small + 1, fontWeight: "700", color: C.ink, marginTop: 4 },
  line: { fontSize: F.small + 1, color: C.ink, marginTop: 2 },
  row: { flexDirection: "row", gap: 8, marginTop: 10 },
  input: { fontSize: F.body, borderWidth: 2, borderColor: C.line, borderRadius: 14, padding: 14, marginVertical: 10, color: C.ink, backgroundColor: "#fff", letterSpacing: 2 },
  tabs: { flexDirection: "row", borderTopWidth: 1, borderColor: C.line, backgroundColor: "#fff" },
  tab: { flex: 1, alignItems: "center", paddingVertical: 8 },
  tabOn: { backgroundColor: C.brandLight },
  tabIcon: { fontSize: 26 },
  tabText: { fontSize: F.small, color: C.muted, fontWeight: "600" },
  dot: { position: "absolute", top: 6, right: "30%", width: 12, height: 12, borderRadius: 6, backgroundColor: C.red },
});
