import test from "node:test";
import assert from "node:assert/strict";
import { isoDate, addDays, shiftMonth, monthCells, eventsOnDay, holidayState, lunarLabel, filterEvents, nextHoliday, holidayCountdown, isValidDay, weekBounds, daysBetween } from "../web/calendar.mjs";

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

const national = { kind: "holiday", summary: "国庆节（休）", start: "2026-10-01", end: "2026-10-08", all_day: true };
const spring = { kind: "holiday", summary: "春节（休）", start: "2026-02-15", end: "2026-02-24", all_day: true };

test("next holiday counts down to the nearest published holiday only", () => {
  const before = nextHoliday([national, spring, work], "2026-09-28");
  assert.deepEqual([before.name, before.ongoing, before.days, before.length], ["国庆节", false, 3, 7]);
  assert.equal(holidayCountdown(before), "国庆节 · 还有 3 天");
  assert.equal(holidayCountdown(nextHoliday([national], "2026-09-30")), "国庆节 · 明天放假");
  assert.equal(nextHoliday([spring, national], "2026-01-01").name, "春节");
});

test("an ongoing holiday reports the remaining days, inclusive of today", () => {
  assert.equal(holidayCountdown(nextHoliday([national], "2026-10-05")), "国庆节 · 假期还剩 3 天");
  assert.equal(holidayCountdown(nextHoliday([national], "2026-10-07")), "国庆节 · 假期最后一天");
});

test("no countdown is invented once published holidays run out", () => {
  assert.equal(nextHoliday([national, work], "2026-10-08"), null);
  assert.equal(holidayCountdown(null), "待正式公布");
});

test("shared date links accept only real calendar dates", () => {
  assert.ok(isValidDay("2028-02-29"));
  for (const value of ["2026-02-30", "2026-2-1", "2026-13-01", "", null, "2026-10-01x"]) {
    assert.equal(isValidDay(value), false, String(value));
  }
});

test("week bounds follow the Monday-first grid", () => {
  assert.deepEqual(weekBounds("2026-10-21"), ["2026-10-19", "2026-10-25"]);
  assert.deepEqual(weekBounds("2026-10-25"), ["2026-10-19", "2026-10-25"]);
  assert.equal(daysBetween("2026-12-31", "2027-01-01"), 1);
});
