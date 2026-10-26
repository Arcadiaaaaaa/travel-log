"use strict";
// 看板：根据已加载的行程在前端统计并绘图。依赖 app.js 中的 state、h、格式化函数等。

const RAIL_TYPES = ["normal_train", "emu", "hsr"];

// 看板分为总览、铁路、地铁、公交四个页签
const SECTIONS = {
  all: { label: "总览", types: TRANSPORTS.map((t) => t.key) },
  rail: { label: "铁路", types: RAIL_TYPES },
  metro: { label: "地铁", types: ["metro"] },
  bus: { label: "公交", types: ["bus"] },
};

const dash = {
  year: null,
  section: "all",
  city: "all",
  mixMetric: "count",
  trendMetric: "count",
  trendScale: "month",
  tabs: {}, // 各排行面板当前选中的页签
};

const SVG_NS = "http://www.w3.org/2000/svg";

const tripMinutes = (t) => minutesBetween(t.depart_at, t.arrive_at);

// scale 把原始值换算成坐标轴上的单位（分→元，分钟→小时）
const METRICS = {
  count: { label: "次数", unit: "次", of: () => 1, scale: (v) => v, fmt: (v) => `${v} 次`, int: true },
  spend: { label: "花费", unit: "元", of: (t) => t.price_cents, scale: (v) => v / 100, fmt: fmtPrice },
  time: { label: "时长", unit: "小时", of: tripMinutes, scale: (v) => v / 60, fmt: fmtHours },
  distance: { label: "里程", unit: "公里", of: (t) => t.distance_km || 0, scale: (v) => v, fmt: fmtKm },
};
const metricOptions = Object.fromEntries(Object.entries(METRICS).map(([k, m]) => [k, m.label]));

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const SEAT_ORDER = ["商务座", "一等座", "二等座", "一等卧", "二等卧", "软卧", "硬卧", "硬座", "无座"];
const UNSET = "未填写";

const endpoints = (t) => [t.from_place, t.to_place].filter(Boolean);
const route = (t) => (t.from_place && t.to_place ? [`${t.from_place} → ${t.to_place}`] : []);

// 地铁换乘站：第 2 段起的上车站（为空时取上一段的下车站）。换乘站不算目的地。
const transferStations = (t) =>
  t.legs.slice(1).map((leg, i) => leg.from_station || t.legs[i].to_station).filter(Boolean);

// 排行定义：keys 返回一条行程要计数的名称（可以有多个）
const RANKS = {
  place: { label: "地点", keys: endpoints, empty: "出发地或到达地" },
  route: { label: "路线", keys: route, empty: "出发地和到达地" },
  station: { label: "车站", keys: endpoints, empty: "出发站或到达站" },
  train: { label: "车次", keys: (t) => (t.train_no ? [t.train_no] : []), empty: "车次号" },
  model: { label: "车型", keys: (t) => (t.vehicle_model ? [t.vehicle_model] : []), empty: "车型" },
  stop: { label: "站点", keys: endpoints, empty: "上车站或下车站" },
  busLine: { label: "线路", keys: (t) => (t.train_no ? [t.train_no] : []), empty: "线路" },
};
const RANK_SETS = {
  all: ["place", "route"],
  rail: ["station", "route", "train", "model"],
  bus: ["stop", "route", "busLine", "model"],
};

function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value != null) el.setAttribute(key, value);
  }
  for (const child of children) el.append(child);
  return el;
}

const sum = (items, of) => items.reduce((acc, item) => acc + of(item), 0);

