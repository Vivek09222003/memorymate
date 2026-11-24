// The main screen: talk to MemoryMate. Big bubbles, big Yes / No buttons when it asks a question.
import { useEffect, useRef, useState } from "react";
import { View, Text, TextInput, FlatList, StyleSheet, KeyboardAvoidingView, Platform, Pressable, ActivityIndicator } from "react-native";
import { api } from "../api";
import { syncAlarms } from "../notify";
import { BigButton } from "../components/Big";
import { C, F } from "../theme";

const YES_NO = {
  en: ["Yes", "No"],
  hi: ["हाँ", "नहीं"],
  hinglish: ["Haan", "Nahi"],
};
const HELLO = {
  en: "Hello! Tell me anything you'd like me to remember, or ask me something.",
  hi: "नमस्ते! जो याद रखना हो बताइए, या कुछ भी पूछिए।",
  hinglish: "Namaste! Jo yaad rakhna ho bataiye, ya kuch bhi poochiye.",
};

export default function ChatScreen({ me, onEmergency }) {
  const lang = me.preferred_language || "en";
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [askYesNo, setAskYesNo] = useState(false);
  const [offerHelp, setOfferHelp] = useState(false);
  const list = useRef(null);

  useEffect(() => {
    api("/chat/history", { query: { limit: 40 } })
      .then((h) => setMsgs(h.length ? h.map((m, i) => ({ id: "h" + i, who: m.role, text: m.text }))
                                    : [{ id: "hello", who: "assistant", text: HELLO[lang] || HELLO.en }]))
      .catch(() => setMsgs([{ id: "hello", who: "assistant", text: HELLO[lang] || HELLO.en }]));
  }, []);

  const add = (who, t) => setMsgs((m) => [...m, { id: String(Date.now()) + Math.random(), who, text: t }]);

  async function send(message) {
    const t = (message ?? text).trim();
    if (!t || busy) return;
    setText(""); setAskYesNo(false); setOfferHelp(false);
    add("user", t);
    setBusy(true);
    try {
      const out = await api("/chat", { method: "POST", body: { message: t } });
      add("assistant", out.reply);
      setAskYesNo(!!out.waiting_for_yes_or_no);
      setOfferHelp(!!out.suggest_help);
      if (out.emergency) onEmergency(out.emergency);
      syncAlarms(); // a "yes" may have just set a reminder
    } catch (e) {
      add("error", e.message);
    }
    setBusy(false);
  }

  async function alertFamily() {
    setOfferHelp(false);
    try {
      const a = await api("/emergency/sos", { method: "POST", body: { message: "Asked for help from the chat" } });
      onEmergency(a);
    } catch (e) { add("error", "Couldn't send the alert: " + e.message + " Please call 108."); }
  }

  const [yes, no] = YES_NO[lang] || YES_NO.en;
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : "height"} keyboardVerticalOffset={80}>
      <FlatList
        ref={list}
        data={msgs}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: 12, gap: 10 }}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        renderItem={({ item }) => (
          <View style={[s.bubble, item.who === "user" ? s.me : item.who === "error" ? s.err : s.them]}>
            <Text style={[s.text, item.who === "user" && { color: "#fff" }]}>{item.text}</Text>
          </View>
        )}
        ListFooterComponent={busy ? <View style={s.thinking}><ActivityIndicator color={C.brand} /><Text style={s.muted}>  MemoryMate is thinking…</Text></View> : null}
      />

      {offerHelp && (
        <View style={s.row}>
          <BigButton title="🚨 Alert my family now" kind="red" onPress={alertFamily} style={{ flex: 1 }} />
        </View>
      )}
      {askYesNo && !busy && (
        <View style={s.row}>
          <BigButton title={"✔ " + yes} kind="green" onPress={() => send(yes.toLowerCase())} style={{ flex: 1 }} />
          <BigButton title={"✖ " + no} kind="light" onPress={() => send(no.toLowerCase())} style={{ flex: 1 }} />
        </View>
      )}

      <View style={s.inputRow}>
        <TextInput
          style={s.input}
          value={text}
          onChangeText={setText}
          placeholder="Type here…"
          multiline
          onSubmitEditing={() => send()}
        />
        <Pressable accessibilityLabel="Send" onPress={() => send()} disabled={busy || !text.trim()}
                   style={({ pressed }) => [s.send, (busy || !text.trim()) && { opacity: 0.4 }, pressed && { opacity: 0.7 }]}>
          <Text style={s.sendText}>➤</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  bubble: { maxWidth: "85%", padding: 14, borderRadius: 18 },
  me: { alignSelf: "flex-end", backgroundColor: C.brand },
  them: { alignSelf: "flex-start", backgroundColor: C.card },
  err: { alignSelf: "center", backgroundColor: C.redLight },
  text: { fontSize: F.body, color: C.ink, lineHeight: 28 },
  thinking: { flexDirection: "row", alignItems: "center", padding: 10 },
  muted: { fontSize: F.small, color: C.muted },
  row: { flexDirection: "row", gap: 10, paddingHorizontal: 12, paddingBottom: 8 },
  inputRow: { flexDirection: "row", gap: 8, padding: 10, borderTopWidth: 1, borderColor: C.line, backgroundColor: C.bg, alignItems: "flex-end" },
  input: { flex: 1, fontSize: F.body, borderWidth: 2, borderColor: C.line, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, maxHeight: 130, backgroundColor: "#fff", color: C.ink },
  send: { width: 58, height: 58, borderRadius: 29, backgroundColor: C.brand, alignItems: "center", justifyContent: "center" },
  sendText: { color: "#fff", fontSize: 26 },
});
