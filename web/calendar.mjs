const shanghai = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
});

export function isoDate(value = new Date()) {
  const parts = Object.fromEntries(shanghai.formatToParts(value).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function addDays(day, count) {
  const value = new Date(`${day}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + count);
  return value.toISOString().slice(0, 10);
}

export function shiftMonth(day, count) {
  const [year, month, dayNumber] = day.split("-").map(Number);
  const target = new Date(Date.UTC(year, month - 1 + count, 1));
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(last, dayNumber));
  return target.toISOString().slice(0, 10);
}

export function monthCells(day) {
  const [year, month] = day.split("-").map(Number);
  const first = `${year}-${String(month).padStart(2, "0")}-01`;
  const offset = (new Date(`${first}T12:00:00Z`).getUTCDay() + 6) % 7;
  const count = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const start = addDays(first, -offset);
  return Array.from({ length: Math.ceil((count + offset) / 7) * 7 }, (_, i) => addDays(start, i));
}

export function eventsOnDay(events, day) {
  const lower = Date.parse(`${day}T00:00:00+08:00`);
  const upper = lower + 86_400_000;
  return events.filter(event => event.all_day
    ? event.start <= day && day < event.end
    : Date.parse(event.start) < upper && Date.parse(event.end) > lower);
}

export function filterEvents(events, filter) {
  const kinds = {
    essential: ["holiday", "workday", "traditional", "solar_term"],
    holidays: ["holiday", "workday"],
    "solar-terms": ["solar_term"],
  }[filter];
  return kinds ? events.filter(event => kinds.includes(event.kind)) : events;
}

export function holidayState(day, events, published) {
  const arrangement = eventsOnDay(events, day).find(event => ["holiday", "workday"].includes(event.kind));
  if (arrangement) return arrangement.kind === "holiday"
    ? { kind: "holiday", label: "正式放假", marker: "休" }
    : { kind: "makeup_workday", label: "调休补班", marker: "班" };
  if (!published.includes(Number(day.slice(0, 4)))) return { kind: "unknown", label: "安排未收录", marker: "" };
  const weekend = [0, 6].includes(new Date(`${day}T12:00:00Z`).getUTCDay());
  return { kind: weekend ? "weekend" : "workday", label: weekend ? "周末" : "工作日", marker: "" };
}

const months = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"];
const days = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十", "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十", "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"];

export function lunarLabel(row, full = false) {
  if (!row) return full ? "农历数据未收录" : "—";
  const [month, day, leap] = row;
  const monthName = `${leap ? "闰" : ""}${months[month - 1]}月`;
  return full ? `农历${monthName}${days[day - 1]}` : day === 1 ? monthName : days[day - 1];
}

export function timeLabel(stamp) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(stamp));
}
