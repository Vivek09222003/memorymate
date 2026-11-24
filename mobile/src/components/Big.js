// Shared building blocks: a big button and a heading.
import { Pressable, Text, StyleSheet } from "react-native";
import { C, F } from "../theme";

export function BigButton({ title, onPress, kind = "primary", disabled, style, small }) {
  const k = KINDS[kind] || KINDS.primary;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        s.btn, small && s.small, { backgroundColor: k.bg, opacity: disabled ? 0.5 : pressed ? 0.8 : 1 }, style,
      ]}
    >
      <Text style={[s.text, small && s.smallText, { color: k.fg }]}>{title}</Text>
    </Pressable>
  );
}

export function Heading({ children, style }) {
  return <Text style={[s.h, style]}>{children}</Text>;
}

const KINDS = {
  primary: { bg: C.brand, fg: "#fff" },
  light: { bg: C.brandLight, fg: C.ink },
  red: { bg: C.red, fg: "#fff" },
  redLight: { bg: C.redLight, fg: C.redDark },
  green: { bg: C.green, fg: "#fff" },
};

const s = StyleSheet.create({
  btn: { minHeight: 56, borderRadius: 16, paddingHorizontal: 18, paddingVertical: 12, alignItems: "center", justifyContent: "center" },
  small: { minHeight: 46, paddingVertical: 8, paddingHorizontal: 14 },
  text: { fontSize: F.body, fontWeight: "700", textAlign: "center" },
  smallText: { fontSize: F.small + 1 },
  h: { fontSize: F.big, fontWeight: "800", color: C.ink, marginBottom: 8 },
});
