/** 凉山伴游 · 管理后台单页应用
 *  模块：登录 / 数据概览 / 景区管理 / 点位管理（地图选点）/ 路线管理（排点器）/ 应用设置 / API 说明 / 账号。
 *  约定：全部数据经 /api/admin JWT 接口读写；素材经 /api/admin/uploads 上传后回填 URL。 */

/* eslint-disable no-undef */
const TOKEN_KEY = "banyou:token";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let token = localStorage.getItem(TOKEN_KEY) || "";
let me = null;
const cache = { regions: [], areas: [], spots: [], routes: [] };

/* ================= 基础设施 ================= */

async function api(path, { method = "GET", body, raw } = {}) {
  const res = await fetch("/api/admin" + path, {
    method,
    headers: {
      ...(body && !raw ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? (raw ? body : JSON.stringify(body)) : undefined,
  });
  if (res.status === 401) { showLogin(); throw new Error("登录已过期"); }
  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try { detail = (await res.json()).detail || detail; } catch { /* keep */ }
    throw new Error(detail);
  }
  return res.json();
}

let toastTimer = null;
function toast(msg, ms = 2200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), ms);
}

function icons() { if (window.lucide) lucide.createIcons(); }

function openModal(html) {
  $("#modal").innerHTML = html;
  $("#modal-mask").hidden = false;
  icons();
}
function closeModal() { $("#modal-mask").hidden = true; $("#modal").innerHTML = ""; }
$("#modal-mask").addEventListener("click", (e) => { if (e.target.id === "modal-mask") closeModal(); });

/** 文件上传控件：点击上传并把返回 URL 写进 targetId 输入框。 */
function uploadCell(labelText, targetId, accept) {
  return `
    <div class="full">
      <label>${labelText}</label>
      <div style="display:flex;gap:8px">
        <input id="${targetId}" placeholder="/uploads/… 或留空">
        <button type="button" class="btn ghost sm" data-upload="${targetId}" data-accept="${accept}">上传</button>
      </div>
    </div>`;
}

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-upload]");
  if (!btn) return;
  const input = document.createElement("input");
  input.type = "file";
  input.accept = btn.dataset.accept || "";
  input.onchange = async () => {
    if (!input.files?.[0]) return;
    const fd = new FormData();
    fd.append("file", input.files[0]);
    btn.disabled = true; btn.textContent = "上传中…";
    try {
      const r = await api("/uploads", { method: "POST", body: fd, raw: true });
      $("#" + btn.dataset.upload).value = r.url;
      toast("上传成功");
    } catch (err) { toast(err.message); }
    btn.disabled = false; btn.textContent = "上传";
  };
  input.click();
});

/* ================= 登录 / 布局 ================= */

function showLogin() {
  localStorage.removeItem(TOKEN_KEY);
  token = "";
  $("#main-view").hidden = true;
  $("#login-view").hidden = false;
}

async function doLogin() {
  const username = $("#login-user").value.trim();
  const password = $("#login-pass").value;
  $("#login-err").textContent = "";
  try {
    const r = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "登录失败");
    const data = await r.json();
    token = data.token;
    localStorage.setItem(TOKEN_KEY, token);
    me = data.admin;
    await showMain();
  } catch (err) {
    $("#login-err").textContent = err.message;
  }
}
$("#login-btn").addEventListener("click", doLogin);
$("#login-pass").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
$("#logout-btn").addEventListener("click", showLogin);

async function showMain() {
  $("#login-view").hidden = true;
  $("#main-view").hidden = false;
  await loadBase();
  switchSec("dashboard");
}

/** 拉取区域/景区/点位/路线基础数据（低频，切换模块时按需刷新单项）。 */
async function loadBase() {
  const [regions, areas, spots, routes] = await Promise.all([
    api("/regions"), api("/scenic-areas"), api("/spots"), api("/routes"),
  ]);
  cache.regions = regions.items;
  cache.areas = areas.items;
  cache.spots = spots.items;
  cache.routes = routes.items;
}

const areaName = (id) => cache.areas.find((a) => a.id === id)?.name || `景区#${id}`;

function switchSec(sec) {
  $$("#menu a").forEach((a) => a.classList.toggle("active", a.dataset.sec === sec));
  $$(".sec").forEach((s) => (s.hidden = `sec-${sec}` !== s.id));
  const renderers = {
    dashboard: renderDashboard, areas: renderAreas, spots: renderSpots,
    routes: renderRoutes, products: renderProducts, orders: renderOrders,
    settings: renderSettings,
  };
  (renderers[sec] || (() => {}))();
  icons();
}
$("#menu").addEventListener("click", (e) => {
  const a = e.target.closest("[data-sec]");
  if (a) switchSec(a.dataset.sec);
});

/* ================= 数据概览 ================= */

