// Small helpers shared by the family / doctor screens.
import { Linking } from "react-native";
import * as SecureStore from "expo-secure-store";

// The link stores YOUR relation to them ("daughter"); show THEIR role for you, gender-neutral.
const ROLE = [
  [/\b(daughter-in-law|son-in-law)\b/, "Your parent-in-law"],
  [/\b(daughter|son|child|kid)\b/, "Your parent"],
  [/\b(granddaughter|grandson|grandchild)\b/, "Your grandparent"],
  [/\b(wife|husband|spouse|partner)\b/, "Your spouse"],
  [/\b(sister|brother|sibling)\b/, "Your sibling"],
  [/\b(niece|nephew)\b/, "Your aunt or uncle"],
  [/\b(doctor|physician|nurse)\b/, "Your patient"],
  [/\b(caregiver|carer|attendant)\b/, "In your care"],
  [/\b(friend)\b/, "Your friend"],
  [/\b(neighbou?r)\b/, "Your neighbour"],
];
export const roleFor = (rel) => {
  const r = (rel || "").toLowerCase();
  for (const [re, label] of ROLE) if (re.test(r)) return label;
  return "Family";
};
export const isDoctorLink = (rel) => /doctor|nurse|physician/i.test(rel || "");

export const call = (phone) => Linking.openURL("tel:" + String(phone || "").replace(/[^0-9+]/g, ""));
export const timeOf = (when) => String(when || "").split(", ").pop();

// A small list of ids kept between app starts (e.g. missed doses you tapped "OK" on).
export async function loadIds(key) {
  try { return JSON.parse((await SecureStore.getItemAsync(key)) || "[]"); } catch (e) { return []; }
}
export async function saveIds(key, ids) {
  try { await SecureStore.setItemAsync(key, JSON.stringify(ids.slice(-60))); } catch (e) { /* not important */ }
}

// Local dates as "YYYY-MM-DD" (not UTC, so "today" is India's today).
export function dayString(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
