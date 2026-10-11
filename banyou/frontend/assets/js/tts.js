/** 语音讲解：服务端豆包 TTS 优先（Audio 播放自动路由到已连接的蓝牙耳机），
 *  未配置/失败时回退浏览器 speechSynthesis；人工录音（audio_url）最优先。
 *  播放状态通过 window 事件 'ttschange' 广播。 */

let audioEl = null;
let currentKey = null;
let serverTts = null; // null=未探测 / true / false

export function ttsState() { return currentKey; }

export function stopAll() {
  if (audioEl) {
    try { audioEl.pause(); } catch { /* ignore */ }
    if (audioEl.src && audioEl.src.startsWith("blob:")) URL.revokeObjectURL(audioEl.src);
    audioEl = null;
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  if (currentKey) {
    currentKey = null;
    broadcast("idle");
  }
}

async function probeServerTts() {
  if (serverTts !== null) return serverTts;
  try {
    const res = await fetch("/api/v1/companion/voice-status");
    serverTts = !!(await res.json()).tts;
  } catch {
    serverTts = false;
  }
  return serverTts;
}

/** 播放/停止 切换。key 用于区分不同卡片的播放态。 */
export function toggle(key, { text, audioUrl, lang = "zh", rate = 1.0 }) {
  if (currentKey === key) { stopAll(); return false; }
  stopAll();
  currentKey = key;
  broadcast("playing");

  if (audioUrl) {
    playUrl(audioUrl, key);
    return true;
  }
  speakWithServer(text, lang, Number(rate) || 1, key);
  return true;
}

function playUrl(url, key) {
  audioEl = new Audio(url);
  audioEl.onended = audioEl.onerror = () => { if (currentKey === key) stopAll(); };
  audioEl.play().catch(() => { if (currentKey === key) stopAll(); });
}

/** 豆包 TTS（回耳机）→ 失败回退浏览器 TTS（本机外放/系统蓝牙）。 */
async function speakWithServer(text, lang, rate, key) {
  if (await probeServerTts()) {
    try {
      const res = await fetch("/api/v1/companion/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang, rate }),
      });
      if (res.ok) {
        if (currentKey !== key) return;             // 已被新播放打断
        const blob = await res.blob();
        audioEl = new Audio(URL.createObjectURL(blob));
        audioEl.onended = audioEl.onerror = () => { if (currentKey === key) stopAll(); };
        await audioEl.play();
        return;
      }
    } catch { /* 回退浏览器 TTS */ }
  }
  if (currentKey !== key) return;
  speakWithBrowser(text, lang, rate, key);
}

function speakWithBrowser(text, lang, rate, key) {
  if (!window.speechSynthesis) { stopAll(); return; }
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = lang === "en" ? "en-US" : "zh-CN";
  utter.rate = rate;
  const voice = pickVoice(utter.lang);
  if (voice) utter.voice = voice;
  utter.onend = utter.onerror = () => { if (currentKey === key) stopAll(); };
  window.speechSynthesis.speak(utter);
}

function pickVoice(langPrefix) {
  const voices = window.speechSynthesis.getVoices() || [];
  return voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(langPrefix.slice(0, 2).toLowerCase())) || null;
}

function broadcast(state) {
  window.dispatchEvent(new CustomEvent("ttschange", { detail: { key: currentKey, state } }));
}

// 部分 Android 首次取不到 voice 列表，预热一次
if (window.speechSynthesis) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

// 页面隐藏/卸载时停止，避免后台继续出声
window.addEventListener("pagehide", stopAll);
