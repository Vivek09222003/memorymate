// First screen: where the MemoryMate server is, then email and password.
import { useState } from "react";
import { View, Text, TextInput, StyleSheet, ScrollView, KeyboardAvoidingView, Platform } from "react-native";
import { BigButton, Heading } from "../components/Big";
import { autoServer, getBaseUrl, login, ping, saveServer } from "../api";
import { C, F, card } from "../theme";

export default function LoginScreen({ onLogin }) {
  // Filled in automatically from the laptop that sent the app; can still be changed by hand.
  const [server, setServer] = useState((autoServer() || getBaseUrl()).replace(/^http:\/\//, ""));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true); setMsg("");
    try {
      await saveServer(server);
      await ping();
      setMsg("✅ Connected to MemoryMate.");
    } catch (e) { setMsg(e.message); }
    setBusy(false);
  }

  async function submit() {
    if (!server.trim()) return setMsg("Please enter the server address first.");
    setBusy(true); setMsg("");
    try {
      await saveServer(server);
      const me = await login(email, password);
      onLogin(me);
    } catch (e) { setMsg(e.message); setBusy(false); }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={s.wrap} keyboardShouldPersistTaps="handled">
        <Text style={s.logo}>🧠 MemoryMate</Text>
        <Text style={s.tag}>Your memory companion</Text>

        <View style={card}>
          <Heading>Server address</Heading>
          <Text style={s.help}>{autoServer() ? "Filled in automatically from your laptop. Just tap Check connection." : "Your laptop's address on the Wi-Fi, for example 192.168.1.5:8000"}</Text>
          <TextInput style={s.input} value={server} onChangeText={setServer} placeholder="192.168.1.5:8000"
                     autoCapitalize="none" autoCorrect={false} keyboardType="url" />
          <BigButton title="Check connection" kind="light" onPress={check} disabled={busy} small />
        </View>

        <View style={card}>
          <Heading>Log in</Heading>
          <TextInput style={s.input} value={email} onChangeText={setEmail} placeholder="Email"
                     autoCapitalize="none" autoCorrect={false} keyboardType="email-address" textContentType="username" />
          <TextInput style={s.input} value={password} onChangeText={setPassword} placeholder="Password"
                     secureTextEntry textContentType="password" onSubmitEditing={submit} />
          <BigButton title={busy ? "Please wait…" : "Log in"} onPress={submit} disabled={busy || !email || !password} />
        </View>

        {!!msg && <Text style={[s.msg, msg.startsWith("✅") && { color: C.green }]}>{msg}</Text>}
        <Text style={s.help}>New here? Create your account on the MemoryMate test page for now: http://your-laptop:8000/test</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { padding: 18, paddingTop: 40 },
  logo: { fontSize: 38, fontWeight: "800", color: C.ink, textAlign: "center" },
  tag: { fontSize: F.body, color: C.muted, textAlign: "center", marginBottom: 20 },
  help: { fontSize: F.small, color: C.muted, marginBottom: 10 },
  input: { fontSize: F.body, borderWidth: 2, borderColor: C.line, borderRadius: 14, padding: 14, marginBottom: 12, color: C.ink, backgroundColor: "#fff" },
  msg: { fontSize: F.body, color: C.red, textAlign: "center", marginVertical: 10 },
});