async function renderDashboard() {
  try {
    const s = await api("/stats");
    me = s.admin;
    $("#stat-cards").innerHTML = `
      <div class="stat-card"><b>${s.scenic_areas}</b><span>收录景区</span></div>
      <div class="stat-card"><b>${s.spots}</b><span>讲解点位</span></div>
      <div class="stat-card"><b>${s.routes}</b><span>伴游路线</span></div>
      <div class="stat-card"><b>${esc(s.admin.display_name)}</b><span>当前账号 ${esc(s.admin.username)}</span></div>`;
  } catch (err) { toast(err.message); }
}

/* ================= 景区管理 ================= */

async function renderAreas() {
  await loadBase();
  $("#area-table").innerHTML = `
    <tr><th>景区</th><th>县市</th><th>等级</th><th>点位/路线</th><th>评分</th><th>状态</th><th>操作</th></tr>
    ${cache.areas.map((a) => `
      <tr>
        <td><b>${esc(a.name)}</b><br><span class="muted">${esc(a.en_name || "")}</span></td>
        <td>${esc(a.city)}</td>
        <td>${esc(a.level || "—")}</td>
        <td>${a.spot_count} / ${a.route_count}</td>
        <td>★ ${a.rating}</td>
        <td>${a.status === 1 ? '<span class="tag">上线</span>' : '<span class="tag off">下线</span>'}</td>
        <td><div class="ops">
          <button class="btn ghost sm" data-edit-area="${a.id}">编辑</button>
          <button class="btn danger sm" data-del-area="${a.id}">删除</button>
        </div></td>
      </tr>`).join("")}`;
}

$("#area-new").addEventListener("click", () => areaForm());
$("#area-table").addEventListener("click", async (e) => {
  const editId = e.target.closest("[data-edit-area]")?.dataset.editArea;
  if (editId) return areaForm(cache.areas.find((a) => a.id === Number(editId)));
  const delId = e.target.closest("[data-del-area]")?.dataset.delArea;
  if (delId && confirm("删除景区会同时删除其点位与路线，确定？")) {
    try { await api(`/scenic-areas/${delId}`, { method: "DELETE" }); toast("已删除"); renderAreas(); }
    catch (err) { toast(err.message); }
  }
});

