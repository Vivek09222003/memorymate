// Today: what's ringing now, today's checklist (medicines taken / missed), and things family or the
// doctor suggested that are waiting for a yes or no.
import { useCallback, useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet, RefreshControl } from "react-native";
import { api } from "../api";
import { ringAgainIn, syncAlarms } from "../notify";
import { BigButton, Heading } from "../components/Big";
import { C, F, card } from "../theme";

const EMOJI = { MEDICINE: "💊", APPOINTMENT: "🏥", BIRTHDAY: "🎂", CALL: "📞", TASK: "✅" };
const STATUS = {
  DONE: ["✅ Done", C.green],
  MISSED: ["❌ Missed", C.red],
  DUE: ["⏰ Now", C.orange],
  SCHEDULED: ["Later", C.muted],
  SKIPPED: ["Cancelled", C.muted],
};
const timeOf = (when) => when.split(", ").pop();

export default function TodayScreen({ refreshKey }) {
  const [due, setDue] = useState([]);
  const [today, setToday] = useState([]);
  const [sugs, setSugs] = useState([]);
  const [notes, setNotes] = useState([]);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, t, s, n] = await Promise.all([
        api("/reminders/due"), api("/reminders/today"), api("/reminders/suggestions"), api("/memories/from-others"),
      ]);
      setDue(d); setToday(t); setSugs(s); setNotes(n); setMsg("");
    } catch (e) { setMsg(e.message); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  async function act(fn, okText) {
    try { await fn(); setMsg(okText || ""); } catch (e) { setMsg(e.message); }
    await load();
    syncAlarms();
  }

  const done = (a) => act(() => api(`/reminders/alerts/${a.id}/done`, { method: "POST" }), `Marked "${a.title}" as done.`);
  const later = (a) => act(async () => {
    try { await api(`/reminders/alerts/${a.id}/snooze`, { method: "POST", query: { minutes: 10 } }); }
    catch (e) { await ringAgainIn(10, a.title, a.notes); } // server can't snooze it: ring from the phone instead
  }, "OK, I'll remind you again in 10 minutes.");

  return (
    <ScrollView contentContainerStyle={{ padding: 12 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      {!!msg && <Text style={s.msg}>{msg}</Text>}

      {due.map((a) => (
        <View key={a.id} style={[card, s.ringing]}>
          <Text style={s.ringTitle}>{EMOJI[a.kind] || "⏰"} {a.title}</Text>
          <Text style={s.ringSub}>{a.is_main ? "It's time" : "Tomorrow"} · {a.when}{a.notes ? "\n" + a.notes : ""}</Text>
          <View style={s.row}>
            <BigButton title={a.kind === "MEDICINE" ? "✔ Taken" : "✔ Done"} kind="green" onPress={() => done(a)} style={{ flex: 1 }} />
            <BigButton title="Later" kind="light" onPress={() => later(a)} style={{ flex: 1 }} />
          </View>
        </View>
      ))}

      <View style={card}>
        <Heading>Today</Heading>
        {today.length === 0 && <Text style={s.muted}>Nothing planned for today. Tell me in the chat, like "Remind me to take my BP medicine every day at 9 pm".</Text>}
        {today.map((a) => {
          const [label, color] = STATUS[a.status] || [a.status, C.muted];
          const canDo = a.status === "SCHEDULED" || a.status === "MISSED" || a.status === "DUE";
          return (
            <View key={a.id} style={s.item}>
              <View style={{ flex: 1 }}>
                <Text style={s.itemTitle}>{EMOJI[a.kind] || "•"} {a.title}</Text>
                <Text style={s.muted}>{timeOf(a.when)}{a.notes ? " · " + a.notes : ""}</Text>
                <Text style={[s.status, { color }]}>{label}</Text>
              </View>
              {canDo && <BigButton small title={a.status === "MISSED" ? "Took it late" : "Done"} kind="light" onPress={() => done(a)} />}
            </View>
          );
        })}
      </View>

      {sugs.length > 0 && (
        <View style={card}>
          <Heading>Suggested for you</Heading>
          {sugs.map((r) => (
            <View key={r.id} style={s.sug}>
              <Text style={s.itemTitle}>{EMOJI[r.kind] || "•"} {r.title}</Text>
              <Text style={s.muted}>{r.due_local}{r.repeat !== "NONE" ? ` · ${r.repeat.toLowerCase()}` : ""}{r.notes ? " · " + r.notes : ""}</Text>
              <Text style={s.from}>From {r.suggested_by || "family"}</Text>
              <View style={s.row}>
                <BigButton small title="✔ Accept" kind="green" style={{ flex: 1 }}
                           onPress={() => act(() => api(`/reminders/${r.id}/accept`, { method: "POST" }), "Accepted. It will remind you.")} />
                <BigButton small title="✖ No thanks" kind="light" style={{ flex: 1 }}
                           onPress={() => act(() => api(`/reminders/${r.id}/decline`, { method: "POST" }))} />
              </View>
            </View>
          ))}
        </View>
      )}

      {notes.length > 0 && (
        <View style={card}>
          <Heading>Notes from your doctor</Heading>
          {notes.map((n) => (
            <View key={n.id} style={s.sug}>
              <Text style={s.itemTitle}>{n.text}</Text>
              <Text style={s.from}>From {n.from_name} · {n.created_at}</Text>
              <View style={s.row}>
                <BigButton small title="✔ Keep it" kind="green" style={{ flex: 1 }}
                           onPress={() => act(() => api(`/memories/${n.id}/approve`, { method: "POST" }), "Saved to your memory.")} />
                <BigButton small title="✖ No" kind="light" style={{ flex: 1 }}
                           onPress={() => act(() => api(`/memories/${n.id}/reject`, { method: "POST" }))} />
              </View>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  msg: { fontSize: F.small, color: C.ink, backgroundColor: C.brandLight, padding: 12, borderRadius: 12, marginBottom: 12 },
  ringing: { backgroundColor: C.ink },
  ringTitle: { fontSize: F.huge, fontWeight: "800", color: "#fff" },
  ringSub: { fontSize: F.body, color: "#dfe3ff", marginVertical: 8 },
  row: { flexDirection: "row", gap: 10, marginTop: 8 },
  item: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10, borderTopWidth: 1, borderColor: C.brandLight },
  itemTitle: { fontSize: F.body, fontWeight: "700", color: C.ink },
  status: { fontSize: F.small, fontWeight: "700", marginTop: 2 },
  muted: { fontSize: F.small, color: C.muted },
  sug: { paddingVertical: 10, borderTopWidth: 1, borderColor: C.brandLight },
  from: { fontSize: F.small, color: C.brand, fontWeight: "600", marginTop: 4 },
});
