// Help: one large button (tap twice, so it isn't pressed by mistake), and a short list of people to call.
import { useEffect, useRef, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, Linking, Vibration } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../api";
import { BigButton, Label, Note, Row } from "../components/Big";
import { C, F, card } from "../theme";

const call = (phone) => Linking.openURL("tel:" + String(phone || "").replace(/[^0-9+]/g, ""));

export default function HelpScreen({ alert, setAlert }) {
  const [armed, setArmed] = useState(false);
  const [contacts, setContacts] = useState([]);
  const [msg, setMsg] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    api("/people/emergency").then(setContacts).catch(() => {});
    return () => clearTimeout(timer.current);
  }, []);

  async function press() {
    if (!armed) {
      setArmed(true); Vibration.vibrate(60);
      timer.current = setTimeout(() => setArmed(false), 5000);
      return;
    }
    clearTimeout(timer.current); setArmed(false); setMsg(null);
    try {
      const a = await api("/emergency/sos", { method: "POST" });
      Vibration.vibrate([0, 200, 100, 200]);
      setAlert(a);
    } catch (e) { setMsg({ tone: "danger", text: "Couldn't send the alert: " + e.message + " Please call 108 or a family member." }); }
  }

  async function safe() {
    try {
      await api(`/emergency/${alert.id}/resolve`, { method: "POST" });
      setAlert(null); setMsg({ tone: "good", text: "Glad you're safe. I've told your family." });
    } catch (e) { setMsg({ tone: "danger", text: e.message }); }
  }

  const people = (alert ? alert.contacts : contacts).filter((p) => p.phone);
  return (
    <ScrollView contentContainerStyle={{ padding: 16 }}>
      {alert ? (
        <View style={[card, s.alert]}>
          <View style={s.alertTop}>
            <Ionicons name="checkmark-circle" size={28} color={C.danger} />
            <Text style={s.alertTitle}>Help is on the way</Text>
          </View>
          <Text style={s.alertText}>
            {alert.notified.length
              ? `${alert.notified.join(", ")} ${alert.notified.length > 1 ? "have" : "has"} been told (at ${alert.raised_at.split(", ").pop()}). Stay where you are if you can.`
              : "No family member or doctor is connected yet, so nobody got the alert. Please call someone below."}
          </Text>
          <BigButton title="I'm safe now" kind="light" onPress={safe} />
        </View>
      ) : (
        <View style={s.center}>
          <Pressable accessibilityRole="button" accessibilityLabel="Help. Tap twice to alert your family."
                     onPress={press} style={({ pressed }) => [s.sos, armed && s.armed, pressed && { transform: [{ scale: 0.98 }] }]}>
            <Ionicons name="alert-circle-outline" size={44} color="#fff" />
            <Text style={s.sosText}>{armed ? "Tap again" : "Help"}</Text>
            <Text style={s.sosSub}>{armed ? "to alert your family" : "Tap twice"}</Text>
          </Pressable>
          <Text style={s.hint}>Your family and doctor get an alert with your phone number.{"\n"}You can also type "help" in Talk.</Text>
        </View>
      )}

      {msg && <Note tone={msg.tone}>{msg.text}</Note>}

      <Label>Call someone</Label>
      <View style={[card, { paddingVertical: 4 }]}>
        <Row icon="call-outline" title="Ambulance" value="108" tone="danger" onPress={() => call("108")} last={people.length === 0} />
        {people.map((p, i) => (
          <Row key={p.id} icon="person-outline" title={p.name} value={p.relation_to_user || p.phone}
               onPress={() => call(p.phone)} last={i === people.length - 1} />
        ))}
      </View>
      {people.length === 0 && (
        <Text style={s.hintLeft}>To add someone, go to Talk and say, for example, "Rajesh is my emergency contact, 98765 43210".</Text>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  center: { alignItems: "center", paddingVertical: 18 },
  sos: { width: 210, height: 210, borderRadius: 105, backgroundColor: C.danger, alignItems: "center", justifyContent: "center",
         borderWidth: 10, borderColor: C.dangerSoft },
  armed: { backgroundColor: "#7E3A33" },
  sosText: { color: "#fff", fontSize: 32, fontWeight: "700", marginTop: 4 },
  sosSub: { color: "#F4E5E2", fontSize: F.small, marginTop: 2 },
  hint: { fontSize: F.small, color: C.muted, textAlign: "center", marginTop: 16, lineHeight: 23 },
  hintLeft: { fontSize: F.small, color: C.muted, lineHeight: 23, marginTop: -4, marginBottom: 12 },
  alert: { borderColor: C.danger, borderWidth: 1.5, backgroundColor: C.dangerSoft },
  alertTop: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 },
  alertTitle: { fontSize: F.big, fontWeight: "700", color: C.danger },
  alertText: { fontSize: F.body, color: C.ink, marginBottom: 14, lineHeight: 27 },
});
