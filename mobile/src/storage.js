// Small key-value storage. On a phone: the secure Keychain / Keystore. In a laptop browser: localStorage.
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const web = Platform.OS === "web";

export async function getItem(key) {
  if (web) { try { return window.localStorage.getItem(key); } catch (e) { return null; } }
  return SecureStore.getItemAsync(key);
}

export async function setItem(key, value) {
  if (web) { try { window.localStorage.setItem(key, value); } catch (e) { /* private mode */ } return; }
  return SecureStore.setItemAsync(key, value);
}

export async function removeItem(key) {
  if (web) { try { window.localStorage.removeItem(key); } catch (e) { /* ignore */ } return; }
  return SecureStore.deleteItemAsync(key);
}
