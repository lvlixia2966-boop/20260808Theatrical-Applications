/** 专用耳机蓝牙准入模块（ble，移植自主项目 ble-guard.js，同套业务约定）
 *
 *  业务流程：游客在游客中心租用专用蓝牙耳机 → 扫码进入本应用 →
 *    停留在准入页（仅可选讲解语言 + 连接专用耳机）→ 连接成功才解锁伴游。
 *    耳机断连 → 停止全部语音、回退准入页；耳机回到范围内 3s 间隔自动重连。
 *
 *  高内聚：准入页 UI、BLE 连接、电量检测、断连回退、自动重连全部收敛于此。
 *  低耦合：对外派发 window 事件 'ble:connected' / 'ble:disconnected'，
 *          并在断连时兜底停止 TTS 与页面全部 <audio>。
 *
 *  环境要求：Web Bluetooth 需 HTTPS（或 localhost）+ Chrome/Edge/Android。
 *  开发旁路：URL 带 ?demo=1，或准入页「演示模式」进入（上线置 SKIP_ENABLED=false）。
 *  耳机识别：蓝牙名前缀 CHUAN（与主项目租赁耳机同一批，可用 BLE_GATE_CONFIG 覆盖）。
 */

import { getPrefs, setPrefs } from "./api.js";
import { stopAll } from "./tts.js";

const CFG = Object.assign({
  namePrefix: "CHUAN",
  lowBattery: 20,
  svcBattery: 0x180f,
  chrBattery: 0x2a19,
  pollMs: 60000,
  retryMs: 3000,
}, window.BLE_GATE_CONFIG || {});

const SKIP_ENABLED = true; // 检查/演示阶段允许跳过；上线置 false（耳机即凭证）

const DEMO_BYPASS = new URLSearchParams(location.search).get("demo") === "1";

const I18N = {
  zh: {
    title: "凉山伴游 · 语音讲解", subtitle: "请先选择语言，再连接您租用的专用耳机以开启伴游",
    stepLang: "① 选择讲解语言", stepConnect: "② 连接专用耳机",
    connectBtn: "连接专用耳机", connecting: "正在连接耳机…",
    disconnected: "耳机连接已断开，正在尝试自动重连", lowBattery: "耳机电量偏低（{b}%），请充电后继续使用",
    lowBattNow: "当前耳机电量 {b}%，建议尽快充电",
    unsupported: "当前浏览器不支持蓝牙连接，请使用 Chrome 浏览器或至服务台寻求帮助",
    helpTitle: "蓝牙在此浏览器不可用", helpL1: "iPhone / 微信内置浏览器不支持网页连接蓝牙",
    helpL2: "换用安卓 Chrome，或到游客中心服务台，工作人员协助您佩戴耳机",
    footer: "未租用耳机的游客，请至游客中心服务台办理租用",
    skipBtn: "演示模式进入（无需耳机）",
  },
  en: {
    title: "Liangshan Companion · Audio Guide", subtitle: "Select a language, then connect your rental headset to start",
    stepLang: "① Guide language", stepConnect: "② Connect rental headset",
    connectBtn: "Connect Headset", connecting: "Connecting…",
    disconnected: "Headset disconnected. Reconnecting…", lowBattery: "Headset battery low ({b}%). Please recharge.",
    lowBattNow: "Headset battery: {b}%. Charging is recommended.",
    unsupported: "Bluetooth is not supported here. Please use Chrome or ask the service desk.",
    helpTitle: "Bluetooth unavailable in this browser", helpL1: "iPhone and in-app browsers cannot connect to web Bluetooth",
    helpL2: "Switch to Chrome on Android, or visit the visitor-center service desk",
    footer: "Haven't rented a headset? Please visit the visitor-center service desk.",
    skipBtn: "Demo mode (no headset)",
  },
};

const LANG_LABELS = { zh: "中文", en: "English" };

const state = {
  lang: "zh", device: null, battery: null, lowBatt: false,
  unlocked: false, skipped: false, pollTimer: null, retryTimer: null, els: {},
};

const t = (key, extra) => {
  let s = (I18N[state.lang] || I18N.zh)[key] || I18N.zh[key] || key;
  if (extra !== undefined) s = s.replace("{b}", String(extra));
  return s;
};

