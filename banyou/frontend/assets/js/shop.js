/** 手边好物：不打扰的文创售卖层。
 *
 *  原则落地：
 *  - 伴游进行中（walk 模式）入口完全隐藏，全程零商业元素；
 *  - 入口为角落一枚低调圆形按钮，点开是底部浮层，不离开当前页面；
 *  - 点位讲解页仅在有关联好物时出现一行小条，点击展开同一浮层；
 *  - 下单无购物车、无注册，直接购买，沙盒支付一键完成。
 */

import { createOrder, getMyOrders, getProducts, payOrder } from "./api.js";
import { el, esc, refreshIcons, toast, vibrate } from "./ui.js";

let fab = null;
let mask = null;
let sheet = null;

/* ---------- 挂载 ---------- */

export function initShop() {
  // 单页版：好物入口在对话页标题栏（openShop 由其调用），不再使用浮动按钮
  mask = el(`<div class="shop-mask" id="shop-mask" hidden></div>`);
  sheet = el(`<div class="shop-sheet" id="shop-sheet" hidden></div>`);
  mask.addEventListener("click", closeShop);
  document.body.append(mask, sheet);
}

/** 伴游模式切换（兼容旧调用）：单页版无独立伴游页，保持空操作。 */
export function setWalkMode(_walk) { /* 单页版入口固定在标题栏 */ }

/* ---------- 浮层开关 ---------- */

function openSheet() {
  mask.hidden = false;
  sheet.hidden = false;
  void sheet.offsetWidth;   // 强制 reflow：保证关闭→展开过渡从初始态开始
  mask.classList.add("show");
  sheet.classList.add("show");
}

export function closeShop() {
  if (!sheet || sheet.hidden) return;
  mask.classList.remove("show");
  sheet.classList.remove("show");
  setTimeout(() => { mask.hidden = true; sheet.hidden = true; }, 260);
}

/* ---------- 列表 ---------- */

export async function openShop({ spotId, areaId, spotName } = {}) {
  openSheet();
  sheet.innerHTML = `<div class="shop-loading">好物上架中…</div>`;
  const [ctx, all] = await Promise.all([
    spotId ? getProducts({ spot_id: spotId }).catch(() => ({ items: [] })) : Promise.resolve({ items: [] }),
    getProducts().catch(() => ({ items: [] })),
  ]);
  const ctxItems = ctx.items;
  const ctxIds = new Set(ctxItems.map((p) => p.id));
  const more = all.items;

  const ph = (p, i) => p.image_url
    ? `<img src="${esc(p.image_url)}" alt="" loading="lazy">`
    : `<div class="ph-char ph-${i % 6}">${esc(p.name[0] || "物")}</div>`;

  const card = (p, i) => `
    <div class="shop-card" data-pid="${p.id}">
      <div class="cover">${ph(p, i)}${p.orig_price > p.price ? `<span class="off">省 ¥${(p.orig_price - p.price).toFixed(0)}</span>` : ""}</div>
      <div class="body">
        <b>${esc(p.name)}</b>
        <div class="price">¥${p.price.toFixed(p.price % 1 ? 2 : 0)}
          ${p.orig_price > p.price ? `<s>¥${p.orig_price.toFixed(0)}</s>` : ""}</div>
      </div>
    </div>`;

  sheet.innerHTML = `
    <div class="shop-head">
      <b>手边好物</b>
      ${spotName ? `<span class="muted">${esc(spotName)} · 就在附近</span>` : "<span class='muted'>凉山风物 · 需要时就在手边</span>"}
      <button class="close" id="shop-close" aria-label="关闭"><i data-lucide="x"></i></button>
    </div>
    <div class="shop-body">
      ${ctxItems.length ? `
        <div class="shop-sec-title"><i data-lucide="map-pin"></i>这里的好物</div>
        <div class="shop-scroll">
          ${ctxItems.map((p, i) => card(p, i)).join("")}
        </div>` : ""}
      <div class="shop-sec-title"><i data-lucide="sparkles"></i>${ctxItems.length ? "更多好物" : "全部好物"}</div>
      <div class="shop-grid">
        ${more.map((p, i) => card(p, i + (ctxItems.length ? 3 : 0))).join("")}
      </div>
      <div class="shop-foot-note">沙盒演示 · 不产生真实交易</div>
    </div>`;
  refreshIcons();

  sheet.querySelector("#shop-close").addEventListener("click", closeShop);
  sheet.addEventListener("click", (e) => {
    const c = e.target.closest("[data-pid]");
    if (!c) return;
    const p = more.find((x) => x.id === Number(c.dataset.pid))
      || ctxItems.find((x) => x.id === Number(c.dataset.pid));
    if (p) renderDetail(p);
  });
}

