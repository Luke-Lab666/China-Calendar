import { isoDate, addDays, shiftMonth, monthCells, eventsOnDay, filterEvents, holidayState, lunarLabel, timeLabel } from "./calendar.mjs";

const $ = selector => document.querySelector(selector);
const today = isoDate();
let data;
let selected = today;
let view = today;
let filter = "essential";
let chosenFeed = "essential";
let toastTimer;

const feedInfo = {
  essential: ["中国日历 · 精简版", "保留最常用的日子，把日历的留白还给你。", "精简版与完整版选一个即可，避免重复显示。"],
  supplement: ["苹果日历补充", "和苹果官方节假日日历搭配，补上精确交节和传统时令。", "已使用苹果官方节假日日历时选择；交节事件会与官方全天节气同时显示。"],
  calendar: ["中国日历 · 完整版", "假期、补班、传统节日、纪念日、节气和传统时令，一份收齐。", "完整版本已包含所有分项内容，无需重复订阅其他分项。"],
  holidays: ["法定节假日与调休", "只保留正式放假与调休补班安排，给工作和休息一个清楚的边界。", "只收录正式安排，尚未收录的年份不会预测放假。"],
  "solar-terms": ["二十四节气", "看看季节行至何处；交节时刻以北京时间精确到分钟。", "节气事件持续一分钟，没有强制通知。"],
  traditional: ["中国传统节日", "春节、元宵、端午、中秋，以及那些值得记得的传统日子。", "节日按农历日期标记，节日当天不一定属于正式放假。"],
  observances: ["传统节日与纪念日", "传统节日、官方纪念日和常见社会日期。", "纪念日和社会日期不代表正式放假。"],
  seasonal: ["传统时令", "三伏、数九，跟着节气读懂一年的时序。", "日期根据节气与干支规则自动计算；传统时令不是天气预报。"],
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function inRange(day) {
  const year = Number(day.slice(0, 4));
  return data && year >= data.range.start_year && year <= data.range.end_year;
}

function weekday(day) {
  return "星期" + "日一二三四五六"[new Date(`${day}T12:00:00Z`).getUTCDay()];
}

function dateText(day) {
  const [, month, dayNumber] = day.split("-").map(Number);
  return `${month}月${dayNumber}日`;
}

function toast(text) {
  clearTimeout(toastTimer);
  $("#toast").textContent = text;
  $("#toast").classList.add("visible");
  toastTimer = setTimeout(() => $("#toast").classList.remove("visible"), 3200);
}

function renderToday() {
  $("#today-month").textContent = `${today.slice(0, 4)} 年 ${Number(today.slice(5, 7))} 月`;
  $("#today-weekday").textContent = weekday(today);
  $("#today-number").textContent = Number(today.slice(8));
  $("#today-lunar").textContent = lunarLabel(data.lunar[today], true);
  const next = data.events.find(event => event.kind === "solar_term" && Date.parse(event.start) > Date.now());
  $("#next-term").textContent = next ? `${next.summary} · ${dateText(isoDate(new Date(next.start)))}` : "待下一季更新";
}

function renderMonth() {
  const [year, month] = view.split("-").map(Number);
  $("#month-heading").textContent = `${year} 年 ${month} 月`;
  $("#prev-month").disabled = !inRange(shiftMonth(view, -1));
  $("#next-month").disabled = !inRange(shiftMonth(view, 1));
  $("#go-today").disabled = !inRange(today);
  const visible = filterEvents(data.events, filter);
  const grid = $("#month-grid");
  grid.replaceChildren();
  for (const day of monthCells(view)) {
    const events = eventsOnDay(visible, day);
    const term = events.find(event => event.kind === "solar_term");
    const festival = events.find(event => event.kind === "traditional");
    const status = holidayState(day, data.events, data.holidays_published);
    const cell = node("button", "date-cell");
    cell.type = "button";
    cell.dataset.date = day;
    cell.tabIndex = day === selected ? 0 : -1;
    cell.disabled = !inRange(day);
    cell.setAttribute("aria-label", `${day} ${weekday(day)} ${lunarLabel(data.lunar[day], true)} ${status.label}${events.length ? "，" + events.map(e => e.summary).join("、") : ""}`);
    cell.setAttribute("aria-pressed", String(day === selected));
    if (day === today) { cell.classList.add("today"); cell.setAttribute("aria-current", "date"); }
    if (day === selected) cell.classList.add("selected");
    if (day.slice(0, 7) !== view.slice(0, 7)) cell.classList.add("adjacent");
    if (term) cell.classList.add("term");
    cell.append(node("span", "gregorian", Number(day.slice(8))));
    const label = term?.summary || festival?.summary.replace("传统 · ", "") || lunarLabel(data.lunar[day]);
    cell.append(node("span", "lunar-label", label));
    if (status.marker) cell.append(node("span", `day-marker ${status.kind === "holiday" ? "off" : "on"}`, status.marker));
    if (events.length) cell.append(node("span", "event-dot"));
    cell.addEventListener("click", () => selectDay(day));
    grid.append(cell);
  }
  grid.setAttribute("aria-busy", "false");
  const missing = [];
  for (let y = data.range.start_year; y <= data.range.end_year; y++) {
    if (!data.holidays_published.includes(y)) missing.push(y);
  }
  $("#coverage-note").textContent = `可浏览 ${data.range.start_year}—${data.range.end_year} 年${missing.length ? ` · ${missing.join("、")} 年放假调休安排尚未收录，未预测假期。` : "。"}`;
}

function renderDay() {
  const status = holidayState(selected, data.events, data.holidays_published);
  const events = eventsOnDay(filterEvents(data.events, filter), selected);
  $("#selected-date").textContent = `${selected.replaceAll("-", ".")} / ${weekday(selected)}`;
  $("#selected-title").textContent = dateText(selected);
  $("#selected-lunar").textContent = lunarLabel(data.lunar[selected], true);
  $("#selected-status").textContent = status.label;
  $("#selected-status").className = `day-status ${status.kind}`;
  const list = $("#day-events");
  list.replaceChildren();
  if (!events.length) {
    const empty = node("div", "empty-day");
    empty.append(node("span", "empty-symbol", "◌"), node("p", "", "留白，也是好日子。"), node("small", "", "所选日历当天没有额外事件。"));
    list.append(empty);
  }
  for (const event of events) {
    const article = node("article", "event-item");
    let when = event.all_day ? "全天" : `${timeLabel(event.start)} · 北京时间`;
    if (event.all_day && event.end > addDays(event.start, 1)) when += ` · ${dateText(event.start)}—${dateText(addDays(event.end, -1))}`;
    article.append(node("p", "event-time", when));
    const title = node("h4");
    if (event.url.startsWith("https://")) {
      const link = node("a", "", event.summary);
      link.href = event.url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.title = "查看来源：" + event.summary;
      title.append(link);
    } else title.textContent = event.summary;
    article.append(title);
    if (event.description) {
      const excerpt = event.description.length > 82 ? event.description.slice(0, 82) + "…" : event.description;
      article.append(node("p", "event-excerpt", excerpt));
    }
    list.append(article);
  }
  $("#day-note").textContent = status.kind === "unknown"
    ? "该年份的正式放假调休安排尚未收录，不能仅凭星期判断是否补班或放假。"
    : "工作日与周末依据已收录的放假调休安排判断；具体工作安排请以所在单位通知为准。";
}

function selectDay(day) {
  if (!inRange(day)) return;
  const hadGridFocus = $("#month-grid").contains(document.activeElement);
  selected = day; view = day;
  renderMonth(); renderDay();
  if (hadGridFocus) document.querySelector(`[data-date="${day}"]`)?.focus({ preventScroll: true });
}

function feedURL(id) {
  if (["localhost", "127.0.0.1", ""].includes(location.hostname)) {
    return `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/${id}.ics`;
  }
  return new URL(`./calendars/${id}.ics`, location.href).href;
}

function chooseFeed(id) {
  chosenFeed = id;
  const [title, description, tip] = feedInfo[id];
  $("#feed-title").textContent = title;
  $("#feed-description").textContent = description;
  $("#feed-tip").textContent = tip;
  const feed = data?.feeds.find(item => item.id === id);
  $("#feed-count").textContent = feed ? `${data.range.start_year}—${data.range.end_year} · ${feed.count} 个事件 · 无强制提醒` : "ICS 通用订阅 · 无强制提醒";
  const url = feedURL(id);
  $("#feed-url").value = url;
  $("#subscribe-link").href = url.replace(/^https?:/, "webcal:");
  for (const button of document.querySelectorAll("[data-feed]")) {
    button.classList.toggle("selected", button.dataset.feed === id);
    button.setAttribute("aria-pressed", String(button.dataset.feed === id));
  }
}

function renderMoreFeeds() {
  const list = $("#more-feeds");
  list.replaceChildren();
  for (const id of ["holidays", "solar-terms", "traditional", "observances", "seasonal"]) {
    const row = node("div", "more-feed");
    const title = node("span", "", feedInfo[id][0]);
    const feed = data?.feeds.find(item => item.id === id);
    title.append(node("small", "", feed ? `${feed.count} 个事件 · 独立订阅` : "ICS 独立订阅"));
    const button = node("button", "", "选择订阅 ↗");
    button.type = "button";
    button.setAttribute("aria-label", "选择订阅：" + feedInfo[id][0]);
    button.addEventListener("click", () => {
      chooseFeed(id);
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      $(".subscription-card").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "center" });
      $("#subscribe-link").focus({ preventScroll: true });
    });
    row.append(title, button); list.append(row);
  }
}