/* ── 准入页样式（青山绿主题，注入一次） ── */
const GATE_CSS = `
.ble-gate{position:fixed;inset:0;z-index:9999;overflow-y:auto;
  background:linear-gradient(165deg,#06231e 0%,#0c6b58 58%,#0a3f34 100%);
  display:flex;align-items:center;justify-content:center;padding:24px}
.ble-gate.hidden{display:none}
.ble-gate-card{max-width:400px;width:100%;text-align:center;color:#eef4ef;
  animation:gateIn .45s cubic-bezier(.2,.7,.3,1)}
@keyframes gateIn{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
.ble-gate-seal{width:64px;height:64px;margin:0 auto 16px;background:linear-gradient(135deg,#e3b23c,#b9820f);
  color:#20301f;border-radius:14px;display:flex;align-items:center;justify-content:center;
  font-size:30px;font-weight:900;transform:rotate(-3deg);font-family:"Kaiti SC","STKaiti",serif;
  box-shadow:0 8px 24px rgba(227,178,60,.3)}
.ble-gate-title{font-size:20px;font-weight:800;letter-spacing:2px;margin-bottom:8px}
.ble-gate-sub{font-size:13px;color:rgba(238,244,239,.65);line-height:1.7;margin-bottom:18px}
.ble-gate-step{font-size:12px;color:#e3b23c;letter-spacing:1px;margin:16px 0 10px;text-align:left;font-weight:700}
.ble-gate-langs{display:flex;gap:8px}
.ble-gate-lang{padding:9px 16px;border-radius:999px;font-size:13px;cursor:pointer;
  border:1px solid rgba(238,244,239,.18);background:rgba(255,255,255,.06);color:rgba(238,244,239,.7)}
.ble-gate-lang.active{background:#e3b23c;color:#20301f;border-color:#e3b23c;font-weight:800}
.ble-gate-btn{display:block;width:100%;padding:15px;margin-top:4px;border:none;border-radius:12px;
  font-size:15px;font-weight:800;cursor:pointer;background:#e3b23c;color:#20301f;transition:all .15s}
.ble-gate-btn:hover:not(:disabled){filter:brightness(1.06);box-shadow:0 4px 20px rgba(227,178,60,.35)}
.ble-gate-btn:active:not(:disabled){transform:scale(.98)}
.ble-gate-btn:disabled{opacity:.5;cursor:not-allowed}
.ble-gate-alert{font-size:13px;padding:11px 13px;border-radius:10px;margin-bottom:12px;line-height:1.6;text-align:left}
.ble-gate-alert.warn{background:rgba(227,178,60,.14);color:#ffd98a;border:1px solid rgba(227,178,60,.4)}
.ble-gate-alert.err{background:rgba(179,55,44,.2);color:#ffb3a8;border:1px solid rgba(179,55,44,.45)}
.ble-gate-status{font-size:12px;color:rgba(238,244,239,.55);margin-top:12px;line-height:1.7;min-height:18px}
.ble-gate-footer{font-size:11px;color:rgba(238,244,239,.4);margin-top:20px;line-height:1.7}
.ble-gate-batt{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:rgba(238,244,239,.6);
  margin-top:10px;padding:4px 10px;border-radius:999px;border:1px solid rgba(238,244,239,.15)}
.ble-gate-batt.low{color:#ffb3a8;border-color:rgba(179,55,44,.5)}
.ble-gate-batt.hidden,.ble-gate-alert.hidden,.ble-gate-help.hidden{display:none}
.ble-gate-help{margin-top:14px;padding:14px;border-radius:12px;text-align:left;
  background:rgba(227,178,60,.1);border:1px solid rgba(227,178,60,.35)}
.ble-gate-help-title{font-size:14px;font-weight:800;color:#ffd98a;margin-bottom:8px}
.ble-gate-help-line{font-size:12px;color:rgba(238,244,239,.8);line-height:1.8;padding-left:18px;position:relative}
.ble-gate-help-line::before{content:'•';position:absolute;left:5px;color:#e3b23c}
.ble-gate-skip{margin-top:12px;background:none;border:none;cursor:pointer;
  font-size:12px;color:rgba(238,244,239,.5);text-decoration:underline;text-underline-offset:3px}
.ble-gate-skip:hover{color:rgba(238,244,239,.85)}
`;

