"use strict";

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { execFileSync } = require("node:child_process");
const { test } = require("node:test");
const vm = require("node:vm");

const context = vm.createContext({ TextEncoder });
vm.runInContext(readFileSync("static/quick-import.js", "utf8"), context);
const quickImport = vm.runInContext("QuickImport", context);
const trip = { transport: "bus", depart_at: "2026-10-01T08:00", arrive_at: "2026-10-01T08:30", price: "2" };
const plain = (value) => JSON.parse(JSON.stringify(value));

test("接受直接数组、trips对象与原导出对象，不改写行程字段", () => {
  for (const data of [[trip], { trips: [trip] }, { app: "travel-log", version: 1, trips: [trip] }]) {
    const result = quickImport.parse(JSON.stringify(data));
    assert.deepEqual(plain(result.trips), [trip]);
    assert.equal(result.bytes, Buffer.byteLength(JSON.stringify({ trips: [trip] })));
  }
});

test("兼容包住全文的唯一JSON围栏与首尾空白", () => {
  for (const fence of ["```json", "```JSON", "```"]) {
    assert.deepEqual(plain(quickImport.parse(` \n${fence}\n${JSON.stringify([trip])}\n\x60\x60\x60 \n`).trips), [trip]);
  }
});

test("不从解释文本、多段围栏或其他语言围栏中猜测截取数据", () => {
  for (const text of ["说明\n" + JSON.stringify([trip]), "```json\n[]\n```\n```json\n[]\n```", "```javascript\n[]\n```", "先确认数据再导入"]) {
    assert.throws(() => quickImport.parse(text), /有效的 JSON|JSON/);
  }
});

test("拒绝空输入、非JSON和尾逗号", () => {
  for (const text of ["", " \n ", "{bad}", '[{"price":"1",}]']) {
    assert.throws(() => quickImport.parse(text), /粘贴|JSON/);
  }
});

test("拒绝错误的根结构和空行程列表", () => {
  for (const text of ["null", "42", '"text"', "{}", '{"trips":{}}', "[]", '{"trips":[]}']) {
    assert.throws(() => quickImport.parse(text), /行程|记录/);
  }
});

test("逐条拒绝null、数组、数值等，不静默丢掉坏记录", () => {
  for (const item of [null, [], 1, "text", true]) {
    assert.throws(() => quickImport.parse(JSON.stringify([trip, item])), /第 2 条/);
  }
});

test("一次可解析20000条，20001条明确拒绝", () => {
  assert.equal(quickImport.parse(JSON.stringify(Array(20000).fill(trip))).trips.length, 20000);
  assert.throws(() => quickImport.parse(JSON.stringify(Array(20001).fill(trip))), /20000/);
});

test("按UTF-8字节限制大段中文，字符数未超限也不能通过", () => {
  const text = JSON.stringify([{ note: "你".repeat(1800000) }]);
  assert.ok(text.length < 5 * 1024 * 1024);
  assert.throws(() => quickImport.parse(text), /5 MB/);
});

test("5MiB实际请求体的边界包含trips封装开销", () => {
  const limit = 5 * 1024 * 1024;
  const prefix = '{"trips":[{"note":"';
  const suffix = '"}]}';
  const text = prefix + "x".repeat(limit - prefix.length - suffix.length) + suffix;
  assert.equal(quickImport.parse(text).bytes, limit);
  assert.throws(() => quickImport.parse(text.replace('"note":"', '"note":"x')), /5 MB/);
  const bareArray = text.slice(9, -1);
  assert.equal(quickImport.parse(bareArray).bytes, limit);
  assert.throws(() => quickImport.parse(bareArray.replace('"note":"', '"note":"x')), /5 MB/);
});

test("只检查输入结构，不猜补或改写必填字段", () => {
  const incomplete = { transport: "metro", note: '<img src=x onerror="alert(1)">' };
  assert.deepEqual(plain(quickImport.parse(JSON.stringify([incomplete])).trips), [incomplete]);
});

test("JSON中类似代码的文本保持为数据，不执行也不污染对象原型", () => {
  const text = '[{"note":"globalThis.injected = true","__proto__":{"polluted":true}}]';
  assert.equal(quickImport.parse(text).trips[0].note, "globalThis.injected = true");
  assert.equal(vm.runInContext("globalThis.injected", context), undefined);
  assert.equal({}.polluted, undefined);
});

test("提示词给出明确相对日期基准并要求缺必填先追问", () => {
  const prompt = quickImport.buildPrompt("2026-10-27");
  assert.ok(prompt.includes("2026-10-27"));
  assert.match(prompt, /缺少.*追问/);
  assert.match(prompt, /未知.*0|不.*0.*未知/);
  assert.match(prompt, /不.*自动.*重试|不.*重复.*生成/);
});

test("提示词中的格式示例通过真实服务器校验且包含铁路公交与多段地铁", () => {
  const prompt = quickImport.buildPrompt("2026-10-27");
  const match = prompt.match(/```json\n([\s\S]*?)\n```/);
  assert.ok(match, "提供可实际校验的严格JSON示例");
  const data = JSON.parse(match[1]);
  const checked = JSON.parse(execFileSync("python3", ["-c", "import sys,json,server; print(json.dumps([server.validate_trip(t) for t in json.load(sys.stdin)['trips']],ensure_ascii=False))"], { input: JSON.stringify(data), encoding: "utf8" }));
  assert.equal(checked.length, 3);
  assert.equal(checked[0].price_cents, 55350);
  assert.equal(checked[1].transport, "bus");
  assert.equal(checked[2].transport, "metro");
  assert.equal(checked[2].legs.length, 2);
  assert.equal(checked[2].legs[1].from_station, "建国门");
  assert.match(prompt, /示例.*不是.*行程|示例.*不得.*导入/);
});