async function load() {
  $("#load-error").hidden = true;
  $("#month-grid").setAttribute("aria-busy", "true");
  try {
    const response = await fetch("./data.json");
    if (!response.ok) throw new Error("Calendar data unavailable");
    const payload = await response.json();
    if (payload.schema !== 1 || !Array.isArray(payload.events) || !payload.lunar || !payload.range) throw new Error("Unsupported data");
    data = payload;
    if (!inRange(selected)) selected = `${data.range.start_year}-01-01`;
    view = selected;
    renderToday(); renderMonth(); renderDay(); chooseFeed(chosenFeed); renderMoreFeeds();
    const generated = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(data.generated_at));
    $("#data-updated").textContent = `数据生成于 ${generated} · 北京时间`;
  } catch (error) {
    $("#load-error").hidden = false;
    $("#month-heading").textContent = "数据暂不可用";
    $("#month-grid").setAttribute("aria-busy", "false");
    $("#today-month").textContent = `${today.slice(0, 4)} 年 ${Number(today.slice(5, 7))} 月`;
    $("#today-weekday").textContent = weekday(today);
    $("#today-number").textContent = Number(today.slice(8));
    $("#today-lunar").textContent = "农历数据暂不可用";
    $("#next-term").textContent = "待数据恢复";
  }
}

