// Today: what needs you now, today's plan, and anything family or your doctor sent that's waiting for a yes or no.
import { useCallback, useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet, RefreshControl } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../api";
import { ringAgainIn, syncAlarms } from "../notify";
import { BigButton, Label, Note } from "../components/Big";
import { C, F, card } from "../theme";

const ICON = { MEDICINE: "medkit-outline", APPOINTMENT: "calendar-outline", BIRTHDAY: "gift-outline", CALL: "call-outline", TASK: "checkbox-outline" };
const STATUS = {
  DONE: ["Done", C.good, C.goodSoft],
  MISSED: ["Missed", C.warn, C.warnSoft],
  DUE: ["Now", C.brandInk, C.brandSoft],
  SCHEDULED: ["Later", C.muted, "#EFEEEA"],
  SKIPPED: ["Cancelled", C.muted, "#EFEEEA"],
};
const timeOf = (when) => when.split(", ").pop();

export default function TodayScreen({ refreshKey }) {
  const [due, setDue] = useState([]);
  const [today, setToday] = useState([]);
  const [sugs, setSugs] = useState([]);
  const [notes, setNotes] = useState([]);
  const [msg, setMsg] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, t, s, n] = await Promise.all([
        api("/reminders/due"), api("/reminders/today"), api("/reminders/suggestions"), api("/memories/from-others"),
      ]);
      setDue(d); setToday(t); setSugs(s); setNotes(n);
    } catch (e) { setMsg({ tone: "danger", text: e.message }); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load, refreshKey]);

  async function act(fn, okText) {
    try { await fn(); setMsg(okText ? { tone: "good", text: okText } : null); }
    catch (e) { setMsg({ tone: "danger", text: e.message }); }
    await load();
    syncAlarms();
  }

  const done = (a) => act(() => api(`/reminders/alerts/${a.id}/done`, { method: "POST" }), `Done: ${a.title}.`);
  const later = (a) => act(async () => {
    try { await api(`/reminders/alerts/${a.id}/snooze`, { method: "POST", query: { minutes: 10 } }); }
    catch (e) { await ringAgainIn(10, a.title, a.notes); } // the server can't snooze it: ring from the phone instead
  }, "I'll remind you again in 10 minutes.");

  const waiting = sugs.length + notes.length;
  return (
    <ScrollView contentContainerStyle={{ padding: 16 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      {msg && <Note tone={msg.tone}>{msg.text}</Note>}

      {due.map((a) => (
        <View key={a.id} style={[card, s.now]}>
          <View style={s.nowTop}>
            <Ionicons name={ICON[a.kind] || "alarm-outline"} size={26} color={C.brandInk} />
            <Text style={s.nowLabel}>{a.is_main ? "It's time" : "Tomorrow"}</Text>
          </View>
          <Text style={s.nowTitle}>{a.title}</Text>
          <Text style={s.muted}>{a.is_main ? timeOf(a.when) : a.when}{a.notes ? " · " + a.notes : ""}</Text>
          <View style={s.row}>
            <BigButton title={a.kind === "MEDICINE" ? "I took it" : "Done"} icon="checkmark" onPress={() => done(a)} style={{ flex: 1 }} />
            <BigButton title="Later" kind="light" onPress={() => later(a)} style={{ flex: 1 }} />
          </View>
        </View>
      ))}

      <Label>Today's plan</Label>
      <View style={card}>
        {today.length === 0 && (
          <Text style={s.empty}>Nothing planned today. To add something, go to Talk and say, for example, "Remind me to take my medicine every day at 9 pm".</Text>
        )}
        {today.map((a, i) => {
          const [label, color, bg] = STATUS[a.status] || [a.status, C.muted, "#EFEEEA"];
          const canDo = ["SCHEDULED", "MISSED", "DUE"].includes(a.status);
          return (
            <View key={a.id} style={[s.item, i > 0 && s.itemLine]}>
              <Text style={s.time}>{timeOf(a.when)}</Text>
              <View style={{ flex: 1 }}>
                <Text style={s.itemTitle}>{a.title}</Text>
                {!!a.notes && <Text style={s.muted}>{a.notes}</Text>}
                <View style={[s.pill, { backgroundColor: bg }]}><Text style={[s.pillText, { color }]}>{label}</Text></View>
              </View>
              {canDo && <BigButton small kind="light" title={a.status === "MISSED" ? "Took it late" : "Done"} onPress={() => done(a)} />}
            </View>
          );
        })}
      </View>

      {waiting > 0 && (
        <>
          <Label>Waiting for your answer</Label>
          <View style={card}>
            {sugs.map((r, i) => (
              <View key={"s" + r.id} style={[s.ask, i > 0 && s.itemLine]}>
                <Text style={s.from}>{r.suggested_by || "Your family"} suggests a reminder</Text>
                <Text style={s.itemTitle}>{r.title}</Text>
                <Text style={s.muted}>{r.due_local}{r.repeat !== "NONE" ? ` · ${r.repeat.toLowerCase()}` : ""}{r.notes ? " · " + r.notes : ""}</Text>
                <View style={s.row}>
                  <BigButton small title="Accept" icon="checkmark" style={{ flex: 1 }}
                             onPress={() => act(() => api(`/reminders/${r.id}/accept`, { method: "POST" }), "Added. I'll remind you.")} />
                  <BigButton small kind="light" title="No, thanks" style={{ flex: 1 }}
                             onPress={() => act(() => api(`/reminders/${r.id}/decline`, { method: "POST" }))} />
                </View>
              </View>
            ))}
            {notes.map((n, i) => (
              <View key={"n" + n.id} style={[s.ask, (i > 0 || sugs.length > 0) && s.itemLine]}>
                <Text style={s.from}>{n.from_name} sent you a note</Text>
                <Text style={s.itemTitle}>{n.text}</Text>
                <View style={s.row}>
                  <BigButton small title="Keep it" icon="checkmark" style={{ flex: 1 }}
                             onPress={() => act(() => api(`/memories/${n.id}/approve`, { method: "POST" }), "Saved to your memory.")} />
                  <BigButton small kind="light" title="No, thanks" style={{ flex: 1 }}
                             onPress={() => act(() => api(`/memories/${n.id}/reject`, { method: "POST" }))} />
                </View>
              </View>
            ))}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  now: { borderColor: C.brand, borderWidth: 1.5, backgroundColor: C.brandSoft },

  nowTop: { flexDirection: "row", alignItems: "center", gap: 8 },
  nowLabel: { fontSize: F.small, fontWeight: "700", color: C.brandInk, textTransform: "uppercase", letterSpacing: 0.6 },
  nowTitle: { fontSize: F.huge, fontWeight: "700", color: C.ink, marginTop: 6 },
  row: { flexDirection: "row", gap: 10, marginTop: 12 },
  empty: { fontSize: F.small + 1, color: C.muted, lineHeight: 24 },
  item: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12 },
  itemLine: { borderTopWidth: 1, borderColor: C.line },
  time: { width: 76, fontSize: F.small, fontWeight: "600", color: C.brandInk },
  itemTitle: { fontSize: F.body, fontWeight: "600", color: C.ink },
  muted: { fontSize: F.small, color: C.muted, marginTop: 2 },
  pill: { alignSelf: "flex-start", borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2, marginTop: 5 },
  pillText: { fontSize: 13, fontWeight: "700" },
  ask: { paddingVertical: 12 },
  from: { fontSize: F.small - 1, color: C.brandInk, fontWeight: "600", marginBottom: 4 },
});
