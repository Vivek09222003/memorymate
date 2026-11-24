// Calm, warm and low-glare: a cream page, white rounded cards, and one soft honey accent
// (always with dark text on it). Warnings use muted amber and brick, never bright red.
export const C = {
  bg: "#F7F4EC",          // warm cream page
  card: "#FFFFFF",
  ink: "#26241F",         // main text (warm charcoal, softer than black)
  muted: "#6E6A60",       // secondary text
  faint: "#9A958A",
  line: "#E9E4D8",        // thin borders and dividers
  brand: "#E3B54A",       // soft honey: main buttons, your chat bubbles, selected options
  onBrand: "#2B2414",     // text and icons on honey
  brandSoft: "#FBF2D9",   // pale honey: selected items, hints
  brandInk: "#7A5A12",    // honey-brown text for links and labels
  good: "#4E7A5B",        // muted green: done / all good
  goodSoft: "#E7EFE8",
  warn: "#93682A",        // muted amber: missed medicine
  warnSoft: "#F5EEDF",
  danger: "#9C4A42",      // muted brick: emergency
  dangerSoft: "#F4E5E2",
  // older names, kept so nothing breaks
  sun: "#F5F4F0", red: "#9C4A42", redDark: "#7E3A33", redLight: "#F4E5E2",
  green: "#4E7A5B", greenLight: "#E7EFE8", orange: "#93682A", orangeLight: "#F5EEDF", brandLight: "#FBF2D9",
};

export const F = { small: 16, body: 19, big: 23, huge: 28 };

export const card = {
  backgroundColor: C.card,
  borderRadius: 16,
  padding: 16,
  marginBottom: 12,
  borderWidth: 1,
  borderColor: C.line,
};

export const shadow = {
  shadowColor: "#26241F",
  shadowOpacity: 0.06,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 3 },
  elevation: 1,
};
