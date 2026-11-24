// Shared building blocks, so every screen looks and behaves the same:
// buttons, choice cards, segmented options, settings rows, text fields and short notes.
import { Pressable, Text, TextInput, View, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, F } from "../theme";

const KINDS = {
  primary: { bg: C.brand, fg: C.onBrand, border: C.brand },
  light: { bg: C.card, fg: C.brandInk, border: C.line },
  quiet: { bg: "transparent", fg: C.brandInk, border: "transparent" },
  danger: { bg: C.danger, fg: "#fff", border: C.danger },
  dangerSoft: { bg: C.dangerSoft, fg: C.danger, border: C.dangerSoft },
  good: { bg: C.good, fg: "#fff", border: C.good },
  // older names
  red: { bg: C.danger, fg: "#fff", border: C.danger },
  redLight: { bg: C.dangerSoft, fg: C.danger, border: C.dangerSoft },
  green: { bg: C.good, fg: "#fff", border: C.good },
};

export function BigButton({ title, onPress, kind = "primary", disabled, style, small, icon }) {
  const k = KINDS[kind] || KINDS.primary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        s.btn, small && s.small,
        { backgroundColor: k.bg, borderColor: k.border, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 }, style,
      ]}
    >
      {icon && <Ionicons name={icon} size={small ? 18 : 21} color={k.fg} style={{ marginRight: 8 }} />}
      <Text style={[s.text, small && s.smallText, { color: k.fg }]}>{title}</Text>
    </Pressable>
  );
}

export function Heading({ children, style }) {
  return <Text style={[s.h, style]}>{children}</Text>;
}

export function Label({ children, style }) {
  return <Text style={[s.label, style]}>{children}</Text>;
}

// A choice card: an icon, a short title and one line explaining it. Used for "who is this account for?" etc.
export function Option({ icon, title, hint, selected, onPress }) {
  return (
    <Pressable accessibilityRole="radio" accessibilityState={{ selected }} onPress={onPress}
               style={({ pressed }) => [s.option, selected && s.optionOn, pressed && { opacity: 0.85 }]}>
      <View style={[s.optionIcon, selected && { backgroundColor: C.brand }]}>
        <Ionicons name={icon} size={22} color={selected ? C.onBrand : C.brandInk} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={s.optionTitle}>{title}</Text>
        {!!hint && <Text style={s.optionHint}>{hint}</Text>}
      </View>
      <Ionicons name={selected ? "radio-button-on" : "radio-button-off"} size={22} color={selected ? C.brandInk : C.faint} />
    </Pressable>
  );
}

// Two to four options side by side, one selected (like tabs inside a screen).
export function Segmented({ options, value, onChange, style }) {
  return (
    <View style={[s.seg, style]} accessibilityRole="tablist">
      {options.map(([v, label]) => (
        <Pressable key={v} accessibilityRole="tab" accessibilityState={{ selected: value === v }}
                   onPress={() => onChange(v)} style={[s.segItem, value === v && s.segOn]}>
          <Text style={[s.segText, value === v && s.segTextOn]} numberOfLines={1}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

// A settings-style row: icon, title, optional value on the right, and an arrow if it can be tapped.
export function Row({ icon, title, value, onPress, tone, last }) {
  const color = tone === "danger" ? C.danger : C.ink;
  return (
    <Pressable onPress={onPress} disabled={!onPress} accessibilityRole={onPress ? "button" : undefined}
               style={({ pressed }) => [s.row, !last && s.rowLine, pressed && onPress && { backgroundColor: C.bg }]}>
      {icon && <Ionicons name={icon} size={22} color={tone === "danger" ? C.danger : C.brandInk} style={{ width: 30 }} />}
      <Text style={[s.rowTitle, { color }]}>{title}</Text>
      {!!value && <Text style={s.rowValue} numberOfLines={1}>{value}</Text>}
      {onPress && <Ionicons name="chevron-forward" size={20} color={C.faint} />}
    </Pressable>
  );
}

export function Field({ label, style, ...props }) {
  return (
    <View style={{ marginBottom: 12 }}>
      {!!label && <Text style={s.fieldLabel}>{label}</Text>}
      <TextInput placeholderTextColor={C.faint} style={[s.input, style]} {...props} />
    </View>
  );
}

// A short message in a soft box. tone: info | good | warn | danger
export function Note({ children, tone = "info", style }) {
  const t = { info: [C.brandSoft, C.brandInk], good: [C.goodSoft, C.good], warn: [C.warnSoft, C.warn], danger: [C.dangerSoft, C.danger] }[tone];
  return <Text style={[s.note, { backgroundColor: t[0], color: t[1] }, style]}>{children}</Text>;
}

const s = StyleSheet.create({
  btn: { minHeight: 54, borderRadius: 27, paddingHorizontal: 18, paddingVertical: 12, flexDirection: "row",
         alignItems: "center", justifyContent: "center", borderWidth: 1 },
  small: { minHeight: 44, paddingVertical: 8, paddingHorizontal: 16, borderRadius: 22 },
  text: { fontSize: F.body, fontWeight: "600", textAlign: "center" },
  smallText: { fontSize: F.small },
  h: { fontSize: F.big, fontWeight: "700", color: C.ink, marginBottom: 6 },
  label: { fontSize: F.small - 1, fontWeight: "600", color: C.muted, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8, marginTop: 6 },
  option: { flexDirection: "row", alignItems: "center", gap: 12, padding: 14, borderRadius: 18, borderWidth: 1.5,
            borderColor: C.line, backgroundColor: C.card, marginBottom: 10 },
  optionOn: { borderColor: C.brand, backgroundColor: C.brandSoft },

  optionIcon: { width: 42, height: 42, borderRadius: 21, backgroundColor: C.brandSoft, alignItems: "center", justifyContent: "center" },
  optionTitle: { fontSize: F.body, fontWeight: "600", color: C.ink },
  optionHint: { fontSize: F.small - 1, color: C.muted, marginTop: 2 },
  seg: { flexDirection: "row", backgroundColor: "#EFEADD", borderRadius: 24, padding: 4, marginBottom: 14 },
  segItem: { flex: 1, paddingVertical: 10, borderRadius: 20, alignItems: "center" },
  segOn: { backgroundColor: C.brand },
  segText: { fontSize: F.small, color: C.muted, fontWeight: "600" },
  segTextOn: { color: C.onBrand },
  row: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 15, paddingHorizontal: 4 },
  rowLine: { borderBottomWidth: 1, borderColor: C.line },
  rowTitle: { flex: 1, fontSize: F.body },
  rowValue: { fontSize: F.small, color: C.muted, maxWidth: "45%" },
  fieldLabel: { fontSize: F.small, color: C.muted, marginBottom: 6, fontWeight: "600" },
  input: { fontSize: F.body, borderWidth: 1.5, borderColor: C.line, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12,
           color: C.ink, backgroundColor: C.card },
  note: { fontSize: F.small, padding: 12, borderRadius: 12, overflow: "hidden", marginBottom: 12, lineHeight: 22 },
});
