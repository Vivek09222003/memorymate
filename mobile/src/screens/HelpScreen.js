// Emergency: one big red button (tap twice, so it isn't pressed by mistake), call buttons, and 108.
import { useEffect, useRef, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, Linking, Vibration } from "react-native";
import { api } from "../api";
import { BigButton, Heading } from "../components/Big";
import { C, F, card } from "../theme";

const call = (phone) => Linking.openURL("tel:" + String(phone || "").replace(/[^0-9+]/g, ""));

export default function HelpScreen({ alert, setAlert }) {
  const [armed, setArmed] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [msg, setMsg] = useState("");
  const timer = useRef(null);

  useEffect(() => {
    api("/people/emergency").then(setContacts).catch(() => {});
    return () => clearTimeout(timer.current);
  }, []);

  async function press() {
    if (!armed) {
      setArmed(true); Vibration.vibrate(80);
      timer.current = setTimeout(() => setArmed(false), 5000);
      return;
    }
    clearTimeout(timer.current); setArmed(false); setMsg("");
    try {
      const a = await api("/emergency/sos", { method: "POST" });
      Vibration.vibrate([0, 200, 100, 200]);
      setAlert(a);
    } catch (e) { setMsg("Couldn't send the alert: " + e.message + " Please call 108 or a family member."); }
  }

  async function safe() {
    try {
      await api(`/emergency/${alert.id}/resolve`, { method: "POST" });
      setAlert(null); setMsg("Glad you're safe. I've told your family.");
    } catch (e) { setMsg(e.message); }
  }

  const people = alert ? alert.contacts : contacts;
  return (
    <ScrollView contentContainerStyle={{ padding: 12 }}>
      {alert ? (
        <View style={[card, s.alert]}>
          <Text style={s.alertTitle}>🚨 Help is on the way</Text>
          <Text style={s.alertText}>
            {alert.notified.length
              ? `Alert sent to ${alert.notified.join(", ")} at ${alert.raised_at.split(", ").pop()}. Stay where you are if you can.`
              : "No family member or doctor is connected yet, so nobody got the alert. Please call someone now."}
          </Text>
          <BigButton title="I'm safe now" kind="light" onPress={safe} />
        </View>
      ) : (
        <View style={s.center}>
          <Pressable accessibilityRole="button" accessibilityLabel="Help. Tap twice to alert your family."
                     onPress={press} style={({ pressed }) => [s.sos, armed && s.armed, pressed && { transform: [{ scale: 0.97 }] }]}>
            <Text style={s.sosText}>{armed ? "TAP AGAIN" : "HELP"}</Text>
            <Text style={s.sosSub}>{armed ? "to alert your family" : "tap twice"}</Text>
          </Pressable>
          <Text style={s.hint}>Your family and doctor get an alert with your phone number. You can also just type "help" or "bachao" in the chat.</Text>
        </View>
      )}

      {!!msg && <Text style={s.msg}>{msg}</Text>}

      <View style={card}>
        <Heading>Call now</Heading>
        <BigButton title="📞 Call 108 (Ambulance)" kind="red" onPress={() => call("108")} style={{ marginBottom: 10 }} />
        {people.filter((p) => p.phone).map((p) => (
          <BigButton key={p.id} title={`📞 Call ${p.name}${p.relation_to_user ? " (" + p.relation_to_user + ")" : ""}`}
                     kind="redLight" onPress={() => call(p.phone)} style={{ marginBottom: 10 }} />
        ))}
        {people.filter((p) => p.phone).length === 0 && (
          <Text style={s.muted}>No emergency contacts saved yet. Tell me in the chat, like "Rajesh is my emergency contact, 98765 43210".</Text>
        )}
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  center: { alignItems: "center", paddingVertical: 16 },
  sos: { width: 230, height: 230, borderRadius: 115, backgroundColor: C.red, alignItems: "center", justifyContent: "center", elevation: 6, borderWidth: 8, borderColor: C.redLight },
  armed: { backgroundColor: C.redDark, borderColor: "#ffb3c0" },
  sosText: { color: "#fff", fontSize: 44, fontWeight: "900", letterSpacing: 2 },
  sosSub: { color: "#ffe1e6", fontSize: F.body, marginTop: 4 },
  hint: { fontSize: F.small, color: C.muted, textAlign: "center", marginTop: 16, paddingHorizontal: 10 },
  alert: { backgroundColor: "#fff0f2", borderWidth: 3, borderColor: C.red },
  alertTitle: { fontSize: F.huge, fontWeight: "800", color: "#a00d26", marginBottom: 8 },
  alertText: { fontSize: F.body, color: C.ink, marginBottom: 12, lineHeight: 28 },
  msg: { fontSize: F.body, color: C.ink, backgroundColor: C.brandLight, padding: 12, borderRadius: 12, marginBottom: 12 },
  muted: { fontSize: F.small, color: C.muted },
});
