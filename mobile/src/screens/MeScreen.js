// Me: language, phone number (so family can call you), alarm status, and log out.
import { useState } from "react";
import { View, Text, TextInput, ScrollView, StyleSheet } from "react-native";
import { api, getBaseUrl } from "../api";
import { setupNotifications, syncAlarms } from "../notify";
import { BigButton, Heading } from "../components/Big";
import { C, F, card } from "../theme";

const LANGS = [["en", "English"], ["hi", "हिन्दी"], ["hinglish", "Hinglish"]];

export default function MeScreen({ me, setMe, onLogout }) {
  const [phone, setPhone] = useState(me.phone || "");
  const [msg, setMsg] = useState("");

  async function save(changes, ok) {
    try { setMe(await api("/auth/me", { method: "PATCH", body: changes })); setMsg(ok); }
    catch (e) { setMsg(e.message); }
  }

  async function alarms() {
    const allowed = await setupNotifications();
    if (!allowed) return setMsg("Notifications are turned off. Please allow them in the phone's Settings → Apps → Expo Go → Notifications.");
    const n = await syncAlarms();
    setMsg(n === null ? "Couldn't reach the server, so your old alarms are kept." : `✅ ${n} alarm${n === 1 ? "" : "s"} set on this phone for the next 2 days.`);
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 12 }}>
      <View style={card}>
        <Text style={s.name}>{me.name}</Text>
        <Text style={s.muted}>{me.email}</Text>
      </View>

      <View style={card}>
        <Heading>Language</Heading>
        <Text style={s.muted}>MemoryMate replies in this language.</Text>
        <View style={s.row}>
          {LANGS.map(([code, label]) => (
            <BigButton key={code} small title={label} kind={me.preferred_language === code ? "primary" : "light"} style={{ flex: 1 }}
                       onPress={() => save({ preferred_language: code }, "Language changed.")} />
          ))}
        </View>
      </View>

      <View style={card}>
        <Heading>My phone number</Heading>
        <Text style={s.muted}>So your family can call you from an emergency alert.</Text>
        <TextInput style={s.input} value={phone} onChangeText={setPhone} placeholder="98123 45678" keyboardType="phone-pad" />
        <BigButton small title="Save number" onPress={() => save({ phone: phone.trim() || null }, "Phone number saved.")} />
      </View>

      <View style={card}>
        <Heading>Reminder alarms</Heading>
        <Text style={s.muted}>Your reminders ring from this phone, even when the app is closed.</Text>
        <BigButton small title="Check my alarms" kind="light" onPress={alarms} />
      </View>

      {!!msg && <Text style={s.msg}>{msg}</Text>}

      <View style={card}>
        <Text style={s.muted}>Connected to {getBaseUrl()}</Text>
        <BigButton small title="Log out" kind="redLight" onPress={onLogout} style={{ marginTop: 10 }} />
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  name: { fontSize: F.huge, fontWeight: "800", color: C.ink },
  muted: { fontSize: F.small, color: C.muted, marginBottom: 8 },
  row: { flexDirection: "row", gap: 8 },
  input: { fontSize: F.body, borderWidth: 2, borderColor: C.line, borderRadius: 14, padding: 14, marginBottom: 10, color: C.ink, backgroundColor: "#fff" },
  msg: { fontSize: F.body, color: C.ink, backgroundColor: C.brandLight, padding: 12, borderRadius: 12, marginBottom: 12 },
});
