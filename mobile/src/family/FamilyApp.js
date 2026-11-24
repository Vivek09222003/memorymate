// Family / doctor side of the app. Three tabs:
//   Home    – anything urgent first, then each person you look after; tap a person for details
//   Connect – enter a code from a relative or patient
//   Me      – account and log out
// While the app is open it checks every 20 seconds and shows a notification for anything new.
// (Alerts while the app is fully closed need push notifications: a later step with Firebase.)
import { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, AppState, RefreshControl, Platform } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Notifications from "expo-notifications";
import { api, getBaseUrl } from "../api";
import { setupNotifications } from "../notify";
import { BigButton, Field, Label, Note, Row } from "../components/Big";
import { Header, TabBar, greeting } from "../components/Frame";
import AlertsBox from "./AlertsBox";
import ElderDetail from "./ElderDetail";
import { call, isDoctorLink, loadIds, roleFor, saveIds, timeOf } from "./common";
import { C, F, card } from "../theme";

const STATUS = {
  emergency: ["Needs help", C.danger, C.dangerSoft],
  attention: ["Missed medicine", C.warn, C.warnSoft],
  ok: ["All good", C.good, C.goodSoft],
};
const TABS = [["home", "home", "Home"], ["connect", "link", "Connect"], ["me", "person-circle", "Me"]];

const popNow = (title, body) => {
  if (Platform.OS === "web") return;   // the laptop browser shows the alerts on screen instead
  Notifications.scheduleNotificationAsync({ content: { title, body, sound: "default" }, trigger: null }).catch(() => {});
};

