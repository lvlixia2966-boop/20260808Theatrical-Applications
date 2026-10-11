/** UI 工具：DOM 构建 / toast / 图标刷新 / 顶栏与底部导航控制。 */

export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

let toastTimer = null;
export function toast(msg, ms = 2400) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), ms);
}

export function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

/** 顶栏/底部导航外观：{title, back, action, tab, walk} */
export function setChrome(opts = {}) {
  window.dispatchEvent(new CustomEvent("chrome", { detail: opts }));
}

export function vibrate(pattern = [80, 60, 80]) {
  try { navigator.vibrate && navigator.vibrate(pattern); } catch { /* 忽略 */ }
}
