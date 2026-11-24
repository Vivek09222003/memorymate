// The urgent things at the top of the family home screen:
// red emergency alerts (call buttons, mark handled) and orange missed-medicine alerts.
import { View, Text, StyleSheet } from "react-native";
import { BigButton } from "../components/Big";
import { call, timeOf } from "./common";
import { C, F } from "../theme";

export default function AlertsBox({ alerts, missed, onHandled, onMissedOk }) {
  return (
    <View>
      {alerts.map((a) => (
        <View key={"e" + a.id} style={s.emer} accessibilityRole="alert">
          <Text style={s.emerTitle}>🚨 {a.elder_name} needs help</Text>
          <Text style={s.text}>
            {a.source === "button" ? "Pressed the Help button" : `Said: “${a.message || ""}”`} at {timeOf(a.raised_at)}.
          </Text>
          {a.elder_phone && (
            <BigButton title={`📞 Call ${a.elder_name}`} kind="red" onPress={() => call(a.elder_phone)} style={s.gap} />
          )}
          <BigButton title="📞 Call 108 (Ambulance)" kind="redLight" onPress={() => call("108")} style={s.gap} />
          {a.contacts.filter((p) => p.phone).map((p) => (
            <BigButton key={p.id} small kind="redLight" title={`Call ${p.name}${p.relation_to_user ? " (" + p.relation_to_user + ")" : ""}`}
                       onPress={() => call(p.phone)} style={s.gap} />
          ))}
          {a.information.length > 0 && <Text style={s.info}>{a.information.join(" · ")}</Text>}
          <BigButton small title="Mark as handled" kind="light" onPress={() => onHandled(a)} style={{ marginTop: 6 }} />
        </View>
      ))}

      {missed.length > 0 && (
        <View style={s.missed}>
          <Text style={s.missedTitle}>⚠️ Missed medicine{missed.length > 1 ? "s" : ""}</Text>
          {missed.map((m) => (
            <View key={"m" + m.id} style={s.row}>
              <Text style={[s.text, { flex: 1 }]}>
                <Text style={{ fontWeight: "800" }}>{m.elder_name}</Text> didn't confirm <Text style={{ fontWeight: "800" }}>{m.title}</Text> (due {timeOf(m.when)}){m.notes ? " · " + m.notes : ""}
              </Text>
              <BigButton small title="OK, I'll check" kind="light" onPress={() => onMissedOk(m)} />
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  emer: { backgroundColor: "#fff0f2", borderWidth: 3, borderColor: C.red, borderRadius: 18, padding: 14, marginBottom: 12 },
  emerTitle: { fontSize: F.big, fontWeight: "800", color: "#a00d26", marginBottom: 6 },
  text: { fontSize: F.body - 2, color: C.ink, lineHeight: 26 },
  info: { fontSize: F.small, color: C.muted, marginTop: 6 },
  gap: { marginTop: 8 },
  missed: { backgroundColor: C.orangeLight, borderWidth: 3, borderColor: "#d9861a", borderRadius: 18, padding: 14, marginBottom: 12 },
  missedTitle: { fontSize: F.body, fontWeight: "800", color: C.orange, marginBottom: 6 },
  row: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 6 },
});