$("#prev-month").addEventListener("click", () => selectDay(shiftMonth(view, -1)));
$("#next-month").addEventListener("click", () => selectDay(shiftMonth(view, 1)));
$("#go-today").addEventListener("click", () => selectDay(today));
$("#retry-load").addEventListener("click", load);
for (const button of document.querySelectorAll("[data-filter]")) {
  button.addEventListener("click", () => {
    if (!data) return;
    filter = button.dataset.filter;
    for (const tab of document.querySelectorAll("[data-filter]")) tab.setAttribute("aria-pressed", String(tab === button));
    renderMonth(); renderDay();
  });
}
for (const button of document.querySelectorAll("[data-feed]")) button.addEventListener("click", () => chooseFeed(button.dataset.feed));
$("#copy-url").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("#feed-url").value);
    toast("订阅地址已复制，粘贴到你的日历 App 即可。");
  } catch {
    $("#feed-url").focus(); $("#feed-url").select();
    toast("请复制已选中的地址，再粘贴到日历 App。");
  }
});
$("#month-grid").addEventListener("keydown", event => {
  const offset = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key];
  if (!offset || !data) return;
  event.preventDefault();
  const next = addDays(selected, offset);
  if (!inRange(next)) return;
  selectDay(next);
  document.querySelector(`[data-date="${next}"]`)?.focus();
});

chooseFeed(chosenFeed);
renderMoreFeeds();
load();
