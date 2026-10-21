import test from "node:test";
import assert from "node:assert/strict";
import { isoDate, addDays, shiftMonth, monthCells, eventsOnDay, holidayState, lunarLabel, filterEvents } from "../web/calendar.mjs";

test("today uses Shanghai even when UTC is still the previous day", () => {
  assert.equal(isoDate(new Date("2026-10-20T17:00:00Z")), "2026-10-21");
});

test("month navigation clamps long months and handles leap years", () => {
  assert.equal(shiftMonth("2026-01-31", 1), "2026-02-28");
  assert.equal(shiftMonth("2028-01-31", 1), "2028-02-29");
  assert.equal(shiftMonth("2026-12-31", 1), "2027-01-31");
  assert.equal(addDays("2028-02-28", 1), "2028-02-29");
});

test("calendar weeks start on Monday and include every date exactly once", () => {
  const cells = monthCells("2026-10-21");
  assert.equal(cells[0], "2026-09-28");
  assert.equal(cells.at(-1), "2026-11-01");
  assert.equal(cells.filter(day => day.startsWith("2026-10")).length, 31);
  assert.equal(new Set(cells).size, cells.length);
});

const holiday = { kind: "holiday", start: "2026-10-01", end: "2026-10-08", all_day: true };
const work = { kind: "workday", start: "2026-02-14", end: "2026-02-15", all_day: true };

test("multi-day events remain visible throughout the holiday, with an exclusive end", () => {
  assert.equal(eventsOnDay([holiday], "2026-10-03").length, 1);
  assert.equal(eventsOnDay([holiday], "2026-10-07").length, 1);
  assert.equal(eventsOnDay([holiday], "2026-10-08").length, 0);
});

test("timed solar terms match Beijing date rather than the viewer timezone", () => {
  const term = { start: "2026-01-01T16:01:00Z", end: "2026-01-01T16:02:00Z", all_day: false };
  assert.equal(eventsOnDay([term], "2026-01-01").length, 0);
  assert.equal(eventsOnDay([term], "2026-01-02").length, 1);
});

test("makeup weekends and unpublished schedules are not inferred from weekdays", () => {
  assert.equal(holidayState("2026-02-14", [work], [2026]).marker, "班");
  assert.equal(holidayState("2026-10-03", [holiday], [2026]).marker, "休");
  assert.equal(holidayState("2027-01-02", [], [2026]).kind, "unknown");
  assert.equal(holidayState("2026-10-18", [], [2026]).kind, "weekend");
});

test("lunar labels preserve leap-month information and absent data", () => {
  assert.equal(lunarLabel([6, 1, true]), "闰六月");
  assert.equal(lunarLabel([12, 27, false], true), "农历腊月廿七");
  assert.equal(lunarLabel(null, true), "农历数据未收录");
});

test("essential preview excludes social observances", () => {
  const events = [holiday, work, { kind: "observance" }, { kind: "solar_term" }];
  assert.equal(filterEvents(events, "essential").length, 3);
  assert.equal(filterEvents(events, "solar-terms").length, 1);
});
