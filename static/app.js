"use strict";

const TRANSPORTS = [
  { key: "normal_train", label: "普快火车", short: "普快" },
  { key: "emu", label: "动车组", short: "动车" },
  { key: "hsr", label: "高速动车组", short: "高铁" },
  { key: "bus", label: "公交车", short: "公交" },
  { key: "metro", label: "地铁", short: "地铁" },
];
const TMAP = Object.fromEntries(TRANSPORTS.map((t) => [t.key, t]));
const TRAIN_TYPES = new Set(["normal_train", "emu", "hsr"]);

// 不同交通方式下“车次号/型号”的提示
const HINTS = {
  normal_train: { noLabel: "车次号", no: "如 K1234", model: "如 25G" },
  emu: { noLabel: "车次号", no: "如 D301", model: "如 CRH2A" },
  hsr: { noLabel: "车次号", no: "如 G1", model: "如 CR400AF" },
  bus: { noLabel: "线路", no: "如 18路", model: "如 宇通 E12" },
  metro: { noLabel: "线路", no: "如 2号线", model: "如 A型车" },
};

const state = { trips: [], filter: "all", network: "all", editing: null, saving: false, view: "records" };

// 常见地铁车型：数字为编组节数，字母为车辆类型
const MODEL_PRESETS = ["3B", "4B", "6B", "8B", "4A", "6A", "8A", "6As", "8As", "4L", "6L"];

// 坐席选项（与后端 SEAT_OPTIONS 一致）；公交、地铁不分坐席
const EMU_SEATS = ["二等座", "一等座", "商务座", "二等卧", "一等卧", "无座"];
const SEAT_OPTIONS = {
  normal_train: ["硬座", "硬卧", "软卧", "无座"],
  emu: EMU_SEATS,
  hsr: EMU_SEATS,
};

const $ = (sel) => document.querySelector(sel);

function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false || child === "") continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

// ---------- 接口 ----------

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function api(method, path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  const opts = { method, headers: { ...Platform.authHeaders() }, credentials: Platform.isNative ? "omit" : "same-origin", signal: controller.signal };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  let data = null;
  try {
    res = await fetch(Platform.apiBase() + path, opts);
    try {
      data = await res.json();
    } catch (err) {
      if (err.name !== "SyntaxError") throw err;
    }
  } catch {
    throw new ApiError(controller.signal.aborted ? "连接超时，请检查网络" : "网络连接失败，请检查网络", 0);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && path !== "/api/login") {
    await Platform.onUnauthorized();
    showLogin();
    throw new ApiError("登录已过期，请重新登录", 401);
  }
  if (!res.ok) throw new ApiError((data && data.error) || `请求失败（${res.status}）`, res.status);
  return data;
}

// ---------- 格式化 ----------

const pad = (n) => String(n).padStart(2, "0");

function parseLocal(s) {
  const [date, time] = s.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm);
}

function toLocalInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function nowRounded() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - (d.getMinutes() % 5), 0, 0);
  return toLocalInput(d);
}

const minutesBetween = (a, b) => Math.round((parseLocal(b) - parseLocal(a)) / 60000);

function fmtDuration(min) {
  if (min < 60) return `${min}分钟`;
  const days = Math.floor(min / 1440);
  const hours = Math.floor((min % 1440) / 60);
  const mins = min % 60;
  if (days) return `${days}天${hours ? hours + "小时" : ""}`;
  return `${hours}小时${mins ? mins + "分" : ""}`;
}

function fmtHours(min) {
  if (min < 60) return `${min}分钟`;
  const hours = min / 60;
  return `${hours >= 100 ? Math.round(hours) : Math.round(hours * 10) / 10}小时`;
}

