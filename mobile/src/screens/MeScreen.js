// Me: a short list of options. Tap one to open it; only one is open at a time, so the screen stays clean.
import { useState } from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { api, getBaseUrl } from "../api";
import { setupNotifications, syncAlarms } from "../notify";
import { BigButton, Field, Label, Note, Row, Segmented } from "../components/Big";
import DeleteAccount from "../components/DeleteAccount";
import { C, F, card } from "../theme";

const LANGS = [["en", "English"], ["hi", "हिन्दी"], ["hinglish", "Hinglish"]];
const LANG_NAME = { en: "English", hi: "हिन्दी", hinglish: "Hinglish" };

export default function MeScreen({ me, setMe, onLogout }) {
  const [open, setOpen] = useState(null);       // "lang" | "phone" | "alarms" | "delete" | null
  const [phone, setPhone] = useState(me.phone || "");
  const [msg, setMsg] = useState(null);

  const toggle = (k) => { setOpen(open === k ? null : k); setMsg(null); };

  async function save(changes, ok) {
    try { setMe(await api("/auth/me", { method: "PATCH", body: changes })); setMsg({ tone: "good", text: ok }); }
    catch (e) { setMsg({ tone: "danger", text: e.message }); }
  }

  async function alarms() {
    const allowed = await setupNotifications();
    if (!allowed) return setMsg({ tone: "warn", text: "Notifications are turned off. Please allow them in your phone's Settings, under this app." });
    const n = await syncAlarms();
    setMsg(n === null
      ? { tone: "warn", text: "Couldn't reach MemoryMate, so your existing alarms are kept." }
      : { tone: "good", text: `${n} reminder${n === 1 ? "" : "s"} set on this phone for the next 2 days.` });
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 16 }}>
      <View style={[card, s.profile]}>
        <View style={s.avatar}><Text style={s.avatarText}>{me.name.trim()[0]?.toUpperCase()}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={s.name}>{me.name}</Text>
          <Text style={s.muted}>{me.email}</Text>
        </View>
      </View>

      <Label>Settings</Label>
      <View style={[card, { paddingVertical: 4 }]}>
        <Row icon="language-outline" title="Language" value={LANG_NAME[me.preferred_language]} onPress={() => toggle("lang")} />
        {open === "lang" && (
          <View style={s.open}>
            <Text style={s.muted}>MemoryMate will talk to you in:</Text>
            <Segmented options={LANGS} value={me.preferred_language} style={{ marginTop: 8 }}
                       onChange={(code) => save({ preferred_language: code }, "Language changed.")} />
          </View>
        )}
        <Row icon="call-outline" title="My phone number" value={me.phone || "Not added"} onPress={() => toggle("phone")} />
        {open === "phone" && (
          <View style={s.open}>
            <Text style={s.muted}>Your family can call you from an emergency alert.</Text>
            <Field value={phone} onChangeText={setPhone} placeholder="98123 45678" keyboardType="phone-pad" style={{ marginTop: 8 }} />
            <BigButton small title="Save number" onPress={() => save({ phone: phone.trim() || null }, "Phone number saved.")} />
          </View>
        )}
        <Row icon="alarm-outline" title="Reminder alarms" onPress={() => { toggle("alarms"); if (open !== "alarms") alarms(); }} last />
        {open === "alarms" && (
          <View style={[s.open, { borderTopWidth: 0 }]}>
            <Text style={s.muted}>Your reminders ring from this phone, even when the app is closed.</Text>
          </View>
        )}
      </View>

      {msg && <Note tone={msg.tone}>{msg.text}</Note>}

      <View style={[card, { paddingVertical: 4 }]}>
        <Row icon="log-out-outline" title="Log out" onPress={onLogout} />
        <Row icon="trash-outline" title="Delete my account" tone="danger" onPress={() => toggle("delete")} last={open !== "delete"} />
        {open === "delete" && <DeleteAccount isElder onDeleted={onLogout} />}
      </View>
      <Text style={s.server}>Connected to {getBaseUrl().replace(/^https?:\/\//, "")}</Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  profile: { flexDirection: "row", alignItems: "center", gap: 14 },
  avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: C.brand, alignItems: "center", justifyContent: "center" },
  avatarText: { fontSize: 22, fontWeight: "700", color: C.onBrand },
  name: { fontSize: F.big, fontWeight: "700", color: C.ink },
  muted: { fontSize: F.small, color: C.muted },
  open: { paddingBottom: 14, paddingHorizontal: 4, borderBottomWidth: 1, borderColor: C.line },
  server: { fontSize: 13, color: C.faint, textAlign: "center", marginTop: 4 },
});