/* ---------- 详情 + 购买 ---------- */

function renderDetail(p) {
  sheet.innerHTML = `
    <div class="shop-head">
      <button class="close" id="shop-back" aria-label="返回"><i data-lucide="chevron-left"></i></button>
      <b>商品详情</b><span></span>
    </div>
    <div class="shop-body detail">
      <div class="shop-hero ph-2"><span class="ph-char">${esc(p.name[0] || "物")}</span>
        ${p.image_url ? `<img src="${esc(p.image_url)}" alt="">` : ""}</div>
      <div class="d-name">${esc(p.name)}</div>
      <div class="d-price">¥${p.price.toFixed(p.price % 1 ? 2 : 0)}
        ${p.orig_price > p.price ? `<s>¥${p.orig_price.toFixed(0)}</s>` : ""}
        ${(p.tags || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
      <p class="d-desc">${esc(p.desc || "")}</p>
      <div class="d-stock">库存 ${p.stock > 0 ? p.stock + " 件" : "紧张，请咨询现场"}</div>
      <div class="d-buybar">
        <div class="stepper">
          <button id="q-dec" ${qty <= 1 ? "disabled" : ""}>−</button><b id="q-val">${qty}</b>
          <button id="q-inc">＋</button>
        </div>
        <button class="btn" id="buy-btn" ${p.stock <= 0 ? "disabled" : ""}>
          立即购买 · ¥${(p.price * qty).toFixed(p.price % 1 ? 2 : 0)}</button>
      </div>
    </div>`;
  refreshIcons();

  sheet.querySelector("#shop-back").addEventListener("click", () => openShop({ spotId: lastCtx.spotId, areaId: lastCtx.areaId, spotName: lastCtx.spotName }));
  const paint = (q) => {
    sheet.querySelector("#q-val").textContent = q;
    sheet.querySelector("#q-dec").disabled = q <= 1;
    sheet.querySelector("#buy-btn").innerHTML =
      `立即购买 · ¥${(p.price * q).toFixed(p.price % 1 ? 2 : 0)}`;
  };
  sheet.querySelector("#q-dec").addEventListener("click", () => { qty = Math.max(1, qty - 1); paint(qty); });
  sheet.querySelector("#q-inc").addEventListener("click", () => { qty = Math.min(20, qty + 1); paint(qty); });
  sheet.querySelector("#buy-btn").addEventListener("click", () => renderPay(p, qty));
}

let qty = 1;
let lastCtx = {};

/* ---------- 沙盒收银 ---------- */