function fmtPrice(cents) {
  const whole = cents % 100 === 0;
  return "¥" + (cents / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

// 统计卡片空间小：千元以上取整，十万以上用“万”
function fmtMoneyShort(cents) {
  const yuan = cents / 100;
  if (yuan >= 100000) return `¥${Math.round(yuan / 1000) / 10}万`;
  if (yuan >= 1000) return `¥${Math.round(yuan).toLocaleString("zh-CN")}`;
  return fmtPrice(cents);
}

function fmtKm(km) {
  return `${Number(km.toFixed(1)).toLocaleString("zh-CN")}公里`;
}

function fmtKmShort(km) {
  if (km >= 100000) return `${Math.round(km / 1000) / 10}万公里`;
  return `${Math.round(km).toLocaleString("zh-CN")}公里`;
}

function centsToInput(cents) {
  return cents % 100 === 0 ? String(cents / 100) : (cents / 100).toFixed(2);
}

const fmtClock = (s) => s.slice(11, 16);

function fmtDepart(s) {
  const d = parseLocal(s);
  return `${d.getMonth() + 1}月${d.getDate()}日 ${fmtClock(s)}`;
}

function fmtArrive(depart, arrive) {
  const dayDiff = Math.round(
    (parseLocal(arrive.slice(0, 10) + "T00:00") - parseLocal(depart.slice(0, 10) + "T00:00")) / 86400000,
  );
  if (dayDiff === 0) return fmtClock(arrive);
  if (dayDiff === 1) return `次日 ${fmtClock(arrive)}`;
  return `+${dayDiff}天 ${fmtClock(arrive)}`;
}

function fmtMonth(key) {
  const [y, m] = key.split("-");
  return `${y}年${Number(m)}月`;
}

// ---------- 渲染 ----------

function visibleTrips() {
  if (state.filter === "all") return state.trips;
  const trips = state.trips.filter((t) => t.transport === state.filter);
  if (state.filter !== "metro" || state.network === "all") return trips;
  return trips.filter((t) => t.network === state.network);
}

const metroLines = (t) => t.legs.map((leg) => leg.line).filter(Boolean);

// 卡片标题：地铁显示“北京地铁 · 2号线 → 10号线”，其他显示车次和型号
function tripMeta(t) {
  if (t.transport === "metro") return [t.network, metroLines(t).join(" → ")].filter(Boolean).join(" · ");
  return [t.train_no, t.vehicle_model, t.seat].filter(Boolean).join(" · ");
}

function render() {
  const trips = visibleTrips();
  renderStats(trips);
  renderFilters();
  renderList(trips);
  if (state.view === "dash") renderDashboard();
}

function setView(view) {
  state.view = view;
  $("#records").hidden = view !== "records";
  $("#add-btn").hidden = view !== "records";
  $("#dashboard").hidden = view !== "dash";
  $("#view-title").textContent = view === "dash" ? "看板" : "旅行记录";
  for (const btn of document.querySelectorAll(".tabbar button")) {
    const active = btn.dataset.view === view;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-current", active ? "page" : "false");
  }
  if (view === "dash") renderDashboard();
  else hideTip();
  window.scrollTo(0, 0);
}

for (const btn of document.querySelectorAll(".tabbar button")) {
  btn.addEventListener("click", () => setView(btn.dataset.view));
}

function renderStats(trips) {
  const spend = trips.reduce((sum, t) => sum + t.price_cents, 0);
  const minutes = trips.reduce((sum, t) => sum + minutesBetween(t.depart_at, t.arrive_at), 0);
  const tile = (value, label) => h("div", { class: "stat" }, h("strong", {}, value), h("span", {}, label));
  $("#stats").replaceChildren(
    tile(`${trips.length}`, "行程"),
    tile(fmtMoneyShort(spend), "花费"),
    tile(fmtHours(minutes), "乘车时长"),
  );
}

function renderFilters() {
  const counts = {};
  for (const t of state.trips) counts[t.transport] = (counts[t.transport] || 0) + 1;
  const chip = (key, label, count) =>
    h(
      "button",
      {
        type: "button",
        class: `filter${state.filter === key ? " active" : ""}`,
        "aria-pressed": String(state.filter === key),
        onclick: () => {
          state.filter = key;
          state.network = "all";
          render();
        },
      },
      label,
      h("span", { class: "count" }, count),
    );
  $("#filters").replaceChildren(
    chip("all", "全部", state.trips.length),
    ...TRANSPORTS.map((t) => chip(t.key, t.label, counts[t.key] || 0)),
  );
  const active = $("#filters .active");
  if (active) $("#filters").scrollLeft = active.offsetLeft - 16;
  renderNetworkFilters();
}

function renderNetworkFilters() {
  const nav = $("#network-filters");
  const metro = state.trips.filter((t) => t.transport === "metro");
  const counts = new Map();
  for (const t of metro) counts.set(t.network, (counts.get(t.network) || 0) + 1);
  nav.hidden = state.filter !== "metro" || counts.size === 0;
  if (nav.hidden) return;
  const chip = (key, label, count) =>
    h(
      "button",
      {
        type: "button",
        class: `filter${state.network === key ? " active" : ""}`,
        "aria-pressed": String(state.network === key),
        onclick: () => {
          state.network = key;
          render();
        },
      },
      label,
      h("span", { class: "count" }, count),
    );
  nav.replaceChildren(
    chip("all", "全部城市", metro.length),
    ...byCount(counts).map((name) => chip(name, name || "未分类", counts.get(name))),
  );
}

// Map(名称 → 次数) 按次数从多到少排序后返回名称
function byCount(counts) {
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN")).map(([name]) => name);
}

function renderList(trips) {
  const list = $("#list");
  if (!trips.length) {
    list.replaceChildren(
      h(
        "div",
        { class: "empty" },
        state.trips.length ? "这个分类下还没有记录" : "还没有记录，点右下角的 + 记下第一段旅程",
      ),
    );
    return;
  }
  const groups = new Map();
  for (const t of trips) {
    const key = t.depart_at.slice(0, 7);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(t);
  }
  const sections = [];
  for (const [key, items] of groups) {
    const spend = items.reduce((sum, t) => sum + t.price_cents, 0);
    sections.push(
      h(
        "section",
        { class: "month" },
        h(
          "div",
          { class: "month-head" },
          h("h2", {}, fmtMonth(key)),
          h("span", {}, `${items.length} 次 · ${fmtPrice(spend)}`),
        ),
        h("div", { class: "cards" }, items.map(tripCard)),
      ),
    );
  }
  list.replaceChildren(...sections);
}

function tripCard(t) {
  const known = Object.hasOwn(TMAP, t.transport);
  const meta = tripMeta(t);
  const transfers = t.transport === "metro" ? t.legs.length - 1 : 0;
  const hasRoute = t.from_place || t.to_place;
  return h(
    "button",
    { type: "button", class: "trip", onclick: () => openEditor(t) },
    h(
      "div",
      { class: "trip-top" },
      h("span", { class: `badge t-${known ? t.transport : "unknown"}` }, known ? TMAP[t.transport].short : t.transport),
      meta && h("span", { class: "meta" }, meta),
      h("span", { class: "price" }, fmtPrice(t.price_cents)),
    ),
    hasRoute && h("div", { class: "route" }, `${t.from_place || "—"} → ${t.to_place || "—"}`),
    h(
      "div",
      { class: "times" },
      `${fmtDepart(t.depart_at)} → ${fmtArrive(t.depart_at, t.arrive_at)}`,
      h("span", { class: "dur" }, ` · ${fmtDuration(minutesBetween(t.depart_at, t.arrive_at))}`),
      transfers > 0 && h("span", { class: "dur" }, ` · 换乘 ${transfers} 次`),
      t.distance_km > 0 && h("span", { class: "dur" }, ` · ${fmtKm(t.distance_km)}`),
    ),
    t.note && h("div", { class: "note" }, t.note),
  );
}

// ---------- 编辑 ----------

const tripDialog = $("#trip-dialog");
const tripForm = $("#trip-form");

function buildTransportOptions() {
  $("#transport-options").replaceChildren(
    ...TRANSPORTS.map((t) =>
      h(
        "label",
        { class: `chip t-${t.key}` },
        h("input", { type: "radio", name: "transport", value: t.key, onchange: applyHints }),
        h("span", {}, t.label),
      ),
    ),
  );
}

function applyHints() {
  const transport = tripForm.elements.transport.value;
  const isMetro = transport === "metro";
  $("#general-fields").hidden = isMetro;
  $("#metro-fields").hidden = !isMetro;
  buildSeatOptions(transport, currentSeat());
  const hint = HINTS[tripForm.elements.transport.value] || HINTS.hsr;
  $("#train-no-label").textContent = hint.noLabel;
  tripForm.elements.train_no.placeholder = hint.no;
  tripForm.elements.vehicle_model.placeholder = hint.model;
}

// ---------- 坐席 ----------

let selectedSeat = "";

function currentSeat() {
  const checked = tripForm.querySelector('input[name="seat"]:checked');
  return checked ? checked.value : "";
}

// 切换交通方式时重建选项；新选项里仍有原坐席（如动车↔高铁）就保留
function buildSeatOptions(transport, keep) {
  const options = [...(SEAT_OPTIONS[transport] || [])];
  if (state.editing && transport === state.editing.transport && TRAIN_TYPES.has(transport) &&
      keep === state.editing.seat && keep && !options.includes(keep)) options.push(keep);
  $("#seat-field").hidden = !options.length;
  selectedSeat = options.includes(keep) ? keep : "";
  $("#seat-options").replaceChildren(
    ...options.map((seat) => {
      const input = h("input", { type: "radio", name: "seat", value: seat });
      input.checked = seat === selectedSeat;
      // 单选框默认不能取消，这里允许再点一次取消选择
      input.addEventListener("click", () => {
        if (selectedSeat === seat) {
          input.checked = false;
          selectedSeat = "";
        } else {
          selectedSeat = seat;
        }
      });
      return h("label", { class: "chip seat-chip" }, input, h("span", {}, seat));
    }),
  );
}

function lastTransport() {
  const value = recall("lastTransport");
  return value && TMAP[value] ? value : "hsr";
}

function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* 忽略 */
  }
}