// 统计每个名称出现的次数，返回 Map(名称 → 次数)
function tally(items, keysOf) {
  const counts = new Map();
  for (const item of items) {
    for (const key of keysOf(item)) counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

// ---------- 入口 ----------

function renderDashboard() {
  const root = $("#dashboard");
  hideTip();
  const thisYear = String(new Date().getFullYear());
  const knownTrips = state.trips.filter((t) => Object.hasOwn(TMAP, t.transport));
  const years = [...new Set(knownTrips.map((t) => t.depart_at.slice(0, 4)))].sort().reverse();
  if (dash.year === null) dash.year = years.includes(thisYear) ? thisYear : "all";
  if (dash.year !== "all" && !years.includes(dash.year)) dash.year = "all";

  const section = SECTIONS[dash.section];
  // scoped：本页签（及地铁城市）范围内的全部年份；trips：再按年份筛选
  let scoped = knownTrips.filter((t) => section.types.includes(t.transport));
  let cityNav = null;
  if (dash.section === "metro") {
    const cities = byCount(tally(scoped, (t) => [t.network]));
    if (dash.city !== "all" && !cities.includes(dash.city)) dash.city = "all";
    if (cities.length > 1) cityNav = cityChips(cities);
    if (dash.city !== "all") scoped = scoped.filter((t) => t.network === dash.city);
  }
  const trips = dash.year === "all" ? scoped : scoped.filter((t) => t.depart_at.startsWith(dash.year));
  const width = Math.max(260, root.clientWidth - 28);

  const head = [yearChips(years), sectionTabs(), cityNav].filter(Boolean);
  if (!trips.length) {
    const what = dash.section === "all" ? "记录" : `${section.label}记录`;
    root.replaceChildren(...head, h("div", { class: "empty" }, `这段时间还没有${what}`));
    return;
  }
  root.replaceChildren(...head, ...PANELS[dash.section](trips, scoped, width).filter(Boolean));
}

const PANELS = {
  all: (trips, scoped, width) => [
    overview(trips, [
      [`${new Set(trips.map((t) => t.depart_at.slice(0, 10))).size}`, "出行天数"],
      [`${new Set(trips.flatMap(endpoints)).size}`, "到过的地点"],
    ]),
    mixPanel(trips, SECTIONS.all.types, "交通方式"),
    trendPanel(trips, scoped, width),
    rankPanel("all", "常去排行", trips),
    timePanel(trips, width),
    recordsPanel(trips, "all"),
  ],
  rail: (trips, scoped, width) => [
    overview(trips, [
      [fmtPrice(Math.round(sum(trips, (t) => t.price_cents) / trips.length)), "平均票价"],
      [`${new Set(trips.map((t) => t.train_no).filter(Boolean)).size}`, "坐过的车次"],
    ]),
    mixPanel(trips, RAIL_TYPES, "列车类型"),
    seatPanel(trips),
    trendPanel(trips, scoped, width),
    rankPanel("rail", "常去排行", trips),
    timePanel(trips, width),
    recordsPanel(trips, "rail"),
  ],
  metro: (trips, scoped, width) => [
    overview(trips, [
      [`${sum(trips, (t) => Math.max(0, t.legs.length - 1))} 次`, "换乘"],
      [`${new Set(trips.flatMap((t) => metroLines(t).map((l) => `${t.network}|${l}`))).size}`, "坐过的线路"],
    ]),
    dash.city === "all" ? citiesPanel(trips) : null,
    trendPanel(trips, scoped, width),
    metroStationsPanel(trips),
    metroLinesPanel(trips),
    timePanel(trips, width),
    recordsPanel(trips, "metro"),
  ],
  bus: (trips, scoped, width) => [
    overview(trips, [
      [fmtPrice(Math.round(sum(trips, (t) => t.price_cents) / trips.length)), "平均票价"],
      [`${new Set(trips.map((t) => t.train_no).filter(Boolean)).size}`, "坐过的线路"],
    ]),
    trendPanel(trips, scoped, width),
    rankPanel("bus", "常去排行", trips),
    timePanel(trips, width),
    recordsPanel(trips, "bus"),
  ],
};

// ---------- 通用组件 ----------

function chipRow(label, entries, current, onPick) {
  return h(
    "nav",
    { class: "filters", "aria-label": label },
    entries.map(([value, text]) =>
      h(
        "button",
        {
          type: "button",
          class: `filter${current === value ? " active" : ""}`,
          "aria-pressed": String(current === value),
          onclick: () => onPick(value),
        },
        text,
      ),
    ),
  );
}

function yearChips(years) {
  return chipRow("按年份筛选", [["all", "全部"], ...years.map((y) => [y, `${y}年`])], dash.year, (value) => {
    dash.year = value;
    renderDashboard();
  });
}

function cityChips(cities) {
  const entries = [["all", "全部城市"], ...cities.map((c) => [c, c || "未分类"])];
  const nav = chipRow("按城市筛选", entries, dash.city, (value) => {
    dash.city = value;
    renderDashboard();
  });
  nav.classList.add("sub");
  return nav;
}

function sectionTabs() {
  const tabs = segmented(
    Object.fromEntries(Object.entries(SECTIONS).map(([k, v]) => [k, v.label])),
    dash.section,
    (key) => {
      dash.section = key;
      renderDashboard();
      window.scrollTo(0, 0);
    },
  );
  tabs.classList.add("wide", "section-tabs");
  return tabs;
}

function panel(title, control, ...body) {
  return h("section", { class: "panel" }, h("div", { class: "panel-head" }, h("h2", {}, title), control), ...body);
}

function segmented(options, current, onChange) {
  return h(
    "div",
    { class: "seg-ctrl", role: "group" },
    Object.entries(options).map(([key, label]) =>
      h(
        "button",
        {
          type: "button",
          class: key === current ? "active" : null,
          "aria-pressed": String(key === current),
          onclick: () => onChange(key),
        },
        label,
      ),
    ),
  );
}

function wideSegmented(options, current, onChange) {
  const el = segmented(options, current, onChange);
  el.classList.add("wide");
  return el;
}

// 只有一个系列时不需要图例
function legend(keys) {
  if (keys.length < 2) return null;
  return h(
    "div",
    { class: "legend" },
    keys.map((k) => h("span", { class: "legend-item" }, h("i", { class: `dot t-${k}` }), TMAP[k].label)),
  );
}

// entries: [{ name, sub?, value }]，通常已按 value 从大到小排好（坐席按固定顺序）
function rankList(entries, fmt = (v) => `${v} 次`, limit = 8) {
  const top = entries.slice(0, limit);
  const max = Math.max(1, ...top.map((e) => e.value));
  return h(
    "ol",
    { class: "rank-list" },
    top.map((e, i) => {
      const bar = h("span", { class: "rank-bar" });
      bar.style.width = `${(e.value / max) * 100}%`;
      return h(
        "li",
        { class: "rank-row" },
        h("span", { class: "rank-no" }, i + 1),
        h("span", { class: "rank-name" }, e.name, e.sub && h("small", {}, e.sub)),
        h("span", { class: "rank-track" }, bar),
        h("span", { class: "rank-val" }, fmt(e.value)),
      );
    }),
  );
}

function toEntries(counts, subOf) {
  return [...counts]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN"))
    .map(([key, value]) => (subOf ? { ...subOf(key), value } : { name: key, value }));
}

const emptyNote = (text) => h("p", { class: "caption empty-small" }, text);

function tabbedPanel(id, title, tabs, renderTab) {
  if (!tabs[dash.tabs[id]]) dash.tabs[id] = Object.keys(tabs)[0];
  return panel(
    title,
    null,
    wideSegmented(tabs, dash.tabs[id], (key) => {
      dash.tabs[id] = key;
      renderDashboard();
    }),
    renderTab(dash.tabs[id]),
  );
}

// ---------- 总览卡片 ----------

function overview(trips, extra) {
  const tile = ([value, label]) => h("div", { class: "stat" }, h("strong", {}, value), h("span", {}, label));
  return h(
    "section",
    { class: "stats six", "aria-label": "总览" },
    [
      [`${trips.length}`, "出行次数"],
      [fmtMoneyShort(sum(trips, (t) => t.price_cents)), "花费"],
      [fmtHours(sum(trips, tripMinutes)), "乘车时长"],
      [fmtKmShort(sum(trips, (t) => t.distance_km || 0)).replace("公里", ""), "里程（公里）"],
      ...extra,
    ].map(tile),
  );
}

// ---------- 构成 ----------

function mixPanel(trips, types, title) {
  const metric = METRICS[dash.mixMetric];
  const rows = types.map((key) => ({ t: TMAP[key], value: sum(trips.filter((x) => x.transport === key), metric.of) }));
  const total = sum(rows, (r) => r.value);
  const pct = (v) => (total ? `${Math.round((v / total) * 1000) / 10}%` : "0%");

  const bar = h("div", { class: "stackbar" });
  for (const r of rows) {
    if (!r.value) continue;
    const seg = h("span", { class: `stack-seg t-${r.t.key}` });
    seg.style.flexGrow = String(r.value);
    bindTip(seg, seg, seg, () => [
      h("div", { class: "tip-title" }, r.t.label),
      h("div", { class: "tip-row" }, h("span", {}, metric.label), h("b", {}, metric.fmt(r.value))),
      h("div", { class: "tip-row" }, h("span", {}, "占比"), h("b", {}, pct(r.value))),
    ]);
    bar.append(seg);
  }
  if (!total) bar.append(h("span", { class: "stack-empty" }));

  const table = h(
    "div",
    { class: "mix-table", role: "table" },
    rows.map((r) =>
      h(
        "div",
        { class: `mix-row${r.value ? "" : " zero"}`, role: "row" },
        h("span", { class: "mix-name", role: "cell" }, h("i", { class: `dot t-${r.t.key}` }), r.t.label),
        h("span", { class: "mix-val", role: "cell" }, metric.fmt(r.value)),
        h("span", { class: "mix-pct", role: "cell" }, pct(r.value)),
      ),
    ),
  );

  return panel(
    title,
    null,
    wideSegmented(metricOptions, dash.mixMetric, (key) => {
      dash.mixMetric = key;
      renderDashboard();
    }),
    bar,
    table,
  );
}

function seatPanel(trips) {
  const counts = tally(trips, (t) => [t.seat || UNSET]);
  const order = [...SEAT_ORDER, UNSET];
  const entries = order.filter((seat) => counts.has(seat)).map((seat) => ({ name: seat, value: counts.get(seat) }));
  const total = trips.length;
  return panel(
    "坐席",
    null,
    rankList(entries, (v) => `${v} 次 · ${Math.round((v / total) * 100)}%`, order.length),
  );
}

function citiesPanel(trips) {
  const counts = tally(trips, (t) => [t.network || "未分类"]);
  if (counts.size < 2) return null;
  return panel("城市", null, rankList(toEntries(counts)));
}

// ---------- 柱状图 ----------

function bucketize(trips, keys, keyOf, metric) {
  const index = new Map(keys.map((k, i) => [k, i]));
  const buckets = keys.map((key) => ({ key, parts: {}, total: 0 }));
  for (const t of trips) {
    const i = index.get(keyOf(t));
    if (i === undefined) continue;
    const v = metric.of(t);
    buckets[i].parts[t.transport] = (buckets[i].parts[t.transport] || 0) + v;
    buckets[i].total += v;
  }
  return buckets;
}

function niceTicks(max, integer) {
  if (max <= 0) return [0, 1];
  const raw = max / 3;
  const mag = 10 ** Math.floor(Math.log10(raw));
  let step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((v) => v >= raw);
  if (integer) step = Math.max(1, Math.ceil(step));
  const ticks = [];
  for (let v = 0; v < max + step * 0.999; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

function fmtTick(v) {
  if (v >= 10000) return `${Number((v / 10000).toFixed(1))}万`;
  return String(Number(v.toFixed(1)));
}

function barPath(x, y, w, hgt, r) {
  if (r <= 0) return `M${x},${y}h${w}v${hgt}h${-w}Z`;
  return `M${x},${y + hgt}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + hgt}Z`;
}

// buckets: [{ label, title, parts: {transport: 原始值}, total }]
// 柱子太多放不下时，图表变宽并允许横向滚动（每格至少 minSlot 像素）
function barChart(buckets, metric, width, ariaLabel, minSlot = 0) {
  const H = 170;
  const padL = 34;
  const padR = 4;
  const padT = 10;
  const padB = 22;
  width = Math.max(width, padL + padR + buckets.length * minSlot);
  const plotW = width - padL - padR;
  const plotH = H - padT - padB;
  const ticks = niceTicks(Math.max(0, ...buckets.map((b) => metric.scale(b.total))), metric.int);
  const top = ticks[ticks.length - 1];
  const y = (v) => padT + plotH - (v / top) * plotH;

  const svg = s("svg", { viewBox: `0 0 ${width} ${H}`, width, height: H, class: "chart", role: "img", "aria-label": ariaLabel });
  for (const tick of ticks) {
    const ty = Math.round(y(tick)) + 0.5;
    svg.append(
      s("line", { x1: padL, x2: width - padR, y1: ty, y2: ty, class: tick === 0 ? "baseline" : "grid" }),
      s("text", { x: padL - 6, y: ty + 3.5, "text-anchor": "end", class: "tick-label" }, fmtTick(tick)),
    );
  }

  const slot = plotW / buckets.length;
  const barW = Math.max(3, Math.min(26, slot * 0.64));
  buckets.forEach((b, i) => {
    const cx = padL + slot * (i + 0.5);
    const col = s("g", { class: "col" });
    const hit = s("rect", { x: padL + slot * i, y: padT, width: slot, height: plotH + padB, class: "hit" });
    const bars = s("g", { class: "bars" });
    const present = TRANSPORTS.filter((t) => b.parts[t.key] > 0);
    let cum = 0;
    present.forEach((t, j) => {
      const yTop = y(metric.scale(cum + b.parts[t.key]));
      const yBottom = y(metric.scale(cum)) - (j > 0 ? 2 : 0); // 段与段之间留 2px 间隙
      cum += b.parts[t.key];
      const segH = yBottom - yTop;
      if (segH <= 0.5) return;
      const radius = j === present.length - 1 ? Math.min(4, barW / 2, segH) : 0;
      bars.append(s("path", { d: barPath(cx - barW / 2, yTop, barW, segH, radius), class: `seg t-${t.key}` }));
    });
    col.append(hit, bars);
    if (b.label) {
      col.append(s("text", { x: cx, y: H - 6, "text-anchor": "middle", class: "tick-label" }, b.label));
    }
    bindTip(hit, col, bars, () => tipContent(b.title, b.parts, metric));
    svg.append(col);
  });

  if (width <= Math.max(260, $("#dashboard").clientWidth - 28)) return svg;
  const wrap = h("div", { class: "chart-scroll" }, svg);
  requestAnimationFrame(() => (wrap.scrollLeft = wrap.scrollWidth)); // 默认显示最近的月份
  return wrap;
}

function tipContent(title, parts, metric) {
  const present = TRANSPORTS.filter((t) => parts[t.key] > 0);
  const rows = present.map((t) =>
    h("div", { class: "tip-row" }, h("i", { class: `dot t-${t.key}` }), h("span", {}, t.label), h("b", {}, metric.fmt(parts[t.key]))),
  );
  if (present.length > 1) {
    rows.push(h("div", { class: "tip-row total" }, h("span", {}, "合计"), h("b", {}, metric.fmt(sum(present, (t) => parts[t.key])))));
  }
  if (!present.length) rows.push(h("div", { class: "tip-row" }, h("span", {}, "没有记录")));
  return [h("div", { class: "tip-title" }, title), ...rows];
}

function presentTransports(trips) {
  const used = new Set(trips.map((t) => t.transport));
  return TRANSPORTS.filter((t) => used.has(t.key)).map((t) => t.key);
}

function monthKeysBetween(first, last) {
  const keys = [];
  let [y, m] = first.split("-").map(Number);
  const [ly, lm] = last.split("-").map(Number);
  while (y < ly || (y === ly && m <= lm)) {
    keys.push(`${y}-${pad(m)}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return keys;
}

function trendPanel(trips, scoped, width) {
  const metric = METRICS[dash.trendMetric];
  let buckets;
  let caption;
  let minSlot = 0;
  if (dash.trendScale === "year") {
    // 年视图总是对比全部年份
    const keys = [...new Set(scoped.map((t) => t.depart_at.slice(0, 4)))].sort();
    buckets = bucketize(scoped, keys, (t) => t.depart_at.slice(0, 4), metric).map((b) => ({
      ...b,
      label: b.key,
      title: `${b.key}年`,
    }));
    caption = "全部年份 · 按年";
  } else if (dash.year !== "all") {
    const keys = Array.from({ length: 12 }, (_, i) => `${dash.year}-${pad(i + 1)}`);
    const roomy = (width - 38) / 12 >= 30; // 窄屏放不下“12月”，只写数字
    buckets = bucketize(trips, keys, (t) => t.depart_at.slice(0, 7), metric).map((b) => {
      const m = Number(b.key.slice(5));
      return { ...b, label: roomy ? `${m}月` : String(m), title: `${dash.year}年${m}月` };
    });
    caption = `${dash.year}年 · 按月`;
  } else {
    const months = trips.map((t) => t.depart_at.slice(0, 7)).sort();
    const keys = monthKeysBetween(months[0], months[months.length - 1]);
    buckets = bucketize(trips, keys, (t) => t.depart_at.slice(0, 7), metric).map((b) => {
      const [y, m] = b.key.split("-").map(Number);
      let label = "";
      if (keys.length <= 12) label = String(m);
      else if (m === 1 || b.key === keys[0]) label = m === 1 ? `${y}年` : `${String(y).slice(2)}.${m}`;
      else if (m === 7) label = "7月";
      return { ...b, label, title: `${y}年${m}月` };
    });
    caption = "全部 · 按月";
    minSlot = 16;
  }
  return panel(
    "出行趋势",
    segmented({ month: "月", year: "年" }, dash.trendScale, (key) => {
      dash.trendScale = key;
      renderDashboard();
    }),
    wideSegmented(metricOptions, dash.trendMetric, (key) => {
      dash.trendMetric = key;
      renderDashboard();
    }),
    h("p", { class: "caption" }, `${caption}，单位：${metric.unit}`),
    barChart(buckets, metric, width, `出行趋势，${caption}`, minSlot),
    legend(presentTransports(dash.trendScale === "year" ? scoped : trips)),
  );
}

function timePanel(trips, width) {
  const metric = METRICS.count;
  const hours = bucketize(trips, Array.from({ length: 24 }, (_, i) => i), (t) => Number(t.depart_at.slice(11, 13)), metric).map(
    (b) => ({ ...b, label: b.key % 6 === 0 ? `${b.key}时` : "", title: `${b.key}:00–${b.key}:59 出发` }),
  );
  const weekdays = bucketize(trips, [0, 1, 2, 3, 4, 5, 6], (t) => (parseLocal(t.depart_at).getDay() + 6) % 7, metric).map(
    (b) => ({ ...b, label: WEEKDAYS[b.key], title: `星期${WEEKDAYS[b.key]}` }),
  );
  return panel(
    "出发时间",
    null,
    h("p", { class: "caption" }, "按出发的钟点，单位：次"),
    barChart(hours, metric, width, "按出发钟点统计的出行次数"),
    h("p", { class: "caption" }, "按星期，单位：次"),
    barChart(weekdays, metric, width, "按星期统计的出行次数"),
    legend(presentTransports(trips)),
  );
}

// ---------- 排行 ----------

function rankPanel(setKey, title, trips) {
  const tabs = Object.fromEntries(RANK_SETS[setKey].map((k) => [k, RANKS[k].label]));
  return tabbedPanel(setKey, title, tabs, (key) => {
    const rank = RANKS[key];
    const entries = toEntries(tally(trips, rank.keys));
    return entries.length ? rankList(entries) : emptyNote(`还没有填写${rank.empty}的记录`);
  });
}

// 地铁站点：全部城市时为总排行（标注城市），选定城市时为该城市排行
function metroStationsPanel(trips) {
  const allCities = dash.city === "all";
  const keyed = (keysOf) => (t) => keysOf(t).map((station) => (allCities ? `${t.network}\u0000${station}` : station));
  const subOf = (key) => {
    if (!allCities) return { name: key };
    const [network, station] = key.split("\u0000");
    return { name: station, sub: network || "未分类" };
  };
  return tabbedPanel(
    "metroStations",
    allCities ? "站点排行 · 全部城市" : `站点排行 · ${dash.city || "未分类"}`,
    { endpoints: "常去站点", transfer: "换乘站" },
    (key) => {
      const counts = tally(trips, keyed(key === "transfer" ? transferStations : endpoints));
      if (!counts.size) return emptyNote(key === "transfer" ? "还没有换乘记录" : "还没有填写上下车站的记录");
      return rankList(toEntries(counts, subOf));
    },
  );
}

// 地铁线路、车型：每个城市分别排行
function metroLinesPanel(trips) {
  return tabbedPanel("metroLines", "线路与车型", { line: "线路", model: "车型" }, (key) => {
    const byCity = new Map();
    for (const t of trips) {
      if (!byCity.has(t.network)) byCity.set(t.network, []);
      byCity.get(t.network).push(t);
    }
    const cities = byCount(new Map([...byCity].map(([c, list]) => [c, list.length])));
    const groups = cities
      .map((city) => {
        const counts = tally(byCity.get(city), (t) =>
          t.legs.map((leg) => (key === "line" ? leg.line : leg.vehicle_model)).filter(Boolean),
        );
        if (!counts.size) return null;
        const title = cities.length > 1 ? h("h3", { class: "rank-group-title" }, city || "未分类") : null;
        return h("div", { class: "rank-group" }, title, rankList(toEntries(counts), (v) => `${v} 段`));
      })
      .filter(Boolean);
    return groups.length ? h("div", {}, groups) : emptyNote(key === "line" ? "还没有填写线路的记录" : "还没有填写车型的记录");
  });
}

// ---------- 记录之最 ----------

function tripSummary(t) {
  const way = t.from_place || t.to_place ? `${t.from_place || "—"} → ${t.to_place || "—"}` : "";
  return [t.depart_at.slice(0, 10), tripMeta(t) || TMAP[t.transport].label, way].filter(Boolean).join(" · ");
}

function pick(trips, score) {
  return trips.reduce((best, t) => (score(t) > score(best) ? t : best));
}

function recordsPanel(trips, section) {
  const clock = (t) => Number(t.depart_at.slice(11, 13)) * 60 + Number(t.depart_at.slice(14, 16));
  const transfers = (t) => (t.transport === "metro" ? t.legs.length - 1 : 0);
  const longest = pick(trips, tripMinutes);
  const farthest = pick(trips, (t) => t.distance_km || 0);
  const priciest = pick(trips, (t) => t.price_cents);
  const earliest = pick(trips, (t) => -clock(t));
  const latest = pick(trips, clock);
  const mostTransfers = pick(trips, transfers);

  const perDay = tally(trips, (t) => [t.depart_at.slice(0, 10)]);
  const [busyDay, busyCount] = [...perDay].reduce((best, cur) => (cur[1] > best[1] ? cur : best));

  const row = (label, value, trip, sub) =>
    h(
      trip ? "button" : "div",
      { class: "record", type: trip ? "button" : null, onclick: trip ? () => openEditor(trip) : null },
      h("span", { class: "record-label" }, label),
      h("span", { class: "record-value" }, value),
      h("span", { class: "record-sub" }, sub),
    );

  return panel(
    "记录之最",
    null,
    h(
      "div",
      { class: "records" },
      row("最久的一程", fmtDuration(tripMinutes(longest)), longest, tripSummary(longest)),
      farthest.distance_km > 0 && row("最远的一程", fmtKm(farthest.distance_km), farthest, tripSummary(farthest)),
      row("最贵的一程", fmtPrice(priciest.price_cents), priciest, tripSummary(priciest)),
      row("最早出发", fmtClock(earliest.depart_at), earliest, tripSummary(earliest)),
      row("最晚出发", fmtClock(latest.depart_at), latest, tripSummary(latest)),
      busyCount > 1 && row("最忙的一天", `${busyCount} 段`, null, busyDay),
      section !== "rail" && section !== "bus" && transfers(mostTransfers) > 0 &&
        row("换乘最多", `${transfers(mostTransfers)} 次`, mostTransfers, tripSummary(mostTransfers)),
    ),
  );
}

// ---------- 提示框 ----------

function bindTip(target, group, anchor, content) {
  const show = () => {
    for (const el of document.querySelectorAll(".tip-active")) el.classList.remove("tip-active");
    group.classList.add("tip-active");
    const box = anchor.getBoundingClientRect();
    showTip(box.height > 0 ? box : target.getBoundingClientRect(), content());
  };
  target.addEventListener("pointerenter", (e) => e.pointerType === "mouse" && show());
  target.addEventListener("pointerleave", (e) => e.pointerType === "mouse" && hideTip());
  target.addEventListener("click", show);
}

function showTip(box, content) {
  const tip = $("#chart-tip");
  tip.replaceChildren(...content);
  tip.hidden = false;
  const left = Math.min(Math.max(8, box.left + box.width / 2 - tip.offsetWidth / 2), innerWidth - tip.offsetWidth - 8);
  let top = box.top - tip.offsetHeight - 8;
  if (top < 8) top = box.bottom + 8;
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}

function hideTip() {
  const tip = document.getElementById("chart-tip");
  if (tip) tip.hidden = true;
  for (const el of document.querySelectorAll(".tip-active")) el.classList.remove("tip-active");
}

document.addEventListener("pointerdown", (e) => {
  if (!e.target.closest(".hit, .stack-seg")) hideTip();
});
window.addEventListener("scroll", hideTip, { passive: true });

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (state.view === "dash") renderDashboard();
  }, 150);
});
