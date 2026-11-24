// The frame around every screen: a quiet header, slim banners for urgent things, and the bottom tab bar.
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { C, F } from "../theme";

export function greeting(name) {
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  return `${part}, ${String(name || "").split(" ")[0]}`;
}

export function todayLine() {
  return new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
}

export function Header({ title, subtitle, right }) {
  return (
    <View style={s.header}>
      <View style={{ flex: 1 }}>
        <Text style={s.title} numberOfLines={1}>{title}</Text>
        {!!subtitle && <Text style={s.subtitle} numberOfLines={1}>{subtitle}</Text>}
      </View>
      {right}
    </View>
  );
}

// tone: danger | warn | info
export function Banner({ tone = "info", icon, text, onPress }) {
  const t = { danger: [C.danger, "#fff"], warn: [C.warnSoft, C.warn], info: [C.brandSoft, C.brandInk] }[tone];
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={[s.banner, { backgroundColor: t[0] }]}>
      {icon && <Ionicons name={icon} size={20} color={t[1]} style={{ marginRight: 8 }} />}
      <Text style={[s.bannerText, { color: t[1] }]}>{text}</Text>
      <Ionicons name="chevron-forward" size={18} color={t[1]} />
    </Pressable>
  );
}

// tabs: [key, icon, label]; dots: { key: true } shows a small dot on that tab
export function TabBar({ tabs, value, onChange, dots = {} }) {
  return (
    <View style={s.tabs} accessibilityRole="tablist">
      {tabs.map(([key, icon, label]) => {
        const on = value === key;
        const color = on ? C.onBrand : C.faint;
        return (
          <Pressable key={key} accessibilityRole="tab" accessibilityLabel={label} accessibilityState={{ selected: on }}
                     onPress={() => onChange(key)} style={s.tab}>
            <View style={[s.pill, on && { backgroundColor: C.brand }]}>
              <Ionicons name={on ? icon : icon + "-outline"} size={24} color={key === "help" && !on ? C.danger : color} />
            </View>
            <Text style={[s.tabText, { color: key === "help" && !on ? C.danger : on ? C.ink : C.muted }, on && { fontWeight: "700" }]}>{label}</Text>
            {dots[key] && <View style={s.dot} />}
          </Pressable>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  header: { paddingHorizontal: 20, paddingTop: 14, paddingBottom: 12, flexDirection: "row", alignItems: "center",
            backgroundColor: C.bg },
  title: { fontSize: F.big, fontWeight: "700", color: C.ink },
  subtitle: { fontSize: F.small - 1, color: C.muted, marginTop: 2 },
  banner: { flexDirection: "row", alignItems: "center", paddingVertical: 12, paddingHorizontal: 16 },
  bannerText: { flex: 1, fontSize: F.small + 1, fontWeight: "600" },
  tabs: { flexDirection: "row", borderTopWidth: 1, borderColor: C.line, backgroundColor: C.card, paddingTop: 6, paddingBottom: 4 },
  tab: { flex: 1, alignItems: "center", paddingVertical: 4 },
  tabText: { fontSize: 13, marginTop: 3, fontWeight: "500" },
  pill: { paddingHorizontal: 16, paddingVertical: 4, borderRadius: 16 },
  dot: { position: "absolute", top: 2, right: "30%", width: 10, height: 10, borderRadius: 5, backgroundColor: C.warn },
});
