// Welcome screen: one place to log in or create an account.
// Instead of separate forms for elders, family and doctors, you pick who the account is for.
import { useState } from "react";
import { View, Text, ScrollView, StyleSheet, KeyboardAvoidingView, Platform, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { BigButton, Field, Label, Note, Option, Segmented } from "../components/Big";
import { autoServer, getBaseUrl, login, ping, register, saveServer } from "../api";
import { C, F } from "../theme";

const WHO = [
  ["ELDER", "person-outline", "For me", "I want help remembering things and taking medicines on time"],
  ["FAMILY", "people-outline", "For a family member", "I help look after a parent or relative"],
  ["DOCTOR", "medkit-outline", "I'm a doctor or caregiver", "I look after a patient's health"],
];
const LANGS = [["en", "English"], ["hi", "हिन्दी"], ["hinglish", "Hinglish"]];

export default function LoginScreen({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [who, setWho] = useState("ELDER");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [lang, setLang] = useState("en");
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState(null);           // { tone, text }
  const [busy, setBusy] = useState(false);
  const [showServer, setShowServer] = useState(false);
  const [server, setServer] = useState((autoServer() || getBaseUrl()).replace(/^https?:\/\//, ""));

  const helper = who !== "ELDER";

  async function useServer() {
    if (!server.trim()) throw new Error("Please add the server address under Connection settings.");
    await saveServer(server);
  }

  async function check() {
    setBusy(true); setMsg(null);
    try { await useServer(); await ping(); setMsg({ tone: "good", text: "Connected to MemoryMate." }); }
    catch (e) { setMsg({ tone: "danger", text: e.message }); }
    setBusy(false);
  }

  async function submit() {
    setMsg(null);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) return setMsg({ tone: "warn", text: "Please enter a valid email address." });
    if (password.length < 6) return setMsg({ tone: "warn", text: "The password needs at least 6 characters." });
    if (mode === "create" && !name.trim()) return setMsg({ tone: "warn", text: "Please enter your name." });
    setBusy(true);
    try {
      await useServer();
      const me = mode === "login"
        ? await login(email, password)
        : await register({
            name: name.trim(), email: email.trim(), password, role: who,
            preferred_language: helper ? "en" : lang,
            phone: !helper && phone.trim() ? phone.trim() : null,
            invite_code: helper && code.trim() ? code.trim().toUpperCase() : null,
          });
      onLogin(me);
    } catch (e) { setMsg({ tone: "danger", text: e.message }); setBusy(false); }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={s.wrap} keyboardShouldPersistTaps="handled">
        <View style={s.logo}><Ionicons name="sparkles-outline" size={30} color={C.onBrand} /></View>
        <Text style={s.title}>MemoryMate</Text>
        <Text style={s.tag}>Remembers for you. Reminds you on time.</Text>

        <Segmented options={[["login", "Log in"], ["create", "Create account"]]} value={mode}
                   onChange={(m) => { setMode(m); setMsg(null); }} style={{ marginTop: 8 }} />

        {mode === "create" && (
          <>
            <Label>Who is this account for?</Label>
            {WHO.map(([v, icon, title, hint]) => (
              <Option key={v} icon={icon} title={title} hint={hint} selected={who === v} onPress={() => setWho(v)} />
            ))}
            <Label style={{ marginTop: 14 }}>Your details</Label>
            <Field label="Your name" value={name} onChangeText={setName} placeholder="e.g. Vivek Chandra" autoCapitalize="words" />
          </>
        )}

        <Field label="Email" value={email} onChangeText={setEmail} placeholder="you@example.com"
               autoCapitalize="none" autoCorrect={false} keyboardType="email-address" textContentType="username" />
        <Field label={mode === "create" ? "Choose a password (6 or more characters)" : "Password"} value={password}
               onChangeText={setPassword} placeholder="Password" secureTextEntry
               textContentType={mode === "create" ? "newPassword" : "password"} onSubmitEditing={mode === "login" ? submit : undefined} />

        {mode === "create" && !helper && (
          <>
            <Field label="Your phone number (optional)" value={phone} onChangeText={setPhone}
                   placeholder="So family can call you in an emergency" keyboardType="phone-pad" />
            <Text style={s.fieldLabel}>MemoryMate should talk to me in</Text>
            <Segmented options={LANGS} value={lang} onChange={setLang} />
          </>
        )}
        {mode === "create" && helper && (
          <Field label={`Code from your ${who === "DOCTOR" ? "patient" : "relative"} (optional)`} value={code} onChangeText={setCode}
                 placeholder="e.g. K7M2Q9RD" autoCapitalize="characters" autoCorrect={false} />
        )}

        {msg && <Note tone={msg.tone}>{msg.text}</Note>}

        <BigButton title={busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"} onPress={submit} disabled={busy} />

        <Pressable onPress={() => setShowServer((v) => !v)} style={s.link} accessibilityRole="button">
          <Ionicons name="settings-outline" size={16} color={C.muted} />
          <Text style={s.linkText}>  Connection settings</Text>
        </Pressable>
        {showServer && (
          <View style={s.server}>
            <Field label="Server address" value={server} onChangeText={setServer} placeholder="memorymate-grie.onrender.com"
                   autoCapitalize="none" autoCorrect={false} keyboardType="url" />
            <BigButton small kind="light" title="Check connection" onPress={check} disabled={busy} />
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { padding: 22, paddingTop: 36 },
  logo: { alignSelf: "center", width: 62, height: 62, borderRadius: 20, backgroundColor: C.brand, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 30, fontWeight: "700", color: C.ink, textAlign: "center", marginTop: 10 },
  tag: { fontSize: F.small, color: C.muted, textAlign: "center", marginBottom: 18 },
  fieldLabel: { fontSize: F.small, color: C.muted, marginBottom: 6, fontWeight: "600" },
  link: { flexDirection: "row", alignItems: "center", justifyContent: "center", paddingVertical: 18 },
  linkText: { fontSize: F.small, color: C.muted },
  server: { backgroundColor: C.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: C.line },
});