function buildGate() {
  const style = document.createElement("style");
  style.textContent = GATE_CSS;
  document.head.appendChild(style);

  const gate = document.createElement("div");
  gate.id = "ble-gate";
  gate.className = "ble-gate";
  gate.innerHTML = `
    <div class="ble-gate-card">
      <div class="ble-gate-seal">山</div>
      <div class="ble-gate-title" data-gt="title"></div>
      <div class="ble-gate-sub" data-gt="subtitle"></div>
      <div id="ble-gate-alert" class="ble-gate-alert hidden"></div>
      <div class="ble-gate-step" data-gt="stepLang"></div>
      <div class="ble-gate-langs" id="ble-gate-langs"></div>
      <div class="ble-gate-step" data-gt="stepConnect"></div>
      <button id="ble-gate-connect" class="ble-gate-btn"></button>
      <button id="ble-gate-skip" class="ble-gate-skip" data-gt="skipBtn"></button>
      <div id="ble-gate-batt" class="ble-gate-batt hidden"></div>
      <div id="ble-gate-status" class="ble-gate-status"></div>
      <div id="ble-gate-help" class="ble-gate-help hidden">
        <div class="ble-gate-help-title"></div>
        <div class="ble-gate-help-line"></div>
        <div class="ble-gate-help-line"></div>
      </div>
      <div class="ble-gate-footer" data-gt="footer"></div>
    </div>`;
  document.body.appendChild(gate);

  state.els = {
    gate,
    alert: gate.querySelector("#ble-gate-alert"),
    langs: gate.querySelector("#ble-gate-langs"),
    btn: gate.querySelector("#ble-gate-connect"),
    skip: gate.querySelector("#ble-gate-skip"),
    batt: gate.querySelector("#ble-gate-batt"),
    status: gate.querySelector("#ble-gate-status"),
    help: gate.querySelector("#ble-gate-help"),
  };
  state.els.btn.addEventListener("click", manualConnect);
  if (SKIP_ENABLED) state.els.skip.addEventListener("click", skipGate);
  else state.els.skip.classList.add("hidden");

  Object.keys(LANG_LABELS).forEach((code) => {
    const chip = document.createElement("span");
    chip.className = "ble-gate-lang";
    chip.dataset.lang = code;
    chip.textContent = LANG_LABELS[code];
    chip.addEventListener("click", () => selectLang(code));
    state.els.langs.appendChild(chip);
  });
  renderGateText();
}

function renderGateText() {
  state.els.gate.querySelectorAll("[data-gt]").forEach((el) => {
    el.textContent = t(el.dataset.gt);
  });
  state.els.btn.textContent = t("connectBtn");
  state.els.langs.querySelectorAll(".ble-gate-lang").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.lang === state.lang);
  });
}

function selectLang(code) {
  state.lang = code;
  setPrefs({ lang: code });   // 与游客端「设置 → 讲解语言」同一偏好
  renderGateText();
}

function showHelpCard() {
  const card = state.els.help;
  if (!card) return;
  card.classList.remove("hidden");
  card.querySelector(".ble-gate-help-title").textContent = "🎧 " + t("helpTitle");
  const lines = card.querySelectorAll(".ble-gate-help-line");
  lines[0].textContent = t("helpL1");
  lines[1].textContent = t("helpL2");
}

function showAlert(kind, text) {
  state.els.alert.className = "ble-gate-alert " + kind;
  state.els.alert.textContent = text;
}
function clearAlert() { state.els.alert.className = "ble-gate-alert hidden"; }
function setStatus(text) { state.els.status.textContent = text || ""; }

function renderBattery() {
  const el = state.els.batt;
  if (state.battery == null) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  el.classList.toggle("low", state.lowBatt);
  el.textContent = `🔋 ${state.battery}%`;
}

/* ── 锁定 / 解锁 ── */

function lock(reason, battery) {
  state.unlocked = false;
  state.els.gate.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  if (reason === "lowBattery") showAlert("warn", t("lowBattery", battery));
  else if (reason === "disconnected") showAlert("err", t("disconnected"));
  else clearAlert();
  renderGateText();
}

function unlock() {
  state.unlocked = true;
  state.els.gate.classList.add("hidden");
  document.body.style.overflow = "";
  clearAlert();
  setStatus("");
  renderBattery();
  window.dispatchEvent(new CustomEvent("ble:connected", {
    detail: { name: state.device ? state.device.name : "", battery: state.battery, lowBattery: state.lowBatt },
  }));
}

