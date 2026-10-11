/** 地理工具：距离 / 方位角 / 坐标系纠偏 / 定位跟踪（含演示模式）。 */

const EARTH_R = 6371008.8;
const demo = { lat: null, lng: null };

export function haversine(lat1, lng1, lat2, lng2) {
  const p1 = rad(lat1), p2 = rad(lat2);
  const dp = p2 - p1, dl = rad(lng2 - lng1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * EARTH_R * Math.asin(Math.sqrt(a));
}

export function bearing(lat1, lng1, lat2, lng2) {
  const p1 = rad(lat1), p2 = rad(lat2), dl = rad(lng2 - lng1);
  const x = Math.sin(dl) * Math.cos(p2);
  const y = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (Math.atan2(x, y) * 180 / Math.PI + 360) % 360;
}

const _BEARINGS = ["正北", "东北", "正东", "东南", "正南", "西南", "正西", "西北"];

/** 方位角 → 八向位名称。 */
export function fmtBearing(deg) {
  return _BEARINGS[Math.floor(((deg + 22.5) % 360) / 45)];
}

export function fmtDistance(meters) {
  if (meters >= 10000) return `${(meters / 1000).toFixed(0)}km`;
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)}km`;
  return `${Math.max(0, Math.round(meters))}m`;
}

/** WGS-84 → GCJ-02（高德/天地图瓦片为 GCJ-02，GPS 定位为 WGS-84，需纠偏后再上图）。 */
const GCJ_A = 6378245.0;
const GCJ_EE = 0.00669342162296594323;

export function wgsToGcj(lat, lng) {
  const outOfChina = lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
  if (outOfChina) return [lat, lng];
  let dLat = transformLat(lng - 105.0, lat - 35.0);
  let dLng = transformLng(lng - 105.0, lat - 35.0);
  const radLat = rad(lat);
  let magic = Math.sin(radLat);
  magic = 1 - GCJ_EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / ((GCJ_A * (1 - GCJ_EE)) / (magic * magic) * Math.PI);
  dLng = (dLng * 180.0) / (GCJ_A / sqrtMagic * Math.cos(radLat) * Math.PI);
  return [lat + dLat, lng + dLng];
}

function transformLat(x, y) {
  let ret = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  ret += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
  ret += (20 * Math.sin(y * Math.PI) + 40 * Math.sin(y / 3 * Math.PI)) * 2 / 3;
  ret += (160 * Math.sin(y / 12 * Math.PI) + 320 * Math.sin(y * Math.PI / 30)) * 2 / 3;
  return ret;
}

function transformLng(x, y) {
  let ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  ret += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
  ret += (20 * Math.sin(x * Math.PI) + 40 * Math.sin(x / 3 * Math.PI)) * 2 / 3;
  ret += (150 * Math.sin(x / 12 * Math.PI) + 300 * Math.sin(x / 30 * Math.PI)) * 2 / 3;
  return ret;
}

function rad(d) { return d * Math.PI / 180; }

/* ---------- 定位跟踪（单例） ---------- */

let watchId = null;
let lastPos = null;          // {lat, lng, source: 'gps'|'demo'}
const listeners = new Set();

export function getPosition() { return lastPos; }

export function onPosition(fn) {
  listeners.add(fn);
  if (lastPos) fn(lastPos);
  return () => listeners.delete(fn);
}

function emit(pos) {
  lastPos = pos;
  listeners.forEach((fn) => fn(pos));
}

export function startWatch() {
  if (demo.lat !== null) return;             // 演示模式已接管
  if (watchId !== null || !navigator.geolocation) return;
  watchId = navigator.geolocation.watchPosition(
    (p) => emit({ lat: p.coords.latitude, lng: p.coords.longitude, source: "gps" }),
    (err) => {
      // 权限被拒绝时明确广播（与「暂无信号」区分）：UI 引导改用对话锁定景区
      if (err && (err.code === 1 || err.name === "NotAllowedError")) {
        window.dispatchEvent(new CustomEvent("geo:denied"));
      }
    },
    { enableHighAccuracy: true, maximumAge: 4000, timeout: 12000 },
  );
}

export function stopWatch() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
}

/** 演示模式：将虚拟定位钉到指定坐标（现场无信号 / 桌面体验时用）。 */
export function setDemoPosition(lat, lng) {
  demo.lat = lat; demo.lng = lng;
  emit({ lat, lng, source: "demo" });
}

export function clearDemoPosition() {
  demo.lat = null; demo.lng = null;
  lastPos = null;
  startWatch();
}

export function isDemo() { return demo.lat !== null; }