function recall(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

// ---------- 地铁：线网、换乘区段 ----------

const NEW_OPTION = "__new__";

// 下拉选择 + “新增…”：选中“新增”时出现输入框，保存后新值会出现在以后的下拉选项里
function comboPicker({ placeholder, newLabel, newPlaceholder, maxlength, onChange }) {
  const select = h("select", {});
  const input = h("input", { type: "text", maxlength, placeholder: newPlaceholder, autocomplete: "off", hidden: true });
  let options = [];
  const fill = (value) => {
    const list = value && !options.includes(value) ? [value, ...options] : options;
    select.replaceChildren(
      h("option", { value: "" }, placeholder),
      ...list.map((o) => h("option", { value: o }, o)),
      h("option", { value: NEW_OPTION }, newLabel),
    );
  };
  const picker = {
    el: h("div", { class: "combo" }, select, input),
    get value() {
      return select.value === NEW_OPTION ? input.value.trim() : select.value;
    },
    set value(v) {
      fill(v || "");
      select.value = v || "";
      input.hidden = true;
      input.value = "";
    },
    setOptions(list) {
      const current = picker.value;
      options = list;
      picker.value = current;
    },
  };
  select.addEventListener("change", () => {
    input.hidden = select.value !== NEW_OPTION;
    if (!input.hidden) input.focus();
    if (onChange) onChange(picker.value);
  });
  input.addEventListener("change", () => onChange && onChange(picker.value));
  return picker;
}

// 从已有记录里整理出地铁系统、线路、车站，以及每条线路最近一次用的车型
function metroHistory() {
  const networks = new Map();
  const lines = new Map();
  const stations = new Map();
  const lineModel = new Map();
  const models = new Set();
  for (const t of state.trips) {
    if (t.transport !== "metro" || !t.network) continue;
    networks.set(t.network, (networks.get(t.network) || 0) + 1);
    if (!lines.has(t.network)) lines.set(t.network, new Map());
    if (!stations.has(t.network)) stations.set(t.network, new Set());
    for (const leg of t.legs) {
      if (leg.line) {
        const counts = lines.get(t.network);
        counts.set(leg.line, (counts.get(leg.line) || 0) + 1);
        const key = `${t.network}\u0000${leg.line}`;
        // state.trips 按时间倒序，第一次遇到的就是最近一次
        if (leg.vehicle_model && !lineModel.has(key)) lineModel.set(key, leg.vehicle_model);
      }
      if (leg.vehicle_model) models.add(leg.vehicle_model);
      for (const s of [leg.from_station, leg.to_station]) if (s) stations.get(t.network).add(s);
    }
  }
  const extraModels = [...models].filter((m) => !MODEL_PRESETS.includes(m)).sort();
  return { networks: byCount(networks), lines, stations, lineModel, models: [...MODEL_PRESETS, ...extraModels] };
}

const metro = { hist: null, network: null, legs: [] };

const currentNetwork = () => (metro.network ? metro.network.value : "");

function linesFor(network) {
  return metro.hist.lines.has(network) ? byCount(metro.hist.lines.get(network)) : [];
}

function refreshNetworkOptions() {
  for (const leg of metro.legs) leg.line.setOptions(linesFor(currentNetwork()));
  const stations = metro.hist.stations.get(currentNetwork()) || new Set();
  $("#station-options").replaceChildren(...[...stations].sort().map((s) => h("option", { value: s })));
}

function buildMetroFields(trip) {
  metro.hist = metroHistory();
  if (!metro.network) {
    metro.network = comboPicker({
      placeholder: "请选择",
      newLabel: "+ 新增地铁系统…",
      newPlaceholder: "如 北京地铁",
      maxlength: 30,
      onChange: refreshNetworkOptions,
    });
    $("#network-picker").replaceChildren(metro.network.el);
  }
  metro.network.setOptions(metro.hist.networks);
  const last = recall("lastNetwork");
  metro.network.value = trip && trip.transport === "metro" ? trip.network : last || metro.hist.networks[0] || "";
  metro.legs = [];
  $("#legs").replaceChildren();
  const legs = trip && trip.legs && trip.legs.length ? trip.legs : [{}];
  legs.forEach((leg, i) => {
    const linked = i > 0 && leg.from_station === legs[i - 1].to_station;
    addLeg({ ...leg, fromAuto: linked });
  });
  refreshNetworkOptions();
}

function addLeg(data = {}) {
  const leg = {};
  leg.line = comboPicker({
    placeholder: "请选择",
    newLabel: "+ 新增线路…",
    newPlaceholder: "如 2号线",
    maxlength: 20,
    onChange: (line) => {
      // 线路通常固定车型，选过一次后自动带出
      const model = metro.hist.lineModel.get(`${currentNetwork()}\u0000${line}`);
      if (model) leg.model.value = model;
    },
  });
  leg.model = comboPicker({ placeholder: "不填", newLabel: "+ 其他车型…", newPlaceholder: "如 6B", maxlength: 20 });
  leg.from = h("input", { maxlength: 50, list: "station-options", placeholder: "可留空", autocomplete: "off" });
  leg.to = h("input", { maxlength: 50, list: "station-options", placeholder: "可留空", autocomplete: "off" });
  leg.fromLabel = h("span", {}, "上车站");
  leg.title = h("span", { class: "leg-title" });
  // fromAuto：上车站是否跟随上一段的下车站（换乘站）；手动改过就不再跟随
  leg.fromAuto = Boolean(data.fromAuto);
  leg.from.addEventListener("input", () => {
    leg.fromAuto = false;
  });
  leg.to.addEventListener("input", syncTransferStations);
  leg.remove = h("button", { type: "button", class: "link leg-remove", onclick: () => removeLeg(leg) }, "删除");
  const field = (label, control) => h("div", { class: "field" }, h("span", {}, label), control);
  leg.el = h(
    "div",
    { class: "leg" },
    h("div", { class: "leg-head" }, leg.title, leg.remove),
    h("div", { class: "row2" }, field("线路", leg.line.el), field("车型", leg.model.el)),
    h("div", { class: "row2" }, h("div", { class: "field" }, leg.fromLabel, leg.from), field("下车站", leg.to)),
  );
  leg.line.setOptions(linesFor(currentNetwork()));
  leg.line.value = data.line || "";
  leg.model.setOptions(metro.hist.models);
  leg.model.value = data.vehicle_model || "";
  leg.from.value = data.from_station || "";
  leg.to.value = data.to_station || "";
  metro.legs.push(leg);
  $("#legs").append(leg.el);
  renumberLegs();
  return leg;
}

function removeLeg(leg) {
  metro.legs = metro.legs.filter((l) => l !== leg);
  leg.el.remove();
  if (metro.legs[0]) metro.legs[0].fromAuto = false;
  syncTransferStations();
}

// 上一段的下车站就是下一段的换乘站，自动填为下一段的上车站
function syncTransferStations() {
  metro.legs.forEach((leg, i) => {
    if (i > 0 && leg.fromAuto) leg.from.value = metro.legs[i - 1].to.value.trim();
  });
  renumberLegs();
}

function renumberLegs() {
  metro.legs.forEach((leg, i) => {
    const transfer = i > 0 && metro.legs[i - 1].to.value.trim();
    leg.title.textContent = i === 0 ? "第 1 段" : `第 ${i + 1} 段 · ${transfer ? `在${transfer}换乘` : "换乘"}`;
    leg.fromLabel.textContent = i === 0 ? "上车站" : "换乘站（上车）";
    leg.remove.hidden = metro.legs.length === 1;
  });
}

$("#add-leg-btn").addEventListener("click", () => {
  const prev = metro.legs[metro.legs.length - 1];
  const leg = addLeg({ from_station: prev ? prev.to.value.trim() : "", fromAuto: true });
  leg.line.el.querySelector("select").focus();
});

$("#legs").addEventListener("change", renumberLegs);

function readLegs() {
  return metro.legs.map((leg) => ({
    line: leg.line.value,
    vehicle_model: leg.model.value,
    from_station: leg.from.value.trim(),
    to_station: leg.to.value.trim(),
  }));
}

function openEditor(trip) {
  if (trip && !Object.hasOwn(TMAP, trip.transport)) {
    toast("这条记录需要新版 App 才能编辑");
    return;
  }
  state.editing = trip || null;
  tripForm.reset();
  $("#trip-error").textContent = "";
  $("#trip-dialog-title").textContent = trip ? "编辑行程" : "新增行程";
  $("#delete-btn").hidden = !trip;
  const f = tripForm.elements;
  if (trip) {
    f.transport.value = trip.transport;
    for (const key of ["from_place", "to_place", "depart_at", "arrive_at", "train_no", "vehicle_model", "note"]) {
      f[key].value = trip[key];
    }
    f.price.value = centsToInput(trip.price_cents);
    f.distance_km.value = trip.distance_km > 0 ? String(trip.distance_km) : "";
  } else {
    f.transport.value = lastTransport();
    f.depart_at.value = f.arrive_at.value = nowRounded();
  }
  buildMetroFields(trip);
  buildSeatOptions(f.transport.value, trip ? trip.seat : "");
  applyHints();
  showDialog(tripDialog);
  tripDialog.querySelector(".sheet-body").scrollTop = 0;
}

function readForm() {
  const f = tripForm.elements;
  const text = (name) => f[name].value.trim();
  if (f.transport.value === "metro") {
    return {
      transport: "metro",
      depart_at: f.depart_at.value.slice(0, 16),
      arrive_at: f.arrive_at.value.slice(0, 16),
      price: text("price").replace(/^¥/, ""),
      network: currentNetwork(),
      legs: readLegs(),
      distance_km: text("distance_km"),
      note: text("note"),
    };
  }
  return {
    transport: f.transport.value,
    depart_at: f.depart_at.value.slice(0, 16),
    arrive_at: f.arrive_at.value.slice(0, 16),
    price: text("price").replace(/^¥/, ""),
    from_place: text("from_place"),
    to_place: text("to_place"),
    train_no: text("train_no").toUpperCase(),
    vehicle_model: text("vehicle_model"),
    seat: currentSeat(),
    distance_km: text("distance_km"),
    note: text("note"),
  };
}

function checkTrip(d) {
  if (!TMAP[d.transport]) return "请选择交通方式";
  if (d.transport === "metro") {
    if (!d.network) return "请选择或新增地铁系统，如“北京地铁”";
    const missing = d.legs.findIndex((leg) => !leg.line);
    if (missing >= 0) return `第 ${missing + 1} 段请选择线路`;
  }
  if (!d.depart_at) return "请填写出发时间";
  if (!d.arrive_at) return "请填写到达时间";
  if (d.arrive_at < d.depart_at) return "到达时间不能早于出发时间";
  if (!d.price) return "请填写票价";
  if (!/^\d+(\.\d{1,2})?$/.test(d.price)) return "票价请填写数字，最多两位小数";
  if (d.distance_km && !/^\d+(\.\d)?$/.test(d.distance_km)) return "里程请填写数字，最多一位小数";
  return null;
}

tripForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (state.saving) return;
  const data = readForm();
  const problem = checkTrip(data);
  if (problem) {
    $("#trip-error").textContent = problem;
    return;
  }
  state.saving = true;
  $("#save-btn").disabled = true;
  try {
    if (state.editing) await api("PUT", `/api/trips/${state.editing.id}`, data);
    else await api("POST", "/api/trips", data);
    remember("lastTransport", data.transport);
    if (data.network) remember("lastNetwork", data.network);
    tripDialog.close();
    toast("已保存");
    await loadTrips();
  } catch (err) {
    $("#trip-error").textContent = err.message;
  } finally {
    state.saving = false;
    $("#save-btn").disabled = false;
  }
});

