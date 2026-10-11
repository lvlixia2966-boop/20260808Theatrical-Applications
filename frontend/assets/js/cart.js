/* 中国川剧文创旗舰店 · 购物车模块。
 *
 * 高内聚：商品目录提取、购物车状态（localStorage 持久化）、抽屉 UI 全部收敛于此。
 * 低耦合：初始化时自动扫描 #shop-products-grid 内的加购按钮并接管点击，
 *         不侵入页面现有 HTML；结算时仅调用 window.Checkout.open(items)（由 checkout.js 提供）。
 *
 * 对外接口：window.Cart = { add, remove, setQty, count, totalCents, openDrawer, closeDrawer }
 */
(function () {
  'use strict';

  const STORE_KEY = 'chuan_cart';

  const I18N = {
    zh: { title: '购物车', empty: '购物车还是空的，去逛逛吧～', checkout: '去结算', clear: '清空', total: '合计', added: '已加入购物车', cart_upgraded: '购物车已升级，请重新加购' },
    en: { title: 'Cart', empty: 'Your cart is empty.', checkout: 'Checkout', clear: 'Clear', total: 'Total', added: 'Added to cart', cart_upgraded: 'Cart upgraded — please add items again' },
  };
  const t = (k) => (I18N[lang()] && I18N[lang()][k]) || I18N.zh[k] || k;
  function lang() { return (localStorage.getItem('app_lang') || 'zh').startsWith('zh') ? 'zh' : 'en'; }

  /* ── 状态 ─────────────────────────────────────────────── */
  let items = load(); // [{id, name, price_cents, qty}]

  function load() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch { return []; }
  }
  function save() { localStorage.setItem(STORE_KEY, JSON.stringify(items)); refreshBadge(); renderDrawer(); }

  /* ── 商品提取：优先读卡片 data-*（后端化渲染），旧静态卡回退 DOM 解析 ── */
  function productFromCard(card) {
    if (card.dataset.id) {
      return { id: card.dataset.id, name: card.dataset.name || '商品',
               price_cents: parseInt(card.dataset.priceCents || '0', 10) || 0, qty: 1 };
    }
    const img = card.querySelector('img');
    const name = (card.querySelector('h4') || {}).textContent || '商品';
    const priceEl = card.querySelector('.text-lg.font-black');
    const yuan = parseFloat((priceEl ? priceEl.textContent : '0').replace(/[^\d.]/g, '')) || 0;
    const id = img ? (img.getAttribute('src').split('/').pop() || '').replace(/\.\w+$/, '') : name;
    return { id, name: name.trim(), price_cents: Math.round(yuan * 100), qty: 1 };
  }

  /* ── 购物车升级清理：旧版 id 为图片文件名，与新 sku 体系不兼容 ── */
  function legacyCartCleanup() {
    try {
      if (items.some(i => !/^SHOP-\d+/.test(i.id))) {
        items = []; save();
        setTimeout(() => { if (window.showToast) window.showToast('🛒 ' + t('cart_upgraded')); }, 600);
      }
    } catch (e) { /* 忽略 */ }
  }

  /* ── 操作 ─────────────────────────────────────────────── */
  function add(product) {
    const hit = items.find(i => i.id === product.id);
    if (hit) hit.qty += 1; else items.push({ ...product });
    save();
    if (window.showToast) window.showToast(`🛒 ${t('added')}【${product.name}】`);
  }
  function setQty(id, qty) {
    const hit = items.find(i => i.id === id);
    if (!hit) return;
    hit.qty = Math.max(0, qty);
    if (hit.qty === 0) items = items.filter(i => i.id !== id);
    save();
  }
  function clear() { items = []; save(); }
  function count() { return items.reduce((s, i) => s + i.qty, 0); }
  function totalCents() { return items.reduce((s, i) => s + i.price_cents * i.qty, 0); }

  /* ── UI：浮动按钮 + 抽屉（样式自包含注入） ─────────────── */
  const CSS = `
  #cart-fab{position:fixed;right:20px;bottom:88px;z-index:280;width:54px;height:54px;border-radius:50%;
    background:linear-gradient(135deg,#C73E3A,#8B1A1A);color:#FFF9F2;border:none;cursor:pointer;
    box-shadow:0 6px 20px rgba(139,26,26,.45);border:1px solid rgba(224,168,62,.45);
    display:flex;align-items:center;justify-content:center}
  #cart-fab svg{width:24px;height:24px}
  #cart-badge{position:absolute;top:-4px;right:-4px;min-width:20px;height:20px;padding:0 5px;border-radius:999px;
    background:#E0A83E;color:#241610;font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center;
    border:2px solid #fff}
  #cart-drawer-mask{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:290;display:none}
  #cart-drawer{position:fixed;top:0;right:-380px;width:min(380px,92vw);height:100vh;background:#fff;z-index:291;
    transition:right .25s ease;display:flex;flex-direction:column;box-shadow:-8px 0 32px rgba(0,0,0,.12)}
  #cart-drawer.open{right:0}
  .cart-head{padding:16px 20px;border-bottom:1px solid #eee;display:flex;align-items:center;gap:8px}
  .cart-head b{font-size:16px}
  .cart-clear{margin-left:auto;font-size:12px;color:#999;background:none;border:none;cursor:pointer}
  .cart-body{flex:1;overflow-y:auto;padding:8px 20px}
  .cart-empty{text-align:center;color:#bbb;font-size:13px;padding:48px 0}
  .cart-item{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px dashed #eee}
  .cart-item .ci-name{flex:1;font-size:13px;font-weight:600;color:#222;line-height:1.4}
  .cart-item .ci-price{font-size:12px;color:#059669;font-weight:700;margin-top:2px}
  .ci-ctrl{display:flex;align-items:center;gap:8px}
  .ci-ctrl button{width:24px;height:24px;border-radius:6px;border:1px solid #ddd;background:#fafafa;
    font-size:14px;cursor:pointer;line-height:1}
  .ci-ctrl span{min-width:18px;text-align:center;font-size:13px;font-weight:600}
  .cart-foot{padding:16px 20px;border-top:1px solid #eee}
  .cart-total{display:flex;justify-content:space-between;font-size:14px;margin-bottom:12px}
  .cart-total b{color:#059669;font-size:18px}
  .cart-checkout{width:100%;padding:13px;border:none;border-radius:12px;background:#059669;color:#fff;
    font-size:15px;font-weight:700;cursor:pointer}
  .cart-checkout:disabled{opacity:.5;cursor:not-allowed}
  `;

  function buildUI() {
    if (document.getElementById('cart-fab')) return;
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    const fab = document.createElement('button');
    fab.id = 'cart-fab';
    fab.setAttribute('aria-label', 'cart');
    fab.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg><span id="cart-badge">0</span>';
    fab.addEventListener('click', openDrawer);
    document.body.appendChild(fab);

    const mask = document.createElement('div');
    mask.id = 'cart-drawer-mask';
    mask.addEventListener('click', closeDrawer);
    document.body.appendChild(mask);

    const drawer = document.createElement('div');
    drawer.id = 'cart-drawer';
    drawer.innerHTML = `
      <div class="cart-head"><b data-cart="title"></b>
        <button class="cart-clear" data-cart="clear"></button></div>
      <div class="cart-body" data-cart="body"></div>
      <div class="cart-foot">
        <div class="cart-total"><span data-cart="totalLabel"></span><b data-cart="total">¥0.00</b></div>
        <button class="cart-checkout" data-cart="checkout"></button>
      </div>`;
    document.body.appendChild(drawer);

    drawer.querySelector('[data-cart="clear"]').addEventListener('click', () => { clear(); });
    drawer.querySelector('[data-cart="checkout"]').addEventListener('click', () => {
      if (!items.length) return;
      closeDrawer();
      if (window.Checkout) window.Checkout.open(items.map(i => ({ ...i })));
      else if (window.showToast) window.showToast('收银台模块未加载');
    });

    document.addEventListener('app:langchange', () => { renderDrawer(); refreshBadge(); });
    renderDrawer();
    refreshBadge();
    observeViews();
  }

  function renderDrawer() {
    const drawer = document.getElementById('cart-drawer');
    if (!drawer) return;
    drawer.querySelector('[data-cart="title"]').textContent = `🛒 ${t('title')}`;
    drawer.querySelector('[data-cart="clear"]').textContent = t('clear');
    drawer.querySelector('[data-cart="totalLabel"]').textContent = t('total');
    const btn = drawer.querySelector('[data-cart="checkout"]');
    btn.textContent = `${t('checkout')}（${count()}）`;
    btn.disabled = !items.length;
    const body = drawer.querySelector('[data-cart="body"]');
    if (!items.length) {
      body.innerHTML = `<div class="cart-empty">${t('empty')}</div>`;
    } else {
      body.innerHTML = items.map(i => `
        <div class="cart-item">
          <div style="flex:1">
            <div class="ci-name">${i.name}</div>
            <div class="ci-price">¥${(i.price_cents / 100).toFixed(2)}</div>
          </div>
          <div class="ci-ctrl">
            <button data-act="dec" data-id="${i.id}">−</button>
            <span>${i.qty}</span>
            <button data-act="inc" data-id="${i.id}">＋</button>
          </div>
        </div>`).join('');
      body.querySelectorAll('button[data-act]').forEach(b => {
        b.addEventListener('click', () => {
          const hit = items.find(i => i.id === b.dataset.id);
          if (!hit) return;
          setQty(hit.id, hit.qty + (b.dataset.act === 'inc' ? 1 : -1));
        });
      });
    }
    drawer.querySelector('[data-cart="total"]').textContent = `¥${(totalCents() / 100).toFixed(2)}`;
  }

  function refreshBadge() {
    const badge = document.getElementById('cart-badge');
    if (badge) badge.textContent = String(count());
    updateFab();
  }

  /* 浮动球显隐规则：文创视图常显；其他视图（观剧/个人中心）仅有商品时显示 */
  function updateFab() {
    const fab = document.getElementById('cart-fab');
    if (!fab) return;
    const vw = document.getElementById('view-wenchuang');
    const vl = document.getElementById('view-livelisten');
    const onWenchuang = !!vw && !vw.classList.contains('hidden');
    const onListen = !!vl && !vl.classList.contains('hidden'); // 收听席浮球会遮挡字幕/列表
    fab.style.display = (onListen || !(onWenchuang || count() > 0)) ? 'none' : 'flex';
  }

  /* 监听视图容器 class 切换（switchView 只改 hidden），模块自治不侵入页面 */
  function observeViews() {
    const obs = new MutationObserver(updateFab);
    ['view-spectate', 'view-wenchuang', 'view-user-profile'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) obs.observe(el, { attributes: true, attributeFilter: ['class'] });
    });
  }

  function openDrawer() { renderDrawer(); document.getElementById('cart-drawer')?.classList.add('open'); const m = document.getElementById('cart-drawer-mask'); if (m) m.style.display = 'block'; }
  function closeDrawer() { document.getElementById('cart-drawer')?.classList.remove('open'); const m = document.getElementById('cart-drawer-mask'); if (m) m.style.display = 'none'; }

  /* ── 初始化：接管店铺加购按钮（不改页面 HTML） ─────────── */
  function bindShopButtons() {
    const grid = document.getElementById('shop-products-grid');
    if (!grid) return;
    grid.querySelectorAll('button').forEach(btn => {
      if (btn.dataset.cartBound) return;
      const card = btn.closest('[data-shop-cat]');
      if (!card) return;
      btn.dataset.cartBound = '1';
      btn.addEventListener('click', () => add(productFromCard(card)));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { buildUI(); bindShopButtons(); legacyCartCleanup(); });
  } else {
    buildUI();
    bindShopButtons();
    legacyCartCleanup();
  }

  window.Cart = { add, remove: setQty, setQty, count, totalCents, openDrawer, closeDrawer, clear, bindShopButtons };
})();
