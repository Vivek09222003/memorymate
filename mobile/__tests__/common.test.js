// Labels and dates used by the family / doctor screens.
jest.mock("expo-secure-store", () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn() }));

import { dayString, isDoctorLink, roleFor, timeOf } from "../src/family/common";

describe("roleFor: shows the elder's role from the helper's side", () => {
  test.each([
    ["daughter", "Your parent"],
    ["son", "Your parent"],
    ["Daughter-in-law", "Your parent-in-law"],
    ["grandson", "Your grandparent"],
    ["doctor", "Your patient"],
    ["family doctor", "Your patient"],
    ["wife", "Your spouse"],
    ["caregiver", "In your care"],
    ["", "Family"],
    [null, "Family"],
  ])("%s -> %s", (relation, label) => {
    expect(roleFor(relation)).toBe(label);
  });
});

test("isDoctorLink spots doctors and nurses only", () => {
  expect(isDoctorLink("doctor")).toBe(true);
  expect(isDoctorLink("Nurse")).toBe(true);
  expect(isDoctorLink("daughter")).toBe(false);
  expect(isDoctorLink(undefined)).toBe(false);
});

test("timeOf keeps only the clock time", () => {
  expect(timeOf("Tue 24 Nov, 9:00 PM")).toBe("9:00 PM");
  expect(timeOf("")).toBe("");
});

test("dayString gives local dates as YYYY-MM-DD, tomorrow after today", () => {
  const today = dayString(0);
  const tomorrow = dayString(1);
  expect(today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(tomorrow).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(new Date(tomorrow) - new Date(today)).toBe(24 * 60 * 60 * 1000);
});
