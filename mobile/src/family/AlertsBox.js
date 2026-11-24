// Urgent things at the top of the family home screen: someone asked for help, or missed a medicine.
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { BigButton, Row } from "../components/Big";
import { call, timeOf } from "./common";
import { C, F, card } from "../theme";

export default function AlertsBox({ alerts, missed, onHandled, onMissedOk }) {
  return (
    <View>
      {alerts.map((a) => (
        <View key={"e" + a.id} style={[card, s.emer]} accessibilityRole="alert">
          <View style={s.top}>
            <Ionicons name="alert-circle" size={26} color={C.danger} />
            <Text style={s.emerTitle}>{a.elder_name} needs help</Text>
          </View>
          <Text style={s.text}>
            {a.source === "button" ? "Pressed the Help button" : `Said: “${a.message || ""}”`} at {timeOf(a.raised_at)}.
          </Text>
          <View style={s.row}>
            {a.elder_phone && <BigButton title={`Call ${a.elder_name}`} icon="call" kind="danger" onPress={() => call(a.elder_phone)} style={{ flex: 1 }} />}
            <BigButton title="Call 108" icon="medical-outline" kind="dangerSoft" onPress={() => call("108")} style={{ flex: 1 }} />
          </View>
          {a.contacts.filter((p) => p.phone).length > 0 && (
            <View style={s.list}>
              {a.contacts.filter((p) => p.phone).map((p, i, all) => (
                <Row key={p.id} icon="person-outline" title={`Call ${p.name}`} value={p.relation_to_user || ""}
                     onPress={() => call(p.phone)} last={i === all.length - 1} />
              ))}
            </View>
          )}
          {a.information.length > 0 && <Text style={s.info}>{a.information.join(" · ")}</Text>}
          <BigButton small title="I've handled it" icon="checkmark" kind="light" onPress={() => onHandled(a)} style={{ marginTop: 10 }} />
        </View>
      ))}

      {missed.length > 0 && (
        <View style={[card, s.missed]}>
          <View style={s.top}>
            <Ionicons name="medkit-outline" size={22} color={C.warn} />
            <Text style={s.missedTitle}>Missed medicine{missed.length > 1 ? "s" : ""}</Text>
          </View>
          {missed.map((m, i) => (
            <View key={"m" + m.id} style={[s.missRow, i > 0 && { borderTopWidth: 1, borderColor: "#EADFC8" }]}>
              <View style={{ flex: 1 }}>
                <Text style={s.missName}>{m.elder_name}: {m.title}</Text>
                <Text style={s.muted}>Due {timeOf(m.when)}, not marked as taken{m.notes ? ` · ${m.notes}` : ""}</Text>
              </View>
              <BigButton small title="OK" kind="light" onPress={() => onMissedOk(m)} />
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  emer: { backgroundColor: C.dangerSoft, borderColor: C.danger, borderWidth: 1.5 },
  top: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 },
  emerTitle: { fontSize: F.big, fontWeight: "700", color: C.danger },
  text: { fontSize: F.body - 1, color: C.ink, lineHeight: 26 },
  row: { flexDirection: "row", gap: 10, marginTop: 12 },
  list: { backgroundColor: C.card, borderRadius: 14, paddingHorizontal: 10, marginTop: 10 },
  info: { fontSize: F.small, color: C.muted, marginTop: 10 },
  missed: { backgroundColor: C.warnSoft, borderColor: "#E6D3AE" },
  missedTitle: { fontSize: F.body, fontWeight: "700", color: C.warn },
  missRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10 },
  missName: { fontSize: F.body - 1, fontWeight: "600", color: C.ink },
  muted: { fontSize: F.small - 1, color: C.muted, marginTop: 2 },
});