// 出发时间晚于到达时间时，把到达时间同步过去
tripForm.elements.depart_at.addEventListener("change", () => {
  const f = tripForm.elements;
  if (f.depart_at.value && (!f.arrive_at.value || f.arrive_at.value < f.depart_at.value)) {
    f.arrive_at.value = f.depart_at.value;
  }
});

// 根据车次首字母自动切换火车类型
tripForm.elements.train_no.addEventListener("input", () => {
  const f = tripForm.elements;
  if (!TRAIN_TYPES.has(f.transport.value)) return;
  const first = f.train_no.value.trim().charAt(0).toUpperCase();
  let guess = null;
  if (first === "G") guess = "hsr";
  else if (first === "D") guess = "emu";
  else if (/[KTZYL0-9]/.test(first)) guess = "normal_train";
  if (guess && guess !== f.transport.value) {
    f.transport.value = guess;
    applyHints();
  }
});

$("#delete-btn").addEventListener("click", async () => {
  if (!state.editing || !confirm("确定删除这条记录吗？删除后无法恢复。")) return;
  try {
    await api("DELETE", `/api/trips/${state.editing.id}`);
    tripDialog.close();
    toast("已删除");
    await loadTrips();
  } catch (err) {
    $("#trip-error").textContent = err.message;
  }
});

