// One person you look after. Instead of one long page, pick what to see:
//   Today (medicines, appointments) · Health (notes, shared memories) · Contacts · Add (reminder or note)
// Anything you add waits for their "yes" before it counts.
import { useCallback, useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, RefreshControl } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../api";
import { BigButton, Field, Label, Note, Option, Row, Segmented } from "../components/Big";
import { call, dayString, isDoctorLink, roleFor, timeOf } from "./common";
import { C, F, card } from "../theme";

const STATUS = {
  DONE: ["Taken", C.good, C.goodSoft], MISSED: ["Missed", C.warn, C.warnSoft], DUE: ["Now", C.brandInk, C.brandSoft],
  SCHEDULED: ["Later", C.muted, "#EFEBE1"], SKIPPED: ["Cancelled", C.muted, "#EFEBE1"],
};
const KINDS = [["MEDICINE", "Medicine"], ["APPOINTMENT", "Visit"], ["CALL", "Call"], ["TASK", "Task"]];
const REPEATS = [["NONE", "Once"], ["DAILY", "Daily"], ["WEEKLY", "Weekly"]];

function Pill({ status }) {
  const [label, color, bg] = STATUS[status] || [status, C.muted, "#EFEBE1"];
  return <View style={[s.pill, { backgroundColor: bg }]}><Text style={[s.pillText, { color }]}>{label}</Text></View>;
}