export default function FamilyApp({ me, onLogout }) {
  const [tab, setTab] = useState("home");
  const [rows, setRows] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [missed, setMissed] = useState([]);
  const [open, setOpen] = useState(null);         // the person whose details are shown
  const [detailKey, setDetailKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const seen = useRef({ alerts: new Set(), missed: new Set(), first: true });
  const hiddenMissed = useRef([]);

  const doctor = me.role === "DOCTOR" || rows.some((r) => isDoctorLink(r.relation));
  const people = doctor ? "patients" : "family";

  const refresh = useCallback(async () => {
    try {
      const [ov, al, mi] = await Promise.all([api("/family/overview"), api("/emergency/alerts"), api("/family/missed-medicines")]);
      const showMissed = mi.filter((m) => !hiddenMissed.current.includes(m.id));
      setRows(ov); setAlerts(al); setMissed(showMissed); setErr("");
      // Notify about anything new (not on the very first load, so opening the app doesn't buzz for old things).
      for (const a of al) {
        if (!seen.current.alerts.has(a.id) && !seen.current.first) popNow(`${a.elder_name} needs help`, a.source === "button" ? "Pressed the Help button" : a.message || "");
        seen.current.alerts.add(a.id);
      }
      for (const m of showMissed) {
        if (!seen.current.missed.has(m.id) && !seen.current.first) popNow(`Missed medicine: ${m.elder_name}`, `${m.title}, due ${timeOf(m.when)}`);
        seen.current.missed.add(m.id);
      }
      seen.current.first = false;
    } catch (e) { setErr(e.message); }
  }, []);

  useEffect(() => {
    (async () => { hiddenMissed.current = await loadIds("mm_missed_ok"); setupNotifications(); refresh(); })();
    const every = setInterval(refresh, 20000);
    // The open details refresh every minute (each view is logged for the elder, so not more often).
    const detail = setInterval(() => setDetailKey((k) => k + 1), 60000);
    const sub = AppState.addEventListener("change", (st) => { if (st === "active") refresh(); });
    const tap = Platform.OS === "web" ? null
      : Notifications.addNotificationResponseReceivedListener(() => { setTab("home"); setOpen(null); refresh(); });
    return () => { clearInterval(every); clearInterval(detail); sub.remove(); tap?.remove(); };
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

  const summary = (r) => [
    r.medicines_total ? `Medicines ${r.medicines_taken}/${r.medicines_total}` : null,
    r.next_appointment ? `Next: ${r.next_appointment}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <Header title={greeting(me.name)} subtitle={doctor ? "Your patients at a glance" : "Your family at a glance"} />

      <View style={[s.page, tab !== "home" && s.hidden]}>
        {open ? (
          <ElderDetail row={open} me={me} onBack={() => { setOpen(null); refresh(); }} refreshKey={detailKey} />
        ) : (
          <ScrollView contentContainerStyle={{ padding: 16 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={pull} />}>
            {!!err && <Note tone="danger">{err}</Note>}
            <AlertsBox alerts={alerts} missed={missed} onHandled={handled} onMissedOk={missedOk} />
            <Label>Your {people}</Label>
            {rows.length === 0 && (
              <View style={card}>
                <Text style={s.body}>You're not connected to anyone yet.</Text>
                <BigButton small kind="light" title="Connect with a code" icon="link-outline" onPress={() => setTab("connect")} style={{ marginTop: 12 }} />
              </View>
            )}
            {rows.map((r) => {
              const [label, color, bg] = STATUS[r.status] || STATUS.ok;
              return (
                <Pressable key={r.elder_id} onPress={() => setOpen(r)} accessibilityRole="button"
                           style={({ pressed }) => [card, s.person, pressed && { opacity: 0.85 }]}>
                  <View style={s.avatar}><Text style={s.avatarText}>{r.elder_name.trim()[0]?.toUpperCase()}</Text></View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.name}>{r.elder_name}</Text>
                    <Text style={s.muted} numberOfLines={1}>{summary(r) || roleFor(r.relation)}</Text>
                    <View style={[s.pill, { backgroundColor: bg }]}><Text style={[s.pillText, { color }]}>{label}</Text></View>
                  </View>
                  {r.elder_phone ? (
                    <Pressable onPress={() => call(r.elder_phone)} style={[s.callBtn, r.status === "emergency" && { backgroundColor: C.danger }]}
                               accessibilityLabel={`Call ${r.elder_name}`}>
                      <Ionicons name="call" size={20} color={r.status === "emergency" ? "#fff" : C.onBrand} />
                    </Pressable>
                  ) : <Ionicons name="chevron-forward" size={22} color={C.faint} />}
                </Pressable>
              );
            })}
            {rows.length > 0 && <Text style={s.foot}>Pull down to refresh</Text>}
          </ScrollView>
        )}
      </View>

      <View style={[s.page, tab !== "connect" && s.hidden]}>
        <Connect doctor={doctor} onJoined={() => { refresh(); setTab("home"); }} />
      </View>

      <View style={[s.page, tab !== "me" && s.hidden]}>
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <View style={[card, s.person]}>
            <View style={[s.avatar, { backgroundColor: C.brand }]}><Text style={[s.avatarText, { color: C.onBrand }]}>{me.name.trim()[0]?.toUpperCase()}</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={s.name}>{me.name}</Text>
              <Text style={s.muted}>{me.email} · {me.role === "DOCTOR" ? "Doctor" : "Family"}</Text>
            </View>
          </View>
          <Note>Alerts appear while this app is open or recently used. Keep it on the phone you check most.</Note>
          <View style={[card, { paddingVertical: 4 }]}>
            <Row icon="log-out-outline" title="Log out" tone="danger" onPress={onLogout} last />
          </View>
          <Text style={s.foot}>Connected to {getBaseUrl().replace(/^https?:\/\//, "")}</Text>
        </ScrollView>
      </View>

      <TabBar tabs={TABS} value={tab} dots={{ home: alerts.length > 0 || missed.length > 0 }}
              onChange={(key) => { setTab(key); if (key === "home") refresh(); }} />
    </View>
  );
}

function Connect({ doctor, onJoined }) {
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState(null);
  async function join() {
    setMsg(null);
    try {
      const l = await api("/family/join", { method: "POST", body: { code: code.trim().toUpperCase() } });
      setMsg({ tone: "good", text: `Connected to ${l.elder_name}.` }); setCode(""); onJoined();
    } catch (e) { setMsg({ tone: "danger", text: e.message }); }
  }
  return (
    <ScrollView contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
      <Label>Connect with a code</Label>
      <View style={card}>
        <Text style={s.body}>Ask your {doctor ? "patient" : "relative"} to tell MemoryMate, for example, "let Priya see my medicines". They'll get a code to give you.</Text>
        <Field value={code} onChangeText={setCode} placeholder="e.g. K7M2Q9RD" autoCapitalize="characters" autoCorrect={false}
               style={{ marginTop: 12, letterSpacing: 2 }} />
        <BigButton title="Connect" icon="link-outline" onPress={join} disabled={code.trim().length < 4} />
      </View>
      {msg && <Note tone={msg.tone}>{msg.text}</Note>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  page: { flex: 1 },
  hidden: { display: "none" },
  body: { fontSize: F.body - 1, color: C.ink, lineHeight: 26 },
  muted: { fontSize: F.small - 1, color: C.muted, marginTop: 2 },
  person: { flexDirection: "row", alignItems: "center", gap: 14 },
  avatar: { width: 50, height: 50, borderRadius: 25, backgroundColor: C.brandSoft, alignItems: "center", justifyContent: "center" },
  avatarText: { fontSize: 21, fontWeight: "700", color: C.brandInk },
  name: { fontSize: F.body + 1, fontWeight: "700", color: C.ink },
  pill: { alignSelf: "flex-start", borderRadius: 10, paddingHorizontal: 9, paddingVertical: 3, marginTop: 6 },
  pillText: { fontSize: 13, fontWeight: "700" },
  callBtn: { width: 46, height: 46, borderRadius: 23, backgroundColor: C.brand, alignItems: "center", justifyContent: "center" },
  foot: { fontSize: 13, color: C.faint, textAlign: "center", marginTop: 6 },
});
