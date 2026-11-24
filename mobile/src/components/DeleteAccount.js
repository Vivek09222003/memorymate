// "Delete my account": explains what happens, asks for the password, and needs a second tap to confirm.
import { useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { deleteAccount } from "../api";
import { BigButton, Field, Note } from "./Big";
import { C, F } from "../theme";

export default function DeleteAccount({ isElder, onDeleted }) {
  const [password, setPassword] = useState("");
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  async function go() {
    setMsg(null);
    if (!password) return setMsg({ tone: "warn", text: "Please enter your password first." });
    if (!armed) { setArmed(true); return; }
    setBusy(true);
    try { await deleteAccount(password); onDeleted(); }
    catch (e) { setMsg({ tone: "danger", text: e.message }); setArmed(false); setBusy(false); }
  }

  return (
    <View style={s.box}>
      <Text style={s.text}>
        {isElder
          ? "This permanently deletes your account and everything in it: memories, chats, reminders, people and emergency details. Your family and doctor lose access. This can't be undone."
          : "This permanently deletes your account. You lose access to the people you look after; their own information stays with them. This can't be undone."}
      </Text>
      <Field label="Your password" value={password} onChangeText={(t) => { setPassword(t); setArmed(false); }}
             secureTextEntry placeholder="Password" textContentType="password" />
      {msg && <Note tone={msg.tone}>{msg.text}</Note>}
      <BigButton kind="danger" icon="trash-outline" disabled={busy}
                 title={busy ? "Deleting…" : armed ? "Tap again to delete forever" : "Delete my account"} onPress={go} />
      {armed && !busy && (
        <BigButton kind="quiet" title="Cancel" onPress={() => setArmed(false)} style={{ marginTop: 4 }} />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  box: { paddingTop: 4, paddingBottom: 14, paddingHorizontal: 4 },
  text: { fontSize: F.small, color: C.muted, lineHeight: 22, marginBottom: 10 },
});