// ---------- 菜单：导入导出 ----------

const menuDialog = $("#menu-dialog");

function todayStamp() {
  const d = new Date();
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
}

async function exportData() {
  const data = await api("GET", "/api/export");
  const name = `travel-log-${todayStamp()}.json`;
  await Platform.saveFile(name, JSON.stringify(data, null, 2), "application/json");
}

async function importFile(file) {
  let parsed;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    toast("文件不是有效的 JSON");
    return;
  }
  const trips = Array.isArray(parsed) ? parsed : parsed && parsed.trips;
  if (!Array.isArray(trips)) {
    toast("文件中没有找到行程记录");
    return;
  }
  if (!confirm(`将追加导入 ${trips.length} 条记录（不会覆盖已有记录），继续吗？`)) return;
  const result = await api("POST", "/api/import", { trips });
  toast(`已导入 ${result.imported} 条`);
  await loadTrips();
}

// ---------- 快速JSON导入：复制提示词、预览、确认后写入 ----------

const quickImportDialog = $("#quick-import-dialog");
const quickImportText = $("#quick-import-text");
const quickImportConfirm = $("#confirm-quick-import");
let quickImportTimer = null;
let quickImportBusy = false;
let quickImportUncertain = false;

function resetQuickImport() {
  clearTimeout(quickImportTimer);
  quickImportTimer = null;
  quickImportText.value = "";
  quickImportText.disabled = false;
  quickImportConfirm.disabled = true;
  quickImportConfirm.textContent = "确认导入";
  $("#quick-import-close").disabled = false;
  $("#copy-import-prompt").disabled = false;
  $("#import-prompt").value = "";
  $("#import-prompt-details").open = false;
  $("#import-copy-status").textContent = "";
  $("#quick-import-status").textContent = "";
  $("#quick-import-error").textContent = "";
  $("#quick-import-preview").replaceChildren();
  quickImportUncertain = false;
}

