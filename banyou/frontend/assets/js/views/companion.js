/** AI 伴游 · 纯对话模式 —— 本应用的唯一页面。
 *
 *  保留能力：
 *  - 知识库：回复内容来自景区/点位/路线知识库（服务端检索组织）；
 *  - 位置获取：GPS 持续跟踪 → 首次定位后自动锁定所在景区（服务端 locate），
 *    顶部位置条实时显示最近点位与距离；进入点位触发半径时主动推送讲解。
 *  简化：不再有首页/景区详情/点位页，设置收进标题栏齿轮浮层，好物在标题栏。
 */

import { bootstrap, getArea, getPrefs, setPrefs, companionLocate } from "../api.js";
import { haversine, fmtDistance, getPosition, onPosition, startWatch, stopWatch, setDemoPosition } from "../geo.js";
import { openShop, openOrders } from "../shop.js";
import { bleStatus } from "../ble.js";
import { canRecord, startRecording, stopRecording } from "../voice-input.js";
import { ttsState, toggle, stopAll } from "../tts.js";
import { el, esc, refreshIcons, toast, vibrate } from "../ui.js";

export async function render(_match, container) {
  const boot = await bootstrap();
  const prefs = getPrefs();

  /* ---- 骨架 ---- */
  container.innerHTML = `
    <div class="chat">
      <div class="chat-head">
        <div class="info">
          <b>${esc(boot.app.app_display_name || "凉山伴游")} · AI 伴游</b>
          <span id="chat-sub">${esc(boot.app.slogan || "知识库 + 定位的纯对话导览")}</span>
        </div>
        <span class="chip" id="chat-geo" title="定位状态"><i data-lucide="locate-fixed"></i>定位中</span>
        <button class="hicon" id="chat-shop" aria-label="手边好物"><i data-lucide="shopping-bag"></i></button>
        <button class="hicon" id="chat-set" aria-label="设置"><i data-lucide="settings-2"></i></button>
      </div>

      <div class="chat-ctx" id="chat-ctx">
        <i data-lucide="map-pin"></i><span id="chat-ctx-txt">正在获取位置…</span>
        <button class="mini" id="chat-demo" title="把虚拟定位钉到最近点位">模拟到达</button>
      </div>

      <div class="chat-msgs" id="chat-msgs"></div>

      <div class="chat-chips" id="chat-chips"></div>

      <div class="chat-input">
        <button class="mic primary" id="chat-mic" aria-label="按住说话"><i data-lucide="mic"></i></button>
        <input id="chat-text" type="text" placeholder="问我任何关于这里的事…" enterkeyhint="send" maxlength="200">
        <button class="send" id="chat-send" aria-label="发送"><i data-lucide="send-horizontal"></i></button>
      </div>
    </div>
  `;
  refreshIcons();

  const msgsEl = container.querySelector("#chat-msgs");
  const chipsEl = container.querySelector("#chat-chips");
  const ctxTxt = container.querySelector("#chat-ctx-txt");
  const geoChip = container.querySelector("#chat-geo");
  const input = container.querySelector("#chat-text");
  const sendBtn = container.querySelector("#chat-send");

  /* ---- 状态 ---- */
  const scopeKey = "free";
  const SAVE_KEY = `banyou:chat:${scopeKey}`;
  const radiusOf = (s) => s.radius || Number(boot.app.default_arrival_radius) || 50;

  let msgs = [];
  try { msgs = JSON.parse(sessionStorage.getItem(SAVE_KEY) || "[]"); } catch { /* 忽略坏档 */ }
  const visited = new Set(msgs.filter((m) => m.arrival).map((m) => m.arrival));

  let area = null;          // 首次定位后自动锁定（服务端 locate）
  let areaLoading = false;
  let lastSuggestions = ["这里有什么故事", "附近怎么玩", "门票多少钱", "吃什么"];

  /* ---- 消息渲染 ---- */

  function bubble(m) {
    if (m.role === "user") {
      return el(`<div class="msg me"><div class="bubble">${esc(m.content)}</div></div>`);
    }
    const key = `chat-${msgs.indexOf(m)}`;
    const playing = ttsState() === key;
    const refs = (m.refs || []).map((r) =>
      `<button class="ref" data-ref="${esc(r.name)}"><i data-lucide="map-pin"></i>${esc(r.name)}</button>`).join("");

    /* 富卡片：美景卡片（点位/景区）与购物卡片（文创商品） */
    const cards = (m.cards || []).map((c, i) => {
      const ph = c.image_url
        ? `<img src="${esc(c.image_url)}" alt="" loading="lazy">`
        : `<div class="ph-char ph-${i % 6}">${esc(c.title[0] || "景")}</div>`;
      const price = c.type === "product" ? `<div class="mc-price">¥${Number(c.price).toFixed(c.price % 1 ? 2 : 0)}</div>` : "";
      return `
        <div class="msg-card" data-ctype="${c.type}" data-ctitle="${esc(c.title)}">
          <div class="mc-cover">${ph}</div>
          <div class="mc-body">
            <b>${esc(c.title)}</b>
            <span>${esc(c.subtitle || "")}</span>
            ${price}
          </div>
          ${c.type === "product" ? '<div class="mc-go">选购</div>' : ""}
        </div>`;
    }).join("");

    const b = el(`
      <div class="msg ai">
        <div class="avatar"><i data-lucide="mountain"></i></div>
        <div class="bubble">
          ${m.arrival ? '<div class="arrive-tag"><i data-lucide="bell-ring"></i>到达 · 自动讲解</div>' : ""}
          <div class="txt">${esc(m.content)}</div>
          ${cards ? `<div class="msg-cards">${cards}</div>` : ""}
          ${refs ? `<div class="refs">${refs}</div>` : ""}
          ${m.kind === "narration" || m.kind === "llm" ? `
            <div class="msg-ops">
              <button class="op play" data-key="${key}"><i data-lucide="${playing ? "square" : "volume-2"}"></i>${playing ? "停止" : "语音播报"}</button>
            </div>` : ""}
        </div>
      </div>`);
    const play = b.querySelector(".op.play");
    if (play) play.addEventListener("click", () => {
      toggle(play.dataset.key, { text: m.content, audioUrl: null, lang: prefs.lang, rate: Number(prefs.rate) || 1 });
      paintPlayIcons();
    });
    b.querySelectorAll(".ref").forEach((r) =>
      r.addEventListener("click", () => send(`给我讲讲「${r.dataset.ref}」`)));
    b.querySelectorAll(".msg-card").forEach((card) => {
      card.addEventListener("click", () => {
        if (card.dataset.ctype === "product") { openShop({}); return; }   // 购物卡片 → 好物浮层选购
        send(`给我讲讲「${card.dataset.ctitle}」`);                        // 美景卡片 → 继续对话
      });
    });
    return b;
  }

  function paintPlayIcons() {
    msgsEl.querySelectorAll(".op.play").forEach((btn) => {
      const on = ttsState() === btn.dataset.key;
      btn.classList.toggle("playing", on);
      btn.innerHTML = `<i data-lucide="${on ? "square" : "volume-2"}"></i>${on ? "停止" : "语音播报"}`;
    });
    refreshIcons();
  }

  function push(m, { save = true, speak = false } = {}) {
    msgs.push(m);
    msgsEl.appendChild(bubble(m));
    if (save) persist();
    msgsEl.scrollTop = msgsEl.scrollHeight;
    if (speak && prefs.autoPlay === "1") {
      toggle(`chat-${msgs.length - 1}`, { text: m.content, audioUrl: null, lang: prefs.lang, rate: Number(prefs.rate) || 1 });
    }
    paintPlayIcons();
  }

  function persist() {
    try { sessionStorage.setItem(SAVE_KEY, JSON.stringify(msgs.slice(-60))); } catch { /* 容量忽略 */ }
  }

  window.addEventListener("ttschange", paintPlayIcons);

  function renderChips(list) {
    chipsEl.innerHTML = "";
    (list || []).forEach((q) => {
      const c = el(`<button class="chip q">${esc(q)}</button>`);
      c.addEventListener("click", () => send(q));
      chipsEl.appendChild(c);
    });
  }

  /* ---- 发送 ---- */

  let pending = false;
  async function send(text) {
    text = (text || "").trim();
    if (!text || pending) return;
    pending = true;
    sendBtn.disabled = true;
    push({ role: "user", content: text });

    const typing = el(`<div class="msg ai typing"><div class="avatar"><i data-lucide="mountain"></i></div><div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>`);
    msgsEl.appendChild(typing);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    refreshIcons();

    const pos = getPosition();
    try {
      const res = await fetch("/api/v1/companion/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          lat: pos?.lat, lng: pos?.lng,
          area_id: area?.id || null,
          history: msgs.filter((m) => !m.arrival).slice(-6).map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "网络异常");
      const data = await res.json();
      typing.remove();
      push({ role: "ai", content: data.reply, kind: data.kind, refs: data.refs || [], cards: data.cards || [] });
      renderChips(data.suggestions || lastSuggestions);
      lastSuggestions = data.suggestions || lastSuggestions;
      // 对话即上下文：用户说「我在泸沽湖」后，服务端锁定景区，这里记住并装载知识
      const ctxArea = data.context?.area;
      if (ctxArea && (!area || area.id !== ctxArea.id)) {
        try {
          area = await getArea(ctxArea.id);
          container.querySelector("#chat-sub").textContent = `${area.name} · ${area.spot_count} 个讲解点`;
          paintCtx();
        } catch { /* 忽略 */ }
      }
      paintCtx();
      // 耳机语音沟通：讲解员的每句回答都播报（可关）
      if (prefs.autoPlay === "1") {
        toggle(`chat-${msgs.length - 1}`, { text: data.reply, audioUrl: null, lang: prefs.lang, rate: Number(prefs.rate) || 1 });
      }
      paintPlayIcons();
    } catch (err) {
      typing.remove();
      push({ role: "ai", content: `网络开小差了（${err.message}），再试一次？`, kind: "small" });
    } finally {
      pending = false;
      sendBtn.disabled = false;
      msgsEl.scrollTop = msgsEl.scrollHeight;
    }
  }

  sendBtn.addEventListener("click", () => { send(input.value); input.value = ""; });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { send(input.value); input.value = ""; }
  });

  /* ---- 位置上下文：定位 → 锁定景区 → 最近点位 / 到站讲解 ---- */

  function spotsPool() { return area ? area.spots : []; }

  async function lockAreaByPosition(pos) {
    if (area || areaLoading) return;
    areaLoading = true;
    try {
      const loc = await companionLocate(pos.lat, pos.lng);
      if (loc.area_id) {
        area = await getArea(loc.area_id);
        container.querySelector("#chat-sub").textContent =
          `${area.name} · ${area.spot_count} 个讲解点`;
      }
    } catch { /* 定位知识锚点失败不阻塞对话 */ }
    areaLoading = false;
    paintCtx();
  }

  function nearestSpot(pos) {
    const pool = spotsPool();
    if (!pos || !pool.length) return null;
    const withD = pool.map((s) => ({ ...s, _dist: haversine(pos.lat, pos.lng, s.lat, s.lng) }));
    withD.sort((a, b) => a._dist - b._dist);
    return withD[0];
  }

  function paintCtx() {
    const pos = getPosition();
    if (!pos) { ctxTxt.textContent = "定位中…（桌面可用「模拟到达」体验）"; return; }
    const s = nearestSpot(pos);
    if (!s) {
      ctxTxt.textContent = area ? "已就位，随便问我" : "定位成功，正在锁定所在景区…";
      return;
    }
    const arrived = s._dist <= radiusOf(s);
    ctxTxt.innerHTML = arrived
      ? `✓ 已到达「${esc(s.name)}」`
      : `距「${esc(s.name)}」${fmtDistance(s._dist)}`;
  }

  function checkArrive(pos) {
    for (const s of spotsPool()) {
      const d = haversine(pos.lat, pos.lng, s.lat, s.lng);
      if (d <= radiusOf(s) && !visited.has(s.id)) {
        visited.add(s.id);
        const narr = (s.narration || {})[prefs.lang] || (s.narration || {}).zh || "";
        push({
          role: "ai", kind: narr ? "narration" : "small", arrival: s.id,
          content: narr
            ? `我们到「${s.name}」了。${narr}`
            : `我们到「${s.name}」了，它的讲解内容筹备中，您可以先四处看看。`,
          refs: [{ type: "spot", id: s.id, name: s.name }],
        }, { speak: true });
        vibrate();
      }
    }
  }

  const unwatch = onPosition((pos) => {
    geoChip.innerHTML = `<i data-lucide="${pos.source === "demo" ? "flask-conical" : "locate-fixed"}"></i>${pos.source === "demo" ? "演示" : "GPS"}`;
    refreshIcons();
    lockAreaByPosition(pos);
    paintCtx();
    if (area) checkArrive(pos);
  });
  startWatch();

  // 定位权限被拒绝：位置条给出明确出路（对话锁定景区），不再永远停在「定位中…」
  const onGeoDenied = () => {
    ctxTxt.innerHTML = "定位权限被拒绝：可直接说「我在泸沽湖」锁定景区，或用「模拟到达」体验";
  };
  window.addEventListener("geo:denied", onGeoDenied);

  container.querySelector("#chat-demo").addEventListener("click", () => {
    const s = nearestSpot(getPosition());
    if (!s) return toast("先说「我在泸沽湖」锁定景区，或等定位成功");
    setDemoPosition(s.lat, s.lng);
    toast("已模拟到达最近点位（演示模式）");
  });

  /* ---- 标题栏：好物 / 设置 ---- */
  container.querySelector("#chat-shop").addEventListener("click", () => openShop({}));

  container.querySelector("#chat-set").addEventListener("click", openSettingsSheet);

  function openSettingsSheet() {
    const mask = el(`<div class="shop-mask" style="z-index:960"></div>`);
    const sheet = el(`
      <div class="shop-sheet show" style="z-index:970">
        <div class="shop-head"><b>设置</b><span class="muted">仅本机生效</span>
          <button class="close" aria-label="关闭"><i data-lucide="x"></i></button></div>
        <div class="shop-body">
          <div class="set-group" style="margin:0 0 12px">
            <div class="group-label">语音讲解</div>
            <div class="set-row">
              <div class="lab">到站自动播报</div>
              <label class="switch"><input type="checkbox" id="s-auto" ${prefs.autoPlay === "1" ? "checked" : ""}><span class="track"></span></label>
            </div>
            <div class="set-row">
              <div class="lab">讲解语言</div>
              <select id="s-lang">
                <option value="zh" ${prefs.lang === "zh" ? "selected" : ""}>中文</option>
                <option value="en" ${prefs.lang === "en" ? "selected" : ""}>English</option>
              </select>
            </div>
            <div class="set-row">
              <div class="lab">语速<small><span id="s-rate-v">${Number(prefs.rate).toFixed(1)}</span> 倍</small></div>
              <input type="range" id="s-rate" min="0.6" max="1.4" step="0.1" value="${prefs.rate}">
            </div>
          </div>
          <div class="set-group" style="margin:0 0 12px">
            <div class="group-label">耳机与订单</div>
            <div class="set-row"><div class="lab" id="s-ble">…</div><span class="chip" id="s-ble-chip">—</span></div>
            <div class="set-row" style="cursor:pointer" id="s-orders">
              <div class="lab">我的订单</div><span class="chip">查看</span>
            </div>
          </div>
          <div class="shop-foot-note">${esc(boot.app.footer_note || "")}<br>内容由 API 输出 · /api/v1</div>
        </div>
      </div>`);
    document.body.append(mask, sheet);
    refreshIcons();

    const st = bleStatus();
    const bleDetail = sheet.querySelector("#s-ble");
    const bleChip = sheet.querySelector("#s-ble-chip");
    if (st.demo) { bleDetail.textContent = "演示模式（?demo=1）"; bleChip.textContent = "DEMO"; }
    else if (st.connected) {
      bleDetail.textContent = `专用耳机已连接${st.battery != null ? ` · 电量 ${st.battery}%` : ""}`;
      bleChip.textContent = "已连接";
    } else { bleDetail.textContent = "未连接耳机（演示进入）"; bleChip.textContent = "未连接"; }

    const close = () => { mask.remove(); sheet.remove(); };
    mask.addEventListener("click", close);
    sheet.querySelector(".close").addEventListener("click", close);
    sheet.querySelector("#s-auto").addEventListener("change", (e) => setPrefs({ autoPlay: e.target.checked ? "1" : "0" }));
    sheet.querySelector("#s-lang").addEventListener("change", (e) => setPrefs({ lang: e.target.value }));
    sheet.querySelector("#s-rate").addEventListener("input", (e) => {
      setPrefs({ rate: e.target.value });
      sheet.querySelector("#s-rate-v").textContent = Number(e.target.value).toFixed(1);
    });
    sheet.querySelector("#s-orders").addEventListener("click", () => { close(); openOrders(); });
  }

  /* ---- 欢迎语 / 历史恢复 ---- */
  if (!msgs.length) {
    const hello = `您好！我是您的 AI 伴游讲解员 🏔️ 走到哪里就讲到哪里：景点故事、怎么走、门票开放时间、吃什么买什么，直接问我就好。到达景点附近时，我会主动为您讲解。`;
    const ann = boot.app.announcement ? `\n\n📢 ${boot.app.announcement}` : "";
    push({ role: "ai", kind: "small", content: hello + ann }, { save: false });
  } else {
    msgs.forEach((m) => msgsEl.appendChild(bubble(m)));
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }
  renderChips(lastSuggestions);
  paintCtx();
  const pos0 = getPosition();
  if (pos0) { lockAreaByPosition(pos0); }

  /* ---- 语音输入：耳机语音沟通主链路 ----
   *  服务端豆包 ASR 已配置 → 大麦克风：点一下说话，再点结束 → 转文字自动提问
   *  未配置但有浏览器语音识别（Chrome）→ 同一按钮走浏览器识别
   *  都不可用 → 按钮降级提示，文字输入兜底 */
  let recording = false;
  const voiceCap = { asr: false, sr: !!(window.SpeechRecognition || window.webkitSpeechRecognition) };
  fetch("/api/v1/companion/voice-status").then((r) => r.json()).then((v) => {
    voiceCap.asr = !!v.asr;
  }).catch(() => { /* 探测失败按未配置处理 */ });

  const micBtn = container.querySelector("#chat-mic");
  async function onMic() {
    if (recording) {                                   // 第二次点击：结束录音 → ASR → 提问
      recording = false;
      micBtn.classList.remove("listening");
      input.placeholder = "问我任何关于这里的事…";
      const blob = await stopRecording();
      if (!blob) return;
      micBtn.disabled = true;
      try {
        const fd = new FormData();
        fd.append("audio", blob, "speech.webm");
        const res = await fetch("/api/v1/companion/asr", { method: "POST", body: fd });
        if (!res.ok) throw new Error((await res.json()).detail || "识别失败");
        const text = (await res.json()).text || "";
        if (!text) { toast("没听清，请靠近耳机再说一遍"); return; }
        send(text);
      } catch (err) {
        toast(`${err.message}，可改用文字输入`);
      } finally {
        micBtn.disabled = false;
      }
      return;
    }
    stopAll();                                          // 别把播报声录进去
    if (voiceCap.asr && (await canRecord())) {
      try {
        recording = await startRecording();
        if (recording) {
          micBtn.classList.add("listening");
          input.placeholder = "正在聆听，说完再点一次麦克风…";
        }
      } catch {
        toast("麦克风不可用，请检查权限");
      }
      return;
    }
    if (voiceCap.sr) {
      try {
        sr.start();
        micBtn.classList.add("listening");
        toast("请讲话…");
      } catch { /* 已在识别 */ }
      return;
    }
    toast("语音服务未配置，请用文字输入");
  }
  micBtn.addEventListener("click", onMic);

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let sr = null;
  if (SR) {
    sr = new SR();
    sr.lang = "zh-CN";
    sr.interimResults = false;
    sr.onresult = (e) => {
      input.value = e.results[0][0].transcript;
      send(input.value); input.value = "";
    };
    sr.onerror = () => toast("没听清，再试一次？");
    sr.onend = () => micBtn.classList.remove("listening");
  }

  return () => {
    unwatch();
    stopWatch();
    stopAll();
    persist();
    window.removeEventListener("geo:denied", onGeoDenied);
    window.removeEventListener("ttschange", paintPlayIcons);
  };
}