function areaForm(a = null) {
  openModal(`
    <h3>${a ? "编辑" : "新建"}景区</h3>
    <div class="grid3">
      <div><label>名称 *</label><input id="f-name" value="${esc(a?.name || "")}"></div>
      <div><label>英文名</label><input id="f-en" value="${esc(a?.en_name || "")}"></div>
      <div><label>所属县市</label><input id="f-city" value="${esc(a?.city || "")}" placeholder="西昌市"></div>
      <div><label>等级</label><input id="f-level" value="${esc(a?.level || "")}" placeholder="4A"></div>
      <div><label>区域</label><select id="f-region">${cache.regions.map((r) =>
        `<option value="${r.id}" ${a?.region_id === r.id ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>
      <div><label>评分</label><input id="f-rating" type="number" step="0.1" min="0" max="5" value="${a?.rating ?? 4.5}"></div>
      <div><label>纬度 lat</label><input id="f-lat" type="number" step="0.000001" value="${a?.lat ?? ""}"></div>
      <div><label>经度 lng</label><input id="f-lng" type="number" step="0.000001" value="${a?.lng ?? ""}"></div>
      <div><label>建议游玩(小时)</label><input id="f-hours" type="number" step="0.5" value="${a?.suggested_hours ?? 3}"></div>
      <div><label>地址</label><input id="f-addr" value="${esc(a?.address || "")}"></div>
      <div><label>电话</label><input id="f-tel" value="${esc(a?.tel || "")}"></div>
      <div><label>开放时间</label><input id="f-open" value="${esc(a?.open_time || "")}"></div>
      <div><label>门票信息</label><input id="f-ticket" value="${esc(a?.ticket_info || "")}"></div>
      <div><label>最佳季节</label><input id="f-season" value="${esc(a?.best_season || "")}"></div>
      <div><label>标签(逗号分隔)</label><input id="f-tags" value="${esc((a?.tags || []).join(","))}"></div>
      <div><label>排序(小在前)</label><input id="f-sort" type="number" value="${a?.sort ?? 0}"></div>
      <div><label>状态</label><select id="f-status">
        <option value="1" ${a?.status !== 0 ? "selected" : ""}>上线</option>
        <option value="0" ${a?.status === 0 ? "selected" : ""}>下线</option></select></div>
    </div>
    <label>一句话简介（列表卡片展示）</label>
    <input id="f-short" value="${esc(a?.short_intro || "")}">
    ${uploadCell("封面图", "f-cover", "image/*")}
    <label>详细介绍</label><textarea id="f-intro">${esc(a?.intro || "")}</textarea>
    <div class="modal-foot">
      <button class="btn ghost" onclick="document.getElementById('modal-mask').hidden=true">取消</button>
      <button class="btn" id="f-save">保存</button>
    </div>`);
  $("#f-cover").value = a?.cover_url || "";
  $("#f-save").addEventListener("click", async () => {
    const body = {
      region_id: Number($("#f-region").value),
      name: $("#f-name").value.trim(),
      en_name: $("#f-en").value.trim(),
      city: $("#f-city").value.trim(),
      level: $("#f-level").value.trim(),
      rating: Number($("#f-rating").value) || 4.5,
      lat: Number($("#f-lat").value) || 0,
      lng: Number($("#f-lng").value) || 0,
      suggested_hours: Number($("#f-hours").value) || 2,
      address: $("#f-addr").value.trim(),
      tel: $("#f-tel").value.trim(),
      open_time: $("#f-open").value.trim(),
      ticket_info: $("#f-ticket").value.trim(),
      best_season: $("#f-season").value.trim(),
      tags: $("#f-tags").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      sort: Number($("#f-sort").value) || 0,
      status: Number($("#f-status").value),
      short_intro: $("#f-short").value.trim(),
      cover_url: $("#f-cover").value.trim(),
      intro: $("#f-intro").value.trim(),
    };
    if (!body.name) return toast("名称必填");
    try {
      if (a) await api(`/scenic-areas/${a.id}`, { method: "PUT", body });
      else await api("/scenic-areas", { method: "POST", body });
      closeModal(); toast("已保存"); renderAreas();
    } catch (err) { toast(err.message); }
  });
}

/* ================= 点位管理 ================= */

function fillAreaFilter(sel, onCh) {
  sel.innerHTML = `<option value="">全部景区</option>` +
    cache.areas.map((a) => `<option value="${a.id}">${esc(a.name)}</option>`).join("");
  sel.onchange = onCh;
}

async function renderSpots() {
  await loadBase();
  fillAreaFilter($("#spot-area-filter"), paintSpots);
  paintSpots();
}

function paintSpots() {
  const areaId = Number($("#spot-area-filter").value) || null;
  const items = cache.spots.filter((s) => !areaId || s.scenic_area_id === areaId);
  $("#spot-table").innerHTML = `
    <tr><th>点位</th><th>所属景区</th><th>类别</th><th>坐标</th><th>停留/半径</th><th>讲解</th><th>状态</th><th>操作</th></tr>
    ${items.map((s) => `
      <tr>
        <td><b>${esc(s.name)}</b><br><span class="muted">${esc(s.en_name || "")}</span></td>
        <td>${esc(areaName(s.scenic_area_id))}</td>
        <td>${esc(s.category)}</td>
        <td class="muted">${s.lat.toFixed(4)}, ${s.lng.toFixed(4)}</td>
        <td>${s.stay_minutes}分 / ${s.radius}m</td>
        <td>${(s.narration?.zh || s.audio_url) ? '<span class="tag">已配置</span>' : '<span class="tag off">缺</span>'}</td>
        <td>${s.status === 1 ? '<span class="tag">上线</span>' : '<span class="tag off">下线</span>'}</td>
        <td><div class="ops">
          <button class="btn ghost sm" data-edit-spot="${s.id}">编辑</button>
          <button class="btn danger sm" data-del-spot="${s.id}">删除</button>
        </div></td>
      </tr>`).join("")}`;
}

$("#spot-new").addEventListener("click", () => spotForm());
$("#spot-table").addEventListener("click", async (e) => {
  const editId = e.target.closest("[data-edit-spot]")?.dataset.editSpot;
  if (editId) return spotForm(cache.spots.find((s) => s.id === Number(editId)));
  const delId = e.target.closest("[data-del-spot]")?.dataset.delSpot;
  if (delId && confirm("确定删除该点位？")) {
    try { await api(`/spots/${delId}`, { method: "DELETE" }); toast("已删除"); await loadBase(); paintSpots(); }
    catch (err) { toast(err.message); }
  }
});

function spotForm(s = null) {
  const defaultArea = Number($("#spot-area-filter").value) || cache.areas[0]?.id;
  openModal(`
    <h3>${s ? "编辑" : "新建"}点位</h3>
    <div class="grid3">
      <div><label>点位名称 *</label><input id="s-name" value="${esc(s?.name || "")}"></div>
      <div><label>英文名</label><input id="s-en" value="${esc(s?.en_name || "")}"></div>
      <div><label>所属景区 *</label><select id="s-area">${cache.areas.map((a) =>
        `<option value="${a.id}" ${(s?.scenic_area_id || defaultArea) === a.id ? "selected" : ""}>${esc(a.name)}</option>`).join("")}</select></div>
      <div><label>类别</label><select id="s-cat">${["观景", "文化", "宗教", "生态", "地质", "红色", "体验", "研学", "休闲", "服务"].map((c) =>
        `<option ${s?.category === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
      <div><label>纬度 lat</label><input id="s-lat" type="number" step="0.000001" value="${s?.lat ?? ""}"></div>
      <div><label>经度 lng</label><input id="s-lng" type="number" step="0.000001" value="${s?.lng ?? ""}"></div>
      <div><label>到站触发半径(米)</label><input id="s-radius" type="number" value="${s?.radius ?? 50}"></div>
      <div><label>建议停留(分钟)</label><input id="s-stay" type="number" value="${s?.stay_minutes ?? 15}"></div>
      <div><label>排序</label><input id="s-sort" type="number" value="${s?.sort ?? 0}"></div>
      <div><label>状态</label><select id="s-status">
        <option value="1" ${s?.status !== 0 ? "selected" : ""}>上线</option>
        <option value="0" ${s?.status === 0 ? "selected" : ""}>下线</option></select></div>
    </div>
    <label>中文讲解稿（到站语音播报内容）</label>
    <textarea id="s-zh">${esc(s?.narration?.zh || "")}</textarea>
    <label>English narration（可选）</label>
    <textarea id="s-en">${esc(s?.narration?.en || "")}</textarea>
    <div class="grid2">
      ${uploadCell("人工录音音频（优先于语音合成）", "s-audio", "audio/*").replace('class="full"', 'style="grid-column:auto"')}
      ${uploadCell("点位图片", "s-image", "image/*").replace('class="full"', 'style="grid-column:auto"')}
    </div>
    <label>游览贴士</label><input id="s-tips" value="${esc(s?.tips || "")}">
    <label>地图选点（点击地图设定坐标）</label>
    <div class="mini-map" id="s-map"></div>
    <div class="hint">提示：坐标为 WGS-84（GPS 原始值）；底图坐标系在「应用设置」中配置，前端会自动纠偏。</div>
    <div class="modal-foot">
      <button class="btn ghost" onclick="document.getElementById('modal-mask').hidden=true">取消</button>
      <button class="btn" id="s-save">保存</button>
    </div>`);

  $("#s-audio").value = s?.audio_url || "";
  $("#s-image").value = s?.image_url || "";

  /* 地图选点 */
  const center = s?.lat ? [s.lat, s.lng] : [27.86, 102.27];
  const mmap = L.map("s-map").setView(center, s?.lat ? 15 : 10);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(mmap);
  let pin = null;
  const setPin = (lat, lng) => {
    $("#s-lat").value = lat.toFixed(6);
    $("#s-lng").value = lng.toFixed(6);
    if (!pin) pin = L.marker([lat, lng]).addTo(mmap);
    else pin.setLatLng([lat, lng]);
  };
  if (s?.lat) setPin(s.lat, s.lng);
  mmap.on("click", (e) => setPin(e.latlng.lat, e.latlng.lng));
  setTimeout(() => mmap.invalidateSize(), 80);

  $("#s-save").addEventListener("click", async () => {
    const body = {
      scenic_area_id: Number($("#s-area").value),
      name: $("#s-name").value.trim(),
      en_name: $("#s-en").value.trim(),
      category: $("#s-cat").value,
      lat: Number($("#s-lat").value) || 0,
      lng: Number($("#s-lng").value) || 0,
      radius: Number($("#s-radius").value) || 50,
      stay_minutes: Number($("#s-stay").value) || 15,
      narration: { zh: $("#s-zh").value.trim(), en: $("#s-en").value.trim() },
      audio_url: $("#s-audio").value.trim(),
      image_url: $("#s-image").value.trim(),
      tips: $("#s-tips").value.trim(),
      sort: Number($("#s-sort").value) || 0,
      status: Number($("#s-status").value),
    };
    if (!body.name) return toast("名称必填");
    try {
      if (s) await api(`/spots/${s.id}`, { method: "PUT", body });
      else await api("/spots", { method: "POST", body });
      closeModal(); toast("已保存"); await loadBase(); paintSpots();
    } catch (err) { toast(err.message); }
  });
}

/* ================= 路线管理 ================= */

async function renderRoutes() {
  await loadBase();
  fillAreaFilter($("#route-area-filter"), paintRoutes);
  paintRoutes();
}

function paintRoutes() {
  const areaId = Number($("#route-area-filter").value) || null;
  const items = cache.routes.filter((r) => !areaId || r.scenic_area_id === areaId);
  $("#route-table").innerHTML = `
    <tr><th>路线</th><th>所属景区</th><th>主题/方式</th><th>站点顺序</th><th>时长/里程</th><th>状态</th><th>操作</th></tr>
    ${items.map((r) => `
      <tr>
        <td><b>${esc(r.name)}</b></td>
        <td>${esc(areaName(r.scenic_area_id))}</td>
        <td>${esc(r.theme)} · ${esc(r.mode)}<br><span class="muted">${esc(r.difficulty)}</span></td>
        <td class="muted">${r.stop_names.length ? r.stop_names.map(esc).join(" → ") : "—"}</td>
        <td>${Math.round(r.duration_minutes / 60)}h / ${r.distance_km}km</td>
        <td>${r.status === 1 ? '<span class="tag">上线</span>' : '<span class="tag off">下线</span>'}</td>
        <td><div class="ops">
          <button class="btn ghost sm" data-edit-route="${r.id}">编辑</button>
          <button class="btn danger sm" data-del-route="${r.id}">删除</button>
        </div></td>
      </tr>`).join("")}`;
}

$("#route-new").addEventListener("click", () => routeForm());
$("#route-table").addEventListener("click", async (e) => {
  const editId = e.target.closest("[data-edit-route]")?.dataset.editRoute;
  if (editId) return routeForm(cache.routes.find((r) => r.id === Number(editId)));
  const delId = e.target.closest("[data-del-route]")?.dataset.delRoute;
  if (delId && confirm("确定删除该路线？")) {
    try { await api(`/routes/${delId}`, { method: "DELETE" }); toast("已删除"); await loadBase(); paintRoutes(); }
    catch (err) { toast(err.message); }
  }
});

function routeForm(r = null) {
  const defaultArea = Number($("#route-area-filter").value) || cache.areas[0]?.id;
  const ordered = (r?.stop_ids || []).map((id) => cache.spots.find((s) => s.id === id)).filter(Boolean);
  openModal(`
    <h3>${r ? "编辑" : "新建"}伴游路线</h3>
    <div class="grid3">
      <div><label>路线名称 *</label><input id="r-name" value="${esc(r?.name || "")}"></div>
      <div><label>所属景区 *</label><select id="r-area">${cache.areas.map((a) =>
        `<option value="${a.id}" ${(r?.scenic_area_id || defaultArea) === a.id ? "selected" : ""}>${esc(a.name)}</option>`).join("")}</select></div>
      <div><label>主题</label><select id="r-theme">${["休闲", "人文", "亲子", "研学", "红色", "徒步", "生态"].map((t) =>
        `<option ${r?.theme === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div><label>游览方式</label><input id="r-mode" value="${esc(r?.mode || "步行")}" placeholder="步行/车行+步行/索道+徒步"></div>
      <div><label>难度</label><select id="r-diff">${["轻松", "中等", "进阶"].map((d) =>
        `<option ${r?.difficulty === d ? "selected" : ""}>${d}</option>`).join("")}</select></div>
      <div><label>时长(分钟)</label><input id="r-dur" type="number" value="${r?.duration_minutes ?? 120}"></div>
      <div><label>里程(km)</label><input id="r-km" type="number" step="0.1" value="${r?.distance_km ?? 0}"></div>
      <div><label>排序</label><input id="r-sort" type="number" value="${r?.sort ?? 0}"></div>
      <div><label>状态</label><select id="r-status">
        <option value="1" ${r?.status !== 0 ? "selected" : ""}>上线</option>
        <option value="0" ${r?.status === 0 ? "selected" : ""}>下线</option></select></div>
    </div>
    <label>路线介绍</label><textarea id="r-intro">${esc(r?.intro || "")}</textarea>
    <label>伴游站点（右侧即游客端播报顺序）</label>
    <div class="stops-pick">
      <div><div class="col-title">可选点位（当前景区）</div><ul id="pool"></ul></div>
      <div><div class="col-title">已选顺序</div><ul id="picked"></ul></div>
    </div>
    <div class="modal-foot">
      <button class="btn ghost" onclick="document.getElementById('modal-mask').hidden=true">取消</button>
      <button class="btn" id="r-save">保存</button>
    </div>`);

  let picked = [...ordered];
  const areaSel = $("#r-area");

  const paintPick = () => {
    const areaId = Number(areaSel.value);
    const pool = cache.spots.filter((s) => s.scenic_area_id === areaId && !picked.includes(s));
    $("#pool").innerHTML = pool.length
      ? pool.map((s) => `<li data-add="${s.id}">＋ ${esc(s.name)}<span class="muted"> ${esc(s.category)}</span></li>`).join("")
      : `<li class="muted">该景区暂无点位，请先到「点位管理」创建</li>`;
    $("#picked").innerHTML = picked.length
      ? picked.map((s, i) => `
        <li data-pick="${s.id}">
          <span class="no">${i + 1}</span>${esc(s.name)}
          <span class="mv">
            <button data-up="${i}" ${i === 0 ? "disabled" : ""}>↑</button>
            <button data-down="${i}" ${i === picked.length - 1 ? "disabled" : ""}>↓</button>
            <button data-rm="${i}">×</button>
          </span>
        </li>`).join("")
      : `<li class="muted">从左侧点击加入站点</li>`;
  };
  paintPick();

  areaSel.addEventListener("change", () => { picked = picked.filter((s) => s.scenic_area_id === Number(areaSel.value)); paintPick(); });
  $("#pool").addEventListener("click", (e) => {
    const li = e.target.closest("[data-add]");
    if (!li) return;
    picked.push(cache.spots.find((s) => s.id === Number(li.dataset.add)));
    paintPick();
  });
  $("#picked").addEventListener("click", (e) => {
    const up = e.target.closest("[data-up]")?.dataset.up;
    const down = e.target.closest("[data-down]")?.dataset.down;
    const rm = e.target.closest("[data-rm]")?.dataset.rm;
    if (up !== undefined) { const i = Number(up); [picked[i - 1], picked[i]] = [picked[i], picked[i - 1]]; }
    else if (down !== undefined) { const i = Number(down); [picked[i + 1], picked[i]] = [picked[i], picked[i + 1]]; }
    else if (rm !== undefined) { picked.splice(Number(rm), 1); }
    else return;
    paintPick();
  });

  $("#r-save").addEventListener("click", async () => {
    const body = {
      scenic_area_id: Number(areaSel.value),
      name: $("#r-name").value.trim(),
      theme: $("#r-theme").value,
      mode: $("#r-mode").value.trim() || "步行",
      difficulty: $("#r-diff").value,
      duration_minutes: Number($("#r-dur").value) || 120,
      distance_km: Number($("#r-km").value) || 0,
      sort: Number($("#r-sort").value) || 0,
      status: Number($("#r-status").value),
      intro: $("#r-intro").value.trim(),
    };
    if (!body.name) return toast("名称必填");
    if (!picked.length) return toast("请至少选择一个站点");
    try {
      const saved = r
        ? await api(`/routes/${r.id}`, { method: "PUT", body })
        : await api("/routes", { method: "POST", body });
      const routeId = r ? r.id : saved.id;
      await api(`/routes/${routeId}/stops`, {
        method: "PUT",
        body: { spot_ids: picked.map((s) => s.id) },
      });
      closeModal(); toast("已保存"); await loadBase(); paintRoutes();
    } catch (err) { toast(err.message); }
  });
}

/* ================= 文创商品 ================= */

async function renderProducts() {
  await loadBase();
  const items = (await api("/products")).items;
  const spotName = (id) => cache.spots.find((s) => s.id === id)?.name || `#${id}`;
  $("#product-table").innerHTML = `
    <tr><th>商品</th><th>价格</th><th>关联</th><th>库存</th><th>状态</th><th>操作</th></tr>
    ${items.map((p) => `
      <tr>
        <td><b>${esc(p.name)}</b>${(p.tags || []).length ? `<br>${p.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}` : ""}</td>
        <td>¥${p.price}${p.orig_price > p.price ? `<br><s class="muted">¥${p.orig_price}</s>` : ""}</td>
        <td class="muted">${
          p.spot_ids?.length
            ? `点位：${p.spot_ids.map(spotName).map(esc).join("、")}`
            : p.scenic_area_id ? `景区：${esc(areaName(p.scenic_area_id))}` : "全域好物"
        }</td>
        <td>${p.stock}</td>
        <td>${p.status === 1 ? '<span class="tag">上架</span>' : '<span class="tag off">下架</span>'}</td>
        <td><div class="ops">
          <button class="btn ghost sm" data-edit-product="${p.id}">编辑</button>
          <button class="btn danger sm" data-del-product="${p.id}">删除</button>
        </div></td>
      </tr>`).join("")}`;
}

$("#product-new").addEventListener("click", () => productForm());
$("#product-table").addEventListener("click", async (e) => {
  const editId = e.target.closest("[data-edit-product]")?.dataset.editProduct;
  if (editId) {
    const p = (await api("/products")).items.find((x) => x.id === Number(editId));
    return productForm(p);
  }
  const delId = e.target.closest("[data-del-product]")?.dataset.delProduct;
  if (delId && confirm("确定删除该商品？")) {
    try { await api(`/products/${delId}`, { method: "DELETE" }); toast("已删除"); renderProducts(); }
    catch (err) { toast(err.message); }
  }
});

function productForm(p = null) {
  openModal(`
    <h3>${p ? "编辑" : "新建"}文创商品</h3>
    <div class="grid3">
      <div><label>商品名称 *</label><input id="p-name" value="${esc(p?.name || "")}"></div>
      <div><label>英文名</label><input id="p-en" value="${esc(p?.en_name || "")}"></div>
      <div><label>售价(元) *</label><input id="p-price" type="number" step="0.01" min="0" value="${p?.price ?? ""}"></div>
      <div><label>划线价(0=不展示)</label><input id="p-orig" type="number" step="0.01" min="0" value="${p?.orig_price ?? 0}"></div>
      <div><label>库存</label><input id="p-stock" type="number" min="0" value="${p?.stock ?? 99}"></div>
      <div><label>标签(逗号分隔)</label><input id="p-tags" value="${esc((p?.tags || []).join(","))}"></div>
      <div><label>排序(小在前)</label><input id="p-sort" type="number" value="${p?.sort ?? 0}"></div>
      <div><label>状态</label><select id="p-status">
        <option value="1" ${p?.status !== 0 ? "selected" : ""}>上架</option>
        <option value="0" ${p?.status === 0 ? "selected" : ""}>下架</option></select></div>
      <div><label>关联景区(空=全域好物)</label><select id="p-area">
        <option value="">全域好物</option>
        ${cache.areas.map((a) => `<option value="${a.id}" ${p?.scenic_area_id === a.id ? "selected" : ""}>${esc(a.name)}</option>`).join("")}
      </select></div>
    </div>
    <label>商品介绍</label><textarea id="p-desc">${esc(p?.desc || "")}</textarea>
    ${uploadCell("商品图", "p-image", "image/*")}
    <label>关联点位(勾选后仅在这些点位讲解页露出)</label>
    <div id="p-spot-box" style="display:flex;flex-wrap:wrap;gap:6px 14px;padding:6px 2px;font-size:12.5px"></div>
    <div class="modal-foot">
      <button class="btn ghost" onclick="document.getElementById('modal-mask').hidden=true">取消</button>
      <button class="btn" id="p-save">保存</button>
    </div>`);

  $("#p-image").value = p?.image_url || "";
  let pickedSpots = new Set(p?.spot_ids || []);
  const paintSpots = () => {
    const areaId = Number($("#p-area").value) || null;
    const list = cache.spots.filter((s) => s.scenic_area_id === areaId);
    const box = $("#p-spot-box");
    if (!areaId || !list.length) {
      box.innerHTML = `<span class="muted">${areaId ? "该景区暂无点位" : "全域好物不关联点位（如需关联请先选景区）"}</span>`;
      return;
    }
    box.innerHTML = list.map((s) => `
      <label style="display:flex;gap:4px;align-items:center;cursor:pointer">
        <input type="checkbox" data-pspot="${s.id}" ${pickedSpots.has(s.id) ? "checked" : ""}>${esc(s.name)}
      </label>`).join("");
  };
  paintSpots();
  $("#p-area").addEventListener("change", () => { pickedSpots = new Set(); paintSpots(); });
  $("#p-spot-box").addEventListener("change", (e) => {
    const cb = e.target.closest("[data-pspot]");
    if (!cb) return;
    const id = Number(cb.dataset.pspot);
    cb.checked ? pickedSpots.add(id) : pickedSpots.delete(id);
  });

  $("#p-save").addEventListener("click", async () => {
    const body = {
      name: $("#p-name").value.trim(),
      en_name: $("#p-en").value.trim(),
      price: Number($("#p-price").value) || 0,
      orig_price: Number($("#p-orig").value) || 0,
      desc: $("#p-desc").value.trim(),
      image_url: $("#p-image").value.trim(),
      stock: Number($("#p-stock").value) || 0,
      tags: $("#p-tags").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      scenic_area_id: Number($("#p-area").value) || null,
      spot_ids: [...pickedSpots],
      sort: Number($("#p-sort").value) || 0,
      status: Number($("#p-status").value),
    };
    if (!body.name) return toast("名称必填");
    if (!body.price) return toast("售价必填");
    try {
      if (p) await api(`/products/${p.id}`, { method: "PUT", body });
      else await api("/products", { method: "POST", body });
      closeModal(); toast("已保存"); renderProducts();
    } catch (err) { toast(err.message); }
  });
}

/* ================= 订单管理 ================= */

const ORDER_STATUS = { pending: "待支付", paid: "已支付", shipped: "已发货", cancelled: "已取消" };

async function renderOrders() {
  const status = $("#order-status-filter").value || "";
  const items = (await api("/orders" + (status ? `?status=${status}` : ""))).items;
  $("#order-table").innerHTML = `
    <tr><th>订单</th><th>游客标识</th><th>商品明细</th><th>金额</th><th>状态/渠道</th><th>操作</th></tr>
    ${items.length ? items.map((o) => `
      <tr>
        <td><b>#${o.id}</b><br><span class="muted">${(o.created_at || "").slice(0, 16).replace("T", " ")}</span></td>
        <td class="muted">${esc(o.visitor_id.slice(0, 12))}…</td>
        <td>${o.items.map((it) => `${esc(it.name)} × ${it.qty}`).join("<br>")}</td>
        <td><b>¥${o.total.toFixed(2)}</b></td>
        <td>${ORDER_STATUS[o.status] || o.status}${o.channel ? `<br><span class="muted">${o.channel === "alipay" ? "支付宝" : "微信"}沙盒</span>` : ""}</td>
        <td><div class="ops">
          ${o.status === "paid" ? `<button class="btn ghost sm" data-ship="${o.id}">发货</button>` : ""}
          ${o.status === "pending" || o.status === "paid" ? `<button class="btn danger sm" data-cancel="${o.id}">取消</button>` : ""}
        </div></td>
      </tr>`).join("") : `<tr><td colspan="6" class="muted" style="text-align:center;padding:30px">暂无订单</td></tr>`}`;
}

$("#order-status-filter").addEventListener("change", renderOrders);
$("#order-table").addEventListener("click", async (e) => {
  const ship = e.target.closest("[data-ship]")?.dataset.ship;
  const cancel = e.target.closest("[data-cancel]")?.dataset.cancel;
  if (!ship && !cancel) return;
  if (cancel && !confirm("确定取消该订单？")) return;
  try {
    await api(`/orders/${ship || cancel}`, { method: "PUT", body: { status: ship ? "shipped" : "cancelled" } });
    toast("已更新"); renderOrders();
  } catch (err) { toast(err.message); }
});

/* ================= 应用设置 ================= */

const SETTING_GROUPS = [
  { title: "应用信息", keys: ["app_display_name", "slogan", "announcement", "footer_note", "service_tel"] },
  { title: "地图底图", keys: ["map_tile_url", "map_subdomains", "map_attribution", "map_coord"] },
  { title: "伴游参数", keys: ["default_arrival_radius", "tts_auto_play", "tts_rate"] },
  { title: "首页横幅(JSON)", keys: ["hero_banners"] },
];
const TILE_PRESETS = [
  ["OSM 标准", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "wgs84"],
  ["高德街道", "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", "gcj02"],
  ["高德卫星", "https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}", "gcj02"],
];

let settingsDraft = {};

async function renderSettings() {
  const r = await api("/settings");
  settingsDraft = r.items;
  $("#settings-body").innerHTML = SETTING_GROUPS.map((g) => `
    <div class="set-block">
      <h3>${g.title}</h3>
      <div class="grid2">
        ${g.keys.map((k) => settingField(k, settingsDraft[k])).join("")}
      </div>
      ${g.title === "地图底图" ? `
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
          ${TILE_PRESETS.map((p, i) => `<button class="btn ghost sm" data-preset="${i}">${p[0]}</button>`).join("")}
          <span class="muted">高德瓦片需将坐标系设为 gcj02，前端自动纠偏</span>
        </div>` : ""}
    </div>`).join("");

  $$("[data-setting]").forEach((inp) => {
    inp.addEventListener("change", () => { settingsDraft[inp.dataset.setting] = inp.value; });
  });
  $$("[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const [name, url, coord] = TILE_PRESETS[Number(btn.dataset.preset)];
      settingsDraft.map_tile_url = url;
      settingsDraft.map_coord = coord;
      settingsDraft.map_subdomains = url.includes("{s}") ? "123" : "";
      settingsDraft.map_attribution = `${name} 底图`;
      const urlInput = $(`[data-setting="map_tile_url"]`);
      if (urlInput) urlInput.value = url;
      const coordSel = $(`[data-setting="map_coord"]`);
      if (coordSel) coordSel.value = coord;
      const subInput = $(`[data-setting="map_subdomains"]`);
      if (subInput) subInput.value = settingsDraft.map_subdomains;
      const attrInput = $(`[data-setting="map_attribution"]`);
      if (attrInput) attrInput.value = settingsDraft.map_attribution;
      toast(`已套用「${name}」预设，记得点保存`);
    });
  });
}

function settingField(key, value) {
  const labels = {
    app_display_name: "应用名称", slogan: "标语", announcement: "公告",
    footer_note: "页脚说明", service_tel: "服务电话",
    map_tile_url: "瓦片 URL（支持 {s}{x}{y}{z}）", map_subdomains: "子域字符(如 123)",
    map_attribution: "版权说明", map_coord: "瓦片坐标系",
    default_arrival_radius: "到站触发半径(米)", tts_auto_play: "到站自动播放(1/0)", tts_rate: "默认语速",
    hero_banners: "首页横幅配置",
  };
  if (key === "map_coord") {
    return `<div><label>${labels[key]}</label><select data-setting="${key}">
      <option value="wgs84" ${value === "wgs84" ? "selected" : ""}>wgs84（GPS / OSM）</option>
      <option value="gcj02" ${value === "gcj02" ? "selected" : ""}>gcj02（高德 / 天地图）</option></select></div>`;
  }
  if (key === "tts_auto_play") {
    return `<div><label>${labels[key]}</label><select data-setting="${key}">
      <option value="1" ${value === "1" ? "selected" : ""}>开启</option>
      <option value="0" ${value === "0" ? "selected" : ""}>关闭</option></select></div>`;
  }
  if (key === "announcement" || key === "hero_banners" || key === "slogan") {
    return `<div style="grid-column:1/-1"><label>${labels[key]}</label><textarea data-setting="${key}" rows="2">${esc(value || "")}</textarea></div>`;
  }
  return `<div><label>${labels[key]}</label><input data-setting="${key}" value="${esc(value || "")}"></div>`;
}

$("#settings-save").addEventListener("click", async () => {
  try {
    await api("/settings", { method: "PUT", body: settingsDraft });
    toast("设置已保存，游客端实时生效");
  } catch (err) { toast(err.message); }
});

/* ================= 账号 ================= */

$("#pwd-save").addEventListener("click", async () => {
  try {
    await api("/password", { method: "PUT", body: { old_password: $("#pwd-old").value, new_password: $("#pwd-new").value } });
    $("#pwd-old").value = $("#pwd-new").value = "";
    toast("密码已修改");
  } catch (err) { toast(err.message); }
});

/* ================= 启动 ================= */

(async function init() {
  if (!token) return showLogin();
  try {
    me = await api("/me");
    await showMain();
  } catch { showLogin(); }
})();