function skipGate() {
  state.unlocked = false;
  state.skipped = true;
  sessionStorage.setItem("ble_gate_skipped", "1"); // 仅本标签页会话；新开页面仍出准入页
  state.els.gate.classList.add("hidden");
  document.body.style.overflow = "";
}

/* ── BLE 连接 ── */

async function manualConnect() {
  if (!navigator.bluetooth) {
    showAlert("err", t("unsupported"));
    showHelpCard();
    return;
  }
  state.els.btn.disabled = true;
  setStatus(t("connecting"));
  try {
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: CFG.namePrefix }],
      optionalServices: [CFG.svcBattery],
    });
    await setupDevice(device);
  } catch (err) {
    if (err.name !== "NotFoundError") setStatus(t("disconnected"));
    else setStatus("");
  } finally {
    state.els.btn.disabled = false;
  }
}

async function setupDevice(device) {
  stopRetry();
  device.addEventListener("gattserverdisconnected", onDisconnected);
  const server = await device.gatt.connect();
  state.device = device;
  await readBattery(server);   // 尽力而为：耳机不支持电量服务不阻塞解锁
  startPoll();
  if (state.lowBatt) showAlert("warn", t("lowBattNow", state.battery));
  else clearAlert();
  unlock();
}

async function readBattery(server) {
  try {
    const svc = await server.getPrimaryService(CFG.svcBattery);
    const chr = await svc.getCharacteristic(CFG.chrBattery);
    const val = await chr.readValue();
    state.battery = val.getUint8(0);
    state.lowBatt = state.battery < CFG.lowBattery;
  } catch {
    state.battery = null;
    state.lowBatt = false;
  }
}

function startPoll() {
  stopPoll();
  state.pollTimer = setInterval(async () => {
    if (!state.device || !state.device.gatt.connected) return;
    try { await readBattery(state.device.gatt); renderBattery(); } catch { /* ignore */ }
  }, CFG.pollMs);
}
function stopPoll() { clearInterval(state.pollTimer); state.pollTimer = null; }

function onDisconnected() {
  stopPoll();
  stopAll();  // 伴游语音立即停止
  document.querySelectorAll("audio").forEach((a) => { try { a.pause(); } catch { /* ignore */ } });
  window.dispatchEvent(new CustomEvent("ble:disconnected", {
    detail: { lowBattery: state.lowBatt, battery: state.battery },
  }));
  lock(state.lowBatt ? "lowBattery" : "disconnected", state.battery);
  scheduleRetry();  // 耳机回到范围内自动恢复
}

function scheduleRetry() {
  stopRetry();
  state.retryTimer = setInterval(async () => {
    if (!state.device || state.device.gatt.connected) return;
    try {
      const server = await state.device.gatt.connect();
      await readBattery(server);
      startPoll();
      unlock();
      stopRetry();
    } catch { /* 未回到范围：继续等 */ }
  }, CFG.retryMs);
}
function stopRetry() { clearInterval(state.retryTimer); state.retryTimer = null; }

/* ── 初始化 ── */

export function bleStatus() {
  return {
    connected: state.unlocked, skipped: state.skipped,
    demo: DEMO_BYPASS, battery: state.battery, lowBattery: state.lowBatt,
  };
}

async function init() {
  if (DEMO_BYPASS) return;   // 开发旁路：?demo=1

  state.lang = getPrefs().lang === "en" ? "en" : "zh";
  buildGate();

  if (sessionStorage.getItem("ble_gate_skipped") === "1") {
    state.skipped = true;
    state.els.gate.classList.add("hidden");
    return;
  }
  lock("initial");

  // 曾连接过的设备：静默自动重连（Chrome getDevices），失败则等待手动连接
  if (navigator.bluetooth && navigator.bluetooth.getDevices) {
    try {
      const devices = await navigator.bluetooth.getDevices();
      const mine = devices.find((d) => (d.name || "").startsWith(CFG.namePrefix));
      if (mine) {
        try { await setupDevice(mine); } catch { /* 静默：留在准入页 */ }
      }
    } catch { /* 浏览器不支持：忽略 */ }
  }
}

init();
