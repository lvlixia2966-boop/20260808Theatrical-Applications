/** API 接入层：游客端一切内容均来自服务端开放 API（/api/v1），本地不做内容硬编码。 */

const V1 = "/api/v1";

const cache = { bootstrap: null };

/** 应用冷启动数据：公开设置 + 区域列表（bootstrap 接口一次拉全）。 */
export async function bootstrap(force = false) {
  if (!cache.bootstrap || force) {
    cache.bootstrap = await getJSON("/bootstrap");
  }
  return cache.bootstrap;
}

export async function getJSON(path) {
  const res = await fetch(V1 + path);
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`;
    try { msg = (await res.json()).detail || msg; } catch { /* 保留默认 */ }
    throw new Error(msg);
  }
  return res.json();
}

export const getAreas = (params = {}) => getJSON("/scenic-areas" + toQuery(params));
export const getArea = (id) => getJSON(`/scenic-areas/${id}`);
export const getSpot = (id) => getJSON(`/spots/${id}`);
export const getRoute = (id) => getJSON(`/routes/${id}`);
export const getNearby = (lat, lng, limit = 10) =>
  getJSON(`/nearby?lat=${lat}&lng=${lng}&limit=${limit}`);
export const companionLocate = (lat, lng) =>
  getJSON(`/companion/locate?lat=${lat}&lng=${lng}`);

/* ---------- 文创好物（不打扰：全部被动查询，游客主动触达） ---------- */

export const getProducts = (params = {}) => getJSON("/products" + toQuery(params));

export function visitorId() {
  let vid = localStorage.getItem("banyou:vid");
  if (!vid) {
    vid = "v" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    localStorage.setItem("banyou:vid", vid);
  }
  return vid;
}

export function createOrder(items) {
  return postJSON("/orders", { visitor_id: visitorId(), items });
}

export function payOrder(orderId, channel = "wechat") {
  return postJSON(`/orders/${orderId}/pay`, { visitor_id: visitorId(), channel });
}

export function getMyOrders() {
  return getJSON("/orders?vid=" + visitorId());
}

async function postJSON(path, body) {
  const res = await fetch(V1 + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`;
    try { msg = (await res.json()).detail || msg; } catch { /* 保留默认 */ }
    throw new Error(msg);
  }
  return res.json();
}

function toQuery(params) {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`);
  return qs.length ? `?${qs.join("&")}` : "";
}

/** 用户偏好（讲解语言 / 自动播放 / 语速），localStorage 持久化。 */
const PREF_KEY = "banyou:prefs";
const DEFAULT_PREFS = { lang: "zh", autoPlay: "1", rate: "1.0" };

export function getPrefs() {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREF_KEY) || "{}") };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function setPrefs(patch) {
  const next = { ...getPrefs(), ...patch };
  localStorage.setItem(PREF_KEY, JSON.stringify(next));
  return next;
}