export default function ElderDetail({ row, me, onBack, refreshKey }) {
  const [view, setView] = useState("today");
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  // add: reminder or note
  const [what, setWhat] = useState("reminder");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("MEDICINE");
  const [day, setDay] = useState("today");
  const [date, setDate] = useState(dayString(2));
  const [time, setTime] = useState("18:00");
  const [repeat, setRepeat] = useState("NONE");
  const [notes, setNotes] = useState("");
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState(null);

  const first = row.elder_name.split(" ")[0];
  const doctor = me.role === "DOCTOR" || isDoctorLink(row.relation);

  const load = useCallback(async () => {
    setLoading(true);
    try { setD(await api(`/family/elders/${row.elder_id}/dashboard`)); setErr(""); }
    catch (e) { setErr(e.message); }
    setLoading(false);
  }, [row.elder_id]);
  useEffect(() => { load(); }, [load, refreshKey]);

  async function addReminder() {
    setMsg(null);
    const when = day === "today" ? dayString(0) : day === "tomorrow" ? dayString(1) : date;
    if (!title.trim()) return setMsg({ tone: "warn", text: "Please write what to remind, for example \"Metformin 500 mg\"." });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(when)) return setMsg({ tone: "warn", text: "Please write the date like 2026-11-30." });
    if (!/^\d{1,2}:\d{2}$/.test(time)) return setMsg({ tone: "warn", text: "Please write the time like 18:00 (24-hour clock)." });
    try {
      await api(`/family/elders/${row.elder_id}/reminders`, { method: "POST",
        body: { title: title.trim(), kind, date: when, time: time.padStart(5, "0"), repeat, notes: notes.trim() || null } });
      setMsg({ tone: "good", text: `Sent to ${first}. It starts once ${first} accepts it.` });
      setTitle(""); setNotes("");
    } catch (e) { setMsg({ tone: "danger", text: e.message }); }
  }

  async function sendNote() {
    setMsg(null);
    if (note.trim().length < 3) return setMsg({ tone: "warn", text: "Please write the note first." });
    try {
      await api(`/family/elders/${row.elder_id}/notes`, { method: "POST", body: { text: note.trim() } });
      setMsg({ tone: "good", text: `Sent to ${first}. It's saved once ${first} accepts it.` }); setNote("");
    } catch (e) { setMsg({ tone: "danger", text: e.message }); }
  }

  const empty = (text) => <Text style={s.empty}>{text}</Text>;
  const hidden = (section) => d?.hidden_sections?.includes(section);

  return (
    <ScrollView contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled"
                refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      <Pressable onPress={onBack} style={s.back} accessibilityRole="button">
        <Ionicons name="chevron-back" size={20} color={C.brandInk} />
        <Text style={s.backText}>Everyone</Text>
      </Pressable>

      <View style={[card, s.person]}>
        <View style={s.avatar}><Text style={s.avatarText}>{row.elder_name.trim()[0]?.toUpperCase()}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={s.name}>{row.elder_name}</Text>
          <Text style={s.muted}>{roleFor(row.relation)}{d ? ` · updated ${timeOf(d.as_of)}` : ""}</Text>
        </View>
        {d?.elder_phone && (
          <Pressable onPress={() => call(d.elder_phone)} style={s.callBtn} accessibilityLabel={`Call ${first}`}>
            <Ionicons name="call" size={22} color={C.onBrand} />
          </Pressable>
        )}
      </View>

      {!!err && <Note tone="danger">{err}</Note>}

      <Segmented value={view} onChange={(v) => { setView(v); setMsg(null); }}
                 options={[["today", "Today"], ["health", "Health"], ["contacts", "Contacts"], ["add", "Add"]]} />

      {view === "today" && d && (
        <>
          <Label>Medicines today</Label>
          <View style={card}>
            {hidden("medicines") ? empty(`${first} hasn't shared medicines with you.`)
              : d.medicines_today?.length ? d.medicines_today.map((m, i) => (
                <View key={m.id} style={[s.item, i > 0 && s.line]}>
                  <Text style={s.time}>{timeOf(m.when)}</Text>
                  <Text style={s.itemTitle}>{m.title}</Text>
                  <Pill status={m.status} />
                </View>
              )) : empty("No medicines planned today.")}
          </View>
          <Label>Coming up</Label>
          <View style={card}>
            {hidden("appointments") ? empty(`${first} hasn't shared appointments with you.`)
              : d.upcoming_appointments?.length ? d.upcoming_appointments.map((a, i) => (
                <View key={a.id} style={[s.item, i > 0 && s.line]}>
                  <Ionicons name="calendar-outline" size={20} color={C.brandInk} />
                  <View style={{ flex: 1 }}>
                    <Text style={s.itemTitle}>{a.title}</Text>
                    <Text style={s.muted}>{a.when}</Text>
                  </View>
                </View>
              )) : empty("Nothing in the next 30 days.")}
          </View>
        </>
      )}

      {view === "health" && d && (
        <>
          <Label>Health notes</Label>
          <View style={card}>
            {d.health_notes?.length ? d.health_notes.map((m, i) => (
              <Text key={i} style={[s.fact, i > 0 && s.line]}>{m.fact}</Text>
            )) : empty("No health notes yet. You can send one from Add.")}
          </View>
          <Label>Shared with you</Label>
          <View style={card}>
            {hidden("shared memories") ? empty(`${first} hasn't shared memories with you.`)
              : d.shared_memories?.length ? d.shared_memories.map((m, i) => (
                <View key={i} style={i > 0 && s.line}>
                  <Text style={s.fact}>{m.fact}</Text>
                  <Text style={[s.muted, { marginBottom: 8 }]}>{m.told_on}</Text>
                </View>
              )) : empty("Nothing shared yet.")}
          </View>
        </>
      )}

      {view === "contacts" && d && (
        <>
          <Label>Emergency contacts</Label>
          <View style={[card, { paddingVertical: 4 }]}>
            {hidden("emergency") ? empty(`${first} hasn't shared emergency details with you.`) : (
              <>
                <Row icon="call-outline" title="Ambulance" value="108" tone="danger" onPress={() => call("108")}
                     last={!d.emergency?.contacts?.length} />
                {(d.emergency?.contacts || []).map((p, i, all) => (
                  <Row key={p.id} icon="person-outline" title={p.name} value={p.relation_to_user || p.phone || "no number"}
                       onPress={p.phone ? () => call(p.phone) : undefined} last={i === all.length - 1} />
                ))}
              </>
            )}
          </View>
          {(d.emergency?.information || []).length > 0 && (
            <>
              <Label>Important to know</Label>
              <View style={card}>{d.emergency.information.map((t, i) => <Text key={i} style={[s.fact, i > 0 && s.line]}>{t}</Text>)}</View>
            </>
          )}
        </>
      )}

      {view === "add" && (
        <>
          <Label>What would you like to add for {first}?</Label>
          <Option icon="alarm-outline" title="A reminder" hint={`A medicine, appointment or task. ${first} gets asked first.`}
                  selected={what === "reminder"} onPress={() => { setWhat("reminder"); setMsg(null); }} />
          <Option icon="document-text-outline" title={doctor ? "A health note" : "A note"} hint={`Advice or an instruction for ${first} to keep.`}
                  selected={what === "note"} onPress={() => { setWhat("note"); setMsg(null); }} />

          <View style={[card, { marginTop: 4 }]}>
            {what === "reminder" ? (
              <>
                <Field label="What" value={title} onChangeText={setTitle} placeholder="e.g. Metformin 500 mg" />
                <Text style={s.fieldLabel}>Type</Text>
                <Segmented options={KINDS} value={kind} onChange={setKind} />
                <Text style={s.fieldLabel}>Day</Text>
                <Segmented options={[["today", "Today"], ["tomorrow", "Tomorrow"], ["other", "Other"]]} value={day} onChange={setDay} />
                {day === "other" && <Field value={date} onChangeText={setDate} placeholder="2026-11-30" />}
                <Field label="Time (24-hour)" value={time} onChangeText={setTime} placeholder="18:00" keyboardType="numbers-and-punctuation" />
                <Text style={s.fieldLabel}>Repeat</Text>
                <Segmented options={REPEATS} value={repeat} onChange={setRepeat} />
                <Field label="Notes (optional)" value={notes} onChangeText={setNotes} placeholder="e.g. after dinner" />
                <BigButton title={`Send to ${first}`} icon="paper-plane-outline" onPress={addReminder} />
              </>
            ) : (
              <>
                <Field label="Your note" value={note} onChangeText={setNote} multiline placeholder="e.g. Walk 20 minutes every morning"
                       style={{ minHeight: 100, textAlignVertical: "top" }} />
                <BigButton title={`Send to ${first}`} icon="paper-plane-outline" onPress={sendNote} />
              </>
            )}
          </View>
          {msg && <Note tone={msg.tone}>{msg.text}</Note>}
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  back: { flexDirection: "row", alignItems: "center", paddingVertical: 6, marginBottom: 6, alignSelf: "flex-start" },
  backText: { fontSize: F.small + 1, color: C.brandInk, fontWeight: "600" },
  person: { flexDirection: "row", alignItems: "center", gap: 14 },
  avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: C.brandSoft, alignItems: "center", justifyContent: "center" },
  avatarText: { fontSize: 22, fontWeight: "700", color: C.brandInk },
  name: { fontSize: F.big, fontWeight: "700", color: C.ink },
  muted: { fontSize: F.small - 1, color: C.muted, marginTop: 2 },
  callBtn: { width: 48, height: 48, borderRadius: 24, backgroundColor: C.brand, alignItems: "center", justifyContent: "center" },
  empty: { fontSize: F.small, color: C.muted, paddingVertical: 6, lineHeight: 22 },
  item: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 11 },
  line: { borderTopWidth: 1, borderColor: C.line },
  time: { width: 74, fontSize: F.small, fontWeight: "600", color: C.brandInk },
  itemTitle: { flex: 1, fontSize: F.body - 1, fontWeight: "600", color: C.ink },
  fact: { fontSize: F.body - 1, color: C.ink, paddingVertical: 8, lineHeight: 25 },
  pill: { borderRadius: 10, paddingHorizontal: 9, paddingVertical: 3 },
  pillText: { fontSize: 13, fontWeight: "700" },
  fieldLabel: { fontSize: F.small, color: C.muted, marginBottom: 6, fontWeight: "600" },
});