function previewText(value, missing = "待核对") {
  if (typeof value !== "string" && typeof value !== "number") return missing;
  const text = String(value).trim();
  return text ? (text.length > 160 ? text.slice(0, 160) + "…" : text) : missing;
}

function previewPrice(trip) {
  if (Object.hasOwn(trip, "price")) {
    const price = previewText(trip.price, "");
    if (/^\d+(\.\d{1,2})?$/.test(price) && Number(price) <= 1000000) return "¥" + price;
    return "票价待核对";
  }
  if (Number.isInteger(trip.price_cents) && trip.price_cents >= 0 && trip.price_cents <= 100000000) {
    return fmtPrice(trip.price_cents);
  }
  return "票价待核对";
}

function renderQuickImport(trips) {
  const preview = $("#quick-import-preview");
  preview.replaceChildren();
  for (const [index, trip] of trips.slice(0, 20).entries()) {
    const transport = typeof trip.transport === "string" && Object.hasOwn(TMAP, trip.transport)
      ? TMAP[trip.transport].label : "交通方式待核对";
    const legs = Array.isArray(trip.legs) ? trip.legs : [];
    const from = trip.transport === "metro" ? legs[0]?.from_station : trip.from_place;
    const to = trip.transport === "metro" ? legs[legs.length - 1]?.to_station : trip.to_place;
    preview.append(h("li", {},
      h("strong", {}, `${index + 1}. ${transport} · ${previewText(from, "未填写起点")} → ${previewText(to, "未填写终点")}`),
      h("p", {}, `${previewText(trip.depart_at)} → ${previewText(trip.arrive_at)}`),
      h("p", {}, previewPrice(trip))));
  }
  $("#quick-import-status").textContent = `已解析 ${trips.length} 条${trips.length > 20 ? "，仅展示前 20 条" : ""}，请核对后确认导入。`;
  quickImportConfirm.textContent = `确认导入 ${trips.length} 条`;
  quickImportConfirm.disabled = quickImportBusy || quickImportUncertain;
}

