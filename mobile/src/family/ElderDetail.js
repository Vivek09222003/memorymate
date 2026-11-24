// One elder or patient: today's dashboard (only what they share), and forms to suggest a reminder
// or send a health note. Both wait for the elder's yes before anything happens.
import { useCallback, useEffect, useState } from "react";
import { View, Text, TextInput, ScrollView, StyleSheet, Pressable, RefreshControl } from "react-native";
import { api } from "../api";
import { BigButton, Heading } from "../components/Big";
import { call, dayString, isDoctorLink, roleFor, timeOf } from "./common";
import { C, F, card } from "../theme";

const WORD = { DONE: "✅ taken / done", MISSED: "❌ missed", DUE: "⏰ ringing now", SCHEDULED: "later today", SKIPPED: "cancelled" };
const KINDS = [["MEDICINE", "💊 Medicine"], ["APPOINTMENT", "🏥 Appointment"], ["CALL", "📞 Call"], ["TASK", "✅ Task"], ["BIRTHDAY", "🎂 Birthday"]];
const REPEATS = [["NONE", "Once"], ["DAILY", "Every day"], ["WEEKLY", "Every week"], ["YEARLY", "Every year"]];

function Chips({ options, value, onChange }) {
  return (
    <View style={s.chips}>
      {options.map(([v, label]) => (
        <Pressable key={v} onPress={() => onChange(v)} style={[s.chip, value === v && s.chipOn]}>
          <Text style={[s.chipText, value === v && { color: "#fff" }]}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function ElderDetail({ row, me, onBack, refreshKey }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  // suggestion form
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("MEDICINE");
  const [date, setDate] = useState(dayString(0));
  const [time, setTime] = useState("18:00");
  const [repeat, setRepeat] = useState("NONE");
  const [notes, setNotes] = useState("");
  const [sugMsg, setSugMsg] = useState("");
  // health note
  const [note, setNote] = useState("");
  const [noteMsg, setNoteMsg] = useState("");

  const doctor = me.role === "DOCTOR" || isDoctorLink(row.relation);

  const load = useCallback(async () => {
    setLoading(true);
    try { setD(await api(`/family/elders/${row.elder_id}/dashboard`)); setErr(""); }
    catch (e) { setErr(e.message); }
    setLoading(false);
  }, [row.elder_id]);
  useEffect(() => { load(); }, [load, refreshKey]);

  async function suggest() {
    setSugMsg("");
    if (!title.trim()) return setSugMsg("Please write what to remind, e.g. Metformin 500 mg.");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return setSugMsg("Date should look like 2026-11-25.");
    if (!/^\d{1,2}:\d{2}$/.test(time)) return setSugMsg("Time should look like 18:00 (24-hour).");
    try {
      await api(`/family/elders/${row.elder_id}/reminders`, { method: "POST",
        body: { title: title.trim(), kind, date, time: time.padStart(5, "0"), repeat, notes: notes.trim() || null } });
      setSugMsg(`✅ Suggested. It will ring once ${row.elder_name} accepts it.`);
      setTitle(""); setNotes("");
    } catch (e) { setSugMsg("Couldn't suggest it: " + e.message); }
  }

  async function sendNote() {
    setNoteMsg("");
    if (note.trim().length < 3) return setNoteMsg("Please write the note first.");
    try {
      await api(`/family/elders/${row.elder_id}/notes`, { method: "POST", body: { text: note.trim() } });
      setNoteMsg(`✅ Sent. It's added once ${row.elder_name} accepts it.`); setNote("");
    } catch (e) { setNoteMsg("Couldn't send it: " + e.message); }
  }

  const list = (items, render) => items.length
    ? items.map(render)
    : <Text style={s.muted}>Nothing here.</Text>;

  return (
    <ScrollView contentContainerStyle={{ padding: 12 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
                keyboardShouldPersistTaps="handled">
      <BigButton small title="← All my people" kind="light" onPress={onBack} style={{ alignSelf: "flex-start", marginBottom: 10 }} />
      {!!err && <Text style={s.err}>{err}</Text>}

      <View style={card}>
        <Text style={s.name}>{row.elder_name}</Text>
        <Text style={s.muted}>{roleFor(row.relation)}{d ? ` · as of ${timeOf(d.as_of)}` : ""}</Text>
        <Text style={[s.muted, { marginTop: 4 }]}>Only what {row.elder_name} chose to share is shown. Each view is logged for them.</Text>
        {d?.elder_phone && <BigButton title={`📞 Call ${row.elder_name}`} kind="redLight" onPress={() => call(d.elder_phone)} style={{ marginTop: 10 }} />}
      </View>

      {d?.medicines_today && (
        <View style={card}>
          <Heading>Medicines today{d.missed_medicines_today ? <Text style={{ color: C.red }}>{` · ${d.missed_medicines_today} missed`}</Text> : null}</Heading>
          {list(d.medicines_today, (m) => (
            <Text key={m.id} style={s.item}>💊 {m.title} at {timeOf(m.when)}: <Text style={{ fontWeight: "700" }}>{WORD[m.status] || m.status}</Text></Text>
          ))}
        </View>
      )}

      {d?.upcoming_appointments && (
        <View style={card}>
          <Heading>Upcoming appointments and tasks</Heading>
          {list(d.upcoming_appointments, (a) => <Text key={a.id} style={s.item}>🏥 <Text style={{ fontWeight: "700" }}>{a.when}</Text>: {a.title}</Text>)}
        </View>
      )}

      {d?.health_notes?.length > 0 && (
        <View style={card}>
          <Heading>Health notes</Heading>
          {d.health_notes.map((m, i) => <Text key={i} style={s.item}>• {m.fact}</Text>)}
        </View>
      )}

      {d?.shared_memories && (
        <View style={card}>
          <Heading>Shared memories</Heading>
          {list(d.shared_memories, (m, i) => <Text key={i} style={s.item}>• {m.fact} <Text style={s.muted}>({m.told_on})</Text></Text>)}
        </View>
      )}

      {d?.emergency && (
        <View style={card}>
          <Heading>Emergency contacts</Heading>
          {list(d.emergency.contacts, (p) => (
            <View key={p.id} style={s.contact}>
              <Text style={[s.item, { flex: 1 }]}>{p.name}{p.relation_to_user ? ` (${p.relation_to_user})` : ""}</Text>
              {p.phone ? <BigButton small title="Call" kind="redLight" onPress={() => call(p.phone)} /> : <Text style={s.muted}>no number</Text>}
            </View>
          ))}
          {d.emergency.information.map((t, i) => <Text key={i} style={s.muted}>{t}</Text>)}
        </View>
      )}

      {d?.hidden_sections?.length > 0 && (
        <Text style={[s.muted, { marginBottom: 12 }]}>Not shared with you: {d.hidden_sections.join(", ")}.</Text>
      )}

      <View style={card}>
        <Heading>Suggest a reminder</Heading>
        <Text style={s.muted}>It only starts ringing after {row.elder_name} accepts it.</Text>
        <TextInput style={s.input} value={title} onChangeText={setTitle} placeholder="What, e.g. Metformin 500 mg" />
        <Chips options={KINDS} value={kind} onChange={setKind} />
        <View style={s.chips}>
          <Pressable onPress={() => setDate(dayString(0))} style={[s.chip, date === dayString(0) && s.chipOn]}>
            <Text style={[s.chipText, date === dayString(0) && { color: "#fff" }]}>Today</Text></Pressable>
          <Pressable onPress={() => setDate(dayString(1))} style={[s.chip, date === dayString(1) && s.chipOn]}>
            <Text style={[s.chipText, date === dayString(1) && { color: "#fff" }]}>Tomorrow</Text></Pressable>
        </View>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <TextInput style={[s.input, { flex: 3 }]} value={date} onChangeText={setDate} placeholder="2026-11-25" />
          <TextInput style={[s.input, { flex: 2 }]} value={time} onChangeText={setTime} placeholder="18:00" keyboardType="numbers-and-punctuation" />
        </View>
        <Chips options={REPEATS} value={repeat} onChange={setRepeat} />
        <TextInput style={s.input} value={notes} onChangeText={setNotes} placeholder="Notes, e.g. after dinner" />
        <BigButton title="Suggest" onPress={suggest} />
        {!!sugMsg && <Text style={s.msg}>{sugMsg}</Text>}
      </View>

      <View style={card}>
        <Heading>{doctor ? "Add a health note" : "Send a health note"}</Heading>
        <Text style={s.muted}>Advice or an instruction. It's added to {row.elder_name}'s memory only if they accept it.</Text>
        <TextInput style={[s.input, { minHeight: 90, textAlignVertical: "top" }]} value={note} onChangeText={setNote} multiline
                   placeholder="e.g. Walk 20 minutes every morning; keep sugar low" />
        <BigButton title="Send note" onPress={sendNote} />
        {!!noteMsg && <Text style={s.msg}>{noteMsg}</Text>}
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  name: { fontSize: F.huge, fontWeight: "800", color: C.ink },
  muted: { fontSize: F.small, color: C.muted },
  err: { fontSize: F.small, color: C.redDark, backgroundColor: C.redLight, padding: 12, borderRadius: 12, marginBottom: 12 },
  item: { fontSize: F.body - 2, color: C.ink, paddingVertical: 4, lineHeight: 26 },
  contact: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 4 },
  input: { fontSize: F.body - 2, borderWidth: 2, borderColor: C.line, borderRadius: 14, padding: 12, marginVertical: 6, color: C.ink, backgroundColor: "#fff" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginVertical: 6 },
  chip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, backgroundColor: C.brandLight },
  chipOn: { backgroundColor: C.brand },
  chipText: { fontSize: F.small, color: C.ink, fontWeight: "600" },
  msg: { fontSize: F.small, color: C.ink, marginTop: 8 },
});
