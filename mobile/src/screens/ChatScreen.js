// Talk: chat with MemoryMate. Clean bubbles, clear Yes / No choices when it asks something,
// and a few ready-made questions to tap, so you don't always have to type.
import { useEffect, useRef, useState } from "react";
import { View, Text, TextInput, FlatList, StyleSheet, KeyboardAvoidingView, Platform, Pressable, ActivityIndicator } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../api";
import { syncAlarms } from "../notify";
import { BigButton } from "../components/Big";
import { C, F } from "../theme";

const YES_NO = { en: ["Yes", "No"], hi: ["हाँ", "नहीं"], hinglish: ["Haan", "Nahi"] };
const HELLO = {
  en: "Hello! Tell me anything you'd like me to remember, or ask me something.",
  hi: "नमस्ते! जो याद रखना हो बताइए, या कुछ भी पूछिए।",
  hinglish: "Namaste! Jo yaad rakhna ho bataiye, ya kuch bhi poochiye.",
};
const IDEAS = {
  en: ["What do I have today?", "Remind me to take my medicine at 9 pm", "Who are my emergency contacts?"],
  hi: ["आज मेरे क्या काम हैं?", "रात 9 बजे दवा की याद दिलाना", "मेरे इमरजेंसी कॉन्टैक्ट कौन हैं?"],
  hinglish: ["Aaj mere kya kaam hain?", "Raat 9 baje dawai yaad dilana", "Mere emergency contacts kaun hain?"],
};
const TYPE_HERE = { en: "Type a message…", hi: "यहाँ लिखिए…", hinglish: "Yahan likhiye…" };

export default function ChatScreen({ me, onEmergency }) {
  const lang = me.preferred_language || "en";
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [askYesNo, setAskYesNo] = useState(false);
  const [offerHelp, setOfferHelp] = useState(false);
  const list = useRef(null);

  useEffect(() => {
    const hello = [{ id: "hello", who: "assistant", text: HELLO[lang] || HELLO.en }];
    api("/chat/history", { query: { limit: 40 } })
      .then((h) => setMsgs(h.length ? h.map((m, i) => ({ id: "h" + i, who: m.role, text: m.text })) : hello))
      .catch(() => setMsgs(hello));
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
  const fresh = msgs.filter((m) => m.who === "user").length === 0;
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : "height"} keyboardVerticalOffset={90}>
      <FlatList
        ref={list}
        data={msgs}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        renderItem={({ item }) => (
          <View style={[s.bubble, item.who === "user" ? s.me : item.who === "error" ? s.err : s.them]}>
            <Text style={[s.text, item.who === "user" && { color: C.onBrand }, item.who === "error" && { color: C.danger }]}>{item.text}</Text>
          </View>
        )}
        ListFooterComponent={
          busy ? (
            <View style={s.thinking}><ActivityIndicator color={C.brand} /><Text style={s.muted}>  Thinking…</Text></View>
          ) : fresh ? (
            <View style={{ marginTop: 6 }}>
              <Text style={s.muted}>You can try:</Text>
              {(IDEAS[lang] || IDEAS.en).map((idea) => (
                <Pressable key={idea} onPress={() => send(idea)} style={({ pressed }) => [s.idea, pressed && { opacity: 0.7 }]}>
                  <Ionicons name="chatbubble-outline" size={16} color={C.brandInk} />
                  <Text style={s.ideaText}>{idea}</Text>
                </Pressable>
              ))}
            </View>
          ) : null
        }
      />

      {offerHelp && (
        <View style={s.row}>
          <BigButton title="Alert my family now" icon="alert-circle-outline" kind="dangerSoft" onPress={alertFamily} style={{ flex: 1 }} />
        </View>
      )}
      {askYesNo && !busy && (
        <View style={s.row}>
          <BigButton title={yes} icon="checkmark" kind="primary" onPress={() => send(yes.toLowerCase())} style={{ flex: 1 }} />
          <BigButton title={no} icon="close" kind="light" onPress={() => send(no.toLowerCase())} style={{ flex: 1 }} />
        </View>
      )}

      <View style={s.inputRow}>
        <TextInput
          style={s.input}
          value={text}
          onChangeText={setText}
          placeholder={TYPE_HERE[lang] || TYPE_HERE.en}
          placeholderTextColor={C.faint}
          multiline
        />
        <Pressable accessibilityLabel="Send" onPress={() => send()} disabled={busy || !text.trim()}
                   style={({ pressed }) => [s.send, (busy || !text.trim()) && { opacity: 0.35 }, pressed && { opacity: 0.7 }]}>
          <Ionicons name="arrow-up" size={26} color={C.onBrand} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  bubble: { maxWidth: "86%", paddingVertical: 12, paddingHorizontal: 15, borderRadius: 18 },
  me: { alignSelf: "flex-end", backgroundColor: C.brand, borderBottomRightRadius: 6 },
  them: { alignSelf: "flex-start", backgroundColor: C.card, borderWidth: 1, borderColor: C.line, borderBottomLeftRadius: 6,
          shadowColor: "#26241F", shadowOpacity: 0.05, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 1 },
  err: { alignSelf: "center", backgroundColor: C.dangerSoft },
  text: { fontSize: F.body, color: C.ink, lineHeight: 27 },
  thinking: { flexDirection: "row", alignItems: "center", padding: 8 },
  muted: { fontSize: F.small, color: C.muted, marginBottom: 6 },
  idea: { flexDirection: "row", alignItems: "center", gap: 8, alignSelf: "flex-start", backgroundColor: C.card,
          borderWidth: 1, borderColor: C.line,
          paddingVertical: 10, paddingHorizontal: 14, borderRadius: 20, marginBottom: 8 },
  ideaText: { fontSize: F.small, color: C.brandInk },
  row: { flexDirection: "row", gap: 10, paddingHorizontal: 16, paddingBottom: 8 },
  inputRow: { flexDirection: "row", gap: 8, paddingHorizontal: 12, paddingVertical: 10, borderTopWidth: 1, borderColor: C.line,
              backgroundColor: C.bg, alignItems: "flex-end" },
  input: { flex: 1, fontSize: F.body, borderWidth: 1.5, borderColor: C.line, borderRadius: 25, paddingHorizontal: 18, paddingVertical: 12,
           maxHeight: 130, backgroundColor: C.card, color: C.ink },
  send: { width: 50, height: 50, borderRadius: 25, backgroundColor: C.brand, alignItems: "center", justifyContent: "center" },
});