// 执行真实快速导入处理器；只替换DOM、剪贴板和网络边界。
function importPanel(send = async () => ({ imported: 1 })) {
  class Element {
    constructor() {
      this.value = "";
      this.textContent = "";
      this.disabled = false;
      this.open = false;
      this.children = [];
      this.listeners = new Map();
    }
    addEventListener(type, listener) {
      if (!this.listeners.has(type)) this.listeners.set(type, []);
      this.listeners.get(type).push(listener);
    }
    async fire(type) {
      for (const listener of this.listeners.get(type) || []) await listener({ preventDefault() {} });
    }
    replaceChildren(...items) { this.children = items; }
    append(...items) { this.children.push(...items); }
    focus() {}
    select() { this.selectionStart = 0; this.selectionEnd = this.value.length; }
    close() { this.open = false; return this.fire("close"); }
  }
  const elements = new Map();
  const element = (selector) => {
    if (!elements.has(selector)) elements.set(selector, new Element());
    return elements.get(selector);
  };
  let date = "2026-10-27";
  let clipboard = "";
  const sandbox = vm.createContext({
    TextEncoder, setTimeout, clearTimeout,
    $: element,
    h: (tag, props, ...children) => ({ tag, props, children }),
    TMAP: { bus: { label: "公交车" }, metro: { label: "地铁" } },
    fmtPrice: (cents) => "¥" + cents / 100,
    menuDialog: new Element(),
    showDialog: (dialog) => { dialog.open = true; },
    Date: class { constructor() { this.value = date; } },
    toLocalInput: (value) => value.value + "T00:00",
    navigator: { clipboard: { writeText: async (text) => { clipboard = text; } } },
    api: send, toast() {}, loadTrips: async () => {},
  });
  vm.runInContext(readFileSync("static/quick-import.js", "utf8"), sandbox);
  const app = readFileSync("static/app.js", "utf8");
  const start = app.indexOf("// ---------- 快速JSON导入");
  const end = app.indexOf("const dialogStack = [];");
  assert.ok(start >= 0 && end > start);
  vm.runInContext(app.slice(start, end), sandbox);
  return {
    element, sandbox,
    setDate(value) { date = value; },
    clipboard: () => clipboard,
    async open() { await element("#quick-import-btn").fire("click"); },
    async preview(data) {
      element("#quick-import-text").value = JSON.stringify(data);
      await element("#quick-import-text").fire("input");
      vm.runInContext("parseQuickImport()", sandbox);
    },
  };
}

test("网络结果未确认时再编辑，保留核对警告且不冒充正在解析", async () => {
  const panel = importPanel(async () => { throw Object.assign(new Error("超时"), { status: 0 }); });
  await panel.open();
  await panel.preview([trip]);
  await panel.element("#confirm-quick-import").fire("click");
  assert.match(panel.element("#quick-import-error").textContent, /结果尚未确认/);
  panel.element("#quick-import-text").value += " ";
  await panel.element("#quick-import-text").fire("input");
  assert.match(panel.element("#quick-import-error").textContent, /结果尚未确认/);
  assert.notEqual(panel.element("#quick-import-status").textContent, "正在解析…");
  assert.equal(panel.element("#confirm-quick-import").disabled, true);
});

test("面板跨午夜打开后复制，日期基准使用复制当天", async () => {
  const panel = importPanel();
  await panel.open();
  panel.setDate("2026-10-28");
  await panel.element("#copy-import-prompt").fire("click");
  assert.match(panel.clipboard(), /日期基准：2026-10-28/);
  assert.equal(panel.element("#import-prompt").value, panel.clipboard());
});

test("预览不提交，双击仅发一请求，成功后清空并阻止再次提交", async () => {
  let requests = 0;
  let finish;
  const panel = importPanel(async () => { requests++; return new Promise((resolve) => { finish = resolve; }); });
  await panel.open();
  await panel.preview([trip]);
  assert.equal(requests, 0);
  const first = panel.element("#confirm-quick-import").fire("click");
  await panel.element("#confirm-quick-import").fire("click");
  assert.equal(requests, 1);
  assert.equal(panel.element("#quick-import-text").disabled, true);
  finish({ imported: 1 });
  await first;
  assert.equal(panel.element("#quick-import-text").value, "");
  await panel.element("#confirm-quick-import").fire("click");
  assert.equal(requests, 1);
});

test("剪贴板不可用时展开并选中提示词，供手动复制", async () => {
  const panel = importPanel();
  await panel.open();
  vm.runInContext("navigator.clipboard.writeText = async () => { throw new Error('不可用'); }", panel.sandbox);
  await panel.element("#copy-import-prompt").fire("click");
  assert.equal(panel.element("#import-prompt-details").open, true);
  const prompt = panel.element("#import-prompt");
  assert.equal(prompt.selectionStart, 0);
  assert.equal(prompt.selectionEnd, prompt.value.length);
  assert.match(panel.element("#import-copy-status").textContent, /手动复制/);
});