function parseQuickImport() {
  clearTimeout(quickImportTimer);
  quickImportTimer = null;
  try {
    const parsed = QuickImport.parse(quickImportText.value);
    renderQuickImport(parsed.trips);
    return parsed;
  } catch (err) {
    $("#quick-import-status").textContent = "";
    $("#quick-import-error").textContent = err.message;
    quickImportConfirm.disabled = true;
    return null;
  }
}

$("#quick-import-btn").addEventListener("click", () => {
  menuDialog.close();
  resetQuickImport();
  $("#import-prompt").value = QuickImport.buildPrompt(toLocalInput(new Date()).slice(0, 10));
  showDialog(quickImportDialog);
});

$("#copy-import-prompt").addEventListener("click", async () => {
  const prompt = $("#import-prompt");
  prompt.value = QuickImport.buildPrompt(toLocalInput(new Date()).slice(0, 10));
  try {
    await navigator.clipboard.writeText(prompt.value);
    $("#import-copy-status").textContent = "已复制提示词，请粘贴到你选择的 AI 工具并附上行程资料。";
  } catch {
    $("#import-prompt-details").open = true;
    prompt.focus();
    prompt.select();
    $("#import-copy-status").textContent = "未能自动复制，已选中提示词，请手动复制。";
  }
});

quickImportText.addEventListener("input", () => {
  if (quickImportUncertain || quickImportBusy) return;
  clearTimeout(quickImportTimer);
  quickImportConfirm.disabled = true;
  quickImportConfirm.textContent = "确认导入";
  $("#quick-import-preview").replaceChildren();
  $("#quick-import-error").textContent = "";
  $("#quick-import-status").textContent = quickImportText.value.trim() ? "正在解析…" : "";
  quickImportTimer = setTimeout(parseQuickImport, 250);
});

quickImportConfirm.addEventListener("click", async () => {
  if (quickImportBusy || quickImportUncertain) return;
  const parsed = parseQuickImport();
  if (!parsed) return;
  quickImportBusy = true;
  quickImportText.disabled = true;
  quickImportConfirm.disabled = true;
  $("#quick-import-close").disabled = true;
  $("#copy-import-prompt").disabled = true;
  $("#quick-import-error").textContent = "";
  $("#quick-import-status").textContent = "正在导入，请稍候…";
  let result;
  try {
    result = await api("POST", "/api/import", { trips: parsed.trips });
  } catch (err) {
    quickImportUncertain = err.status === 0;
    $("#quick-import-status").textContent = "";
    $("#quick-import-error").textContent = quickImportUncertain
      ? "导入结果尚未确认，请先关闭此面板并刷新记录核对，确认未导入后再重试，避免重复追加。"
      : err.message;
  } finally {
    quickImportBusy = false;
    quickImportText.disabled = false;
    quickImportConfirm.disabled = quickImportUncertain || !quickImportDialog.open;
    $("#quick-import-close").disabled = false;
    $("#copy-import-prompt").disabled = false;
  }
  if (!result) return;
  quickImportDialog.close();
  toast(`已导入 ${result.imported} 条`);
  try {
    await loadTrips();
  } catch {
    toast(`已导入 ${result.imported} 条，但刷新失败，请刷新页面查看`);
  }
});