function renderPay(p, q) {
  const total = (p.price * q).toFixed(p.price % 1 ? 2 : 2);
  sheet.innerHTML = `
    <div class="shop-head"><b>确认支付</b><span></span>
      <button class="close" id="shop-close" aria-label="关闭"><i data-lucide="x"></i></button></div>
    <div class="shop-body detail">
      <div class="pay-sum">
        <div class="row"><span>${esc(p.name)} × ${q}</span><b>¥${total}</b></div>
        <div class="row total"><span>合计</span><b>¥${total}</b></div>
      </div>
      <div class="pay-channels">
        <button class="channel" data-ch="wechat"><i data-lucide="message-circle"></i>微信支付<span class="muted">沙盒</span></button>
        <button class="channel" data-ch="alipay"><i data-lucide="wallet"></i>支付宝<span class="muted">沙盒</span></button>
      </div>
      <button class="btn block" id="pay-btn" disabled>请选择支付方式</button>
      <div class="shop-foot-note">沙盒演示 · 点击即模拟支付成功，不产生真实交易</div>
    </div>`;
  refreshIcons();
  let channel = "";
  sheet.querySelectorAll(".channel").forEach((b) => b.addEventListener("click", () => {
    channel = b.dataset.ch;
    sheet.querySelectorAll(".channel").forEach((x) => x.classList.toggle("sel", x === b));
    sheet.querySelector("#pay-btn").disabled = false;
    sheet.querySelector("#pay-btn").textContent = `确认支付 ¥${total}`;
  }));
  sheet.querySelector("#shop-close").addEventListener("click", closeShop);
  sheet.querySelector("#pay-btn").addEventListener("click", async () => {
    const btn = sheet.querySelector("#pay-btn");
    btn.disabled = true;
    btn.textContent = "支付中…";
    try {
      const order = await createOrder([{ product_id: p.id, qty: q }]);
      await new Promise((r) => setTimeout(r, 900));           // 模拟收银台
      const paid = await payOrder(order.id, channel);
      vibrate();
      renderSuccess(paid);
    } catch (err) {
      toast(err.message);
      btn.disabled = false;
      btn.textContent = `确认支付 ¥${total}`;
    }
  });
}

function renderSuccess(order) {
  sheet.innerHTML = `
    <div class="shop-body detail success">
      <div class="ok-ring"><i data-lucide="check"></i></div>
      <b>支付成功</b>
      <div class="muted">订单号 #${order.id} · ¥${order.total.toFixed(2)} · ${order.channel === "alipay" ? "支付宝" : "微信"}（沙盒）</div>
      <p class="d-desc">商品可在离园时于文创柜台凭证号领取，或选择邮寄到家。</p>
      <button class="btn block" id="ok-btn">完成</button>
      <button class="btn block line" id="orders-btn">查看我的订单</button>
    </div>`;
  refreshIcons();
  sheet.querySelector("#ok-btn").addEventListener("click", closeShop);
  sheet.querySelector("#orders-btn").addEventListener("click", openOrders);
}

/* ---------- 我的订单 ---------- */

export async function openOrders() {
  openSheet();
  sheet.innerHTML = `<div class="shop-loading">订单查询中…</div>`;
  let items = [];
  try { items = (await getMyOrders()).items; } catch { /* 忽略 */ }
  const STATUS = { pending: ["待支付", "gold"], paid: ["已支付", ""], shipped: ["已发货", ""], cancelled: ["已取消", "off"] };
  sheet.innerHTML = `
    <div class="shop-head"><b>我的订单</b><span class="muted">仅保留在本机</span>
      <button class="close" id="shop-close" aria-label="关闭"><i data-lucide="x"></i></button></div>
    <div class="shop-body">
      ${items.length ? items.map((o) => `
        <div class="order-card">
          <div class="o-head"><b>订单 #${o.id}</b>
            <span class="chip ${STATUS[o.status]?.[1] || ""}">${STATUS[o.status]?.[0] || o.status}</span></div>
          ${o.items.map((it) => `<div class="o-item"><span>${esc(it.name)} × ${it.qty}</span><b>¥${(it.price * it.qty).toFixed(2)}</b></div>`).join("")}
          <div class="o-foot">合计 <b>¥${o.total.toFixed(2)}</b></div>
        </div>`).join("")
      : `<div class="shop-loading">还没有订单 — 好物会安安静静等你</div>`}
    </div>`;
  refreshIcons();
  sheet.querySelector("#shop-close").addEventListener("click", closeShop);
}