quickImportDialog.addEventListener("close", resetQuickImport);
quickImportDialog.addEventListener("cancel", (event) => {
  if (quickImportBusy) event.preventDefault();
});

const dialogStack = [];

function showDialog(dialog) {
  dialog.showModal();
  const previous = dialogStack.indexOf(dialog);
  if (previous >= 0) dialogStack.splice(previous, 1);
  dialogStack.push(dialog);
}

Platform.onBackButton(() => {
  if (quickImportBusy && quickImportDialog.open) return true;
  while (dialogStack.length) {
    const dialog = dialogStack.pop();
    if (!dialog.open) continue;
    dialog.close();
    return true;
  }
  if (!$("#chart-tip").hidden) {
    hideTip();
    return true;
  }
  if (state.view === "dash") {
    setView("records");
    return true;
  }
  return false;
});

$("#menu-btn").addEventListener("click", () => showDialog(menuDialog));

$("#export-btn").addEventListener("click", async () => {
  menuDialog.close();
  try {
    await exportData();
  } catch (err) {
    toast(err.message);
  }
});

$("#import-btn").addEventListener("click", () => {
  menuDialog.close();
  $("#import-file").click();
});

$("#import-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    await importFile(file);
  } catch (err) {
    toast(err.message);
  }
});

$("#logout-btn").addEventListener("click", async () => {
  menuDialog.close();
  try {
    await Platform.signOut();
  } finally {
    showLogin();
  }
});

$("#switch-server-btn").addEventListener("click", async () => {
  if (!confirm("退出登录并清除服务器地址？")) return;
  menuDialog.close();
  try {
    await Platform.forgetServer();
  } finally {
    showLogin();
  }
});

for (const btn of document.querySelectorAll("[data-close]")) {
  btn.addEventListener("click", () => btn.closest("dialog").close());
}

// ---------- 登录与启动 ----------

function showLogin() {
  for (const dlg of document.querySelectorAll("dialog[open]")) dlg.close();
  state.trips = [];
  $("#main").hidden = true;
  $("#login").hidden = false;
  $("#login-password").value = "";
  $("#connection-status").hidden = true;
  $("#login-server").value = Platform.apiBase();
  (Platform.isNative && !Platform.apiBase() ? $("#login-server") : $("#login-password")).focus();
}

function showMain() {
  $("#menu-server").textContent = `服务器：${Platform.serverLabel()}`;
  $("#login").hidden = true;
  $("#main").hidden = false;
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button");
  btn.disabled = true;
  $("#login-error").textContent = "";
  try {
    await Platform.signIn($("#login-server").value, $("#login-password").value);
    showMain();
    await loadServerData();
  } catch (err) {
    if (Platform.isNative && Platform.hasCredentials() && !$("#main").hidden) showConnectionError(err);
    else $("#login-error").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

$("#add-btn").addEventListener("click", () => openEditor(null));

async function loadTrips() {
  const data = await api("GET", "/api/trips");
  state.trips = data.trips;
  $("#connection-status").hidden = true;
  render();
}

let toastTimer;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 2200);
}

async function loadServerData() {
  if (Platform.isNative) {
    const meta = await api("GET", "/api/meta");
    if (!meta || meta.app !== "travel-log") throw new ApiError("这不是旅行记录服务器", 200);
    if (typeof meta.api_version === "number" && meta.api_version > 1) throw new ApiError("服务器版本较新，请更新 App", 200);
    if (meta.api_version !== 1) throw new ApiError("服务器版本过旧，请先更新服务器", 200);
  }
  await loadTrips();
}

function showConnectionError(err) {
  $("#connection-message").textContent = err.status === 0 && err.message !== "连接超时，请检查网络" ? "无法连接到服务器" : err.message;
  $("#connection-status").hidden = false;
}

$("#retry-btn").addEventListener("click", async () => {
  const button = $("#retry-btn");
  button.disabled = true;
  try {
    await loadServerData();
  } catch (err) {
    if (err.status !== 401) showConnectionError(err);
  } finally {
    button.disabled = false;
  }
});

async function boot() {
  buildTransportOptions();
  $("#login-server").hidden = !Platform.isNative;
  $("#login-form").noValidate = Platform.isNative;
  $("#native-info").hidden = !Platform.isNative;
  $("#switch-server-btn").hidden = !Platform.isNative;
  try {
    await Platform.init();
    if (Platform.isNative) {
      if (!Platform.hasCredentials()) return showLogin();
    } else {
      const session = await api("GET", "/api/session");
      if (!session.authenticated) return showLogin();
    }
    showMain();
    await loadServerData();
  } catch (err) {
    if (err.status !== 401) {
      if (Platform.isNative && Platform.hasCredentials()) {
        showMain();
        showConnectionError(err);
      } else {
        showLogin();
        $("#login-error").textContent = err.message;
      }
    }
  }
}

boot();
