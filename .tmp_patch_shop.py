# -*- coding: utf-8 -*-
"""商品后端化 T5-T7：游客端渲染 + 购物车适配 + 管理台商品页（一次性补丁）"""
import io, re

# ============ A. frontend/index.html（T6 游客端渲染） ============
p = 'frontend/index.html'
s = io.open(p, encoding='utf-8').read()

# A1) 静态 8 卡 → 动态容器（保留 grid 类名与加载占位）
gi = s.index('<div id="shop-products-grid"')
sj = s.index('</section>', gi)
grid_line_end = s.index('>', gi) + 1
old_seg = s[gi:sj]
new_seg = ('<div id="shop-products-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">\n'
           '            <div class="stream-empty col-span-full" id="shop-loading">商品加载中…</div>\n'
           '          </div>\n          ')
s = s[:gi] + new_seg + s[sj:]
print('A1) 静态卡移除，改为动态容器 (移除', len(old_seg), '字符)')

# A2) 注入商城渲染 JS（放在「4. 商城产品分类筛选」之前）
anchor = '    // 4. 商城产品分类筛选'
assert s.count(anchor) == 1
block = '''    /* 3.5 商城商品后端化渲染（T6）：/api/shop/products → 卡片网格 */
    let SHOP_ITEMS = [];
    function shopEsc(x) { return String(x ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])); }
    function shopLangPick(p, zhKey, enKey) {
      const lg = localStorage.getItem('app_lang') || 'zh';
      return (lg !== 'zh' && p[enKey]) ? p[enKey] : p[zhKey];
    }
    function shopYuan(cents) { return cents % 100 === 0 ? String(cents / 100) : (cents / 100).toFixed(2); }
    async function loadShopProducts() {
      const grid = document.getElementById('shop-products-grid');
      if (!grid) return;
      grid.innerHTML = '<div class="stream-empty col-span-full" id="shop-loading">商品加载中…</div>';
      try {
        const r = await fetch('/api/shop/products');
        if (!r.ok) throw new Error(r.status);
        SHOP_ITEMS = (await r.json()).data || [];
      } catch (e) {
        grid.innerHTML = '<div class="stream-empty col-span-full">商品暂时无法加载 <button class="underline font-bold" onclick="loadShopProducts()">重试</button></div>';
        return;
      }
      renderShopProducts();
      updateShopCatCounts();
      if (window.Cart && window.Cart.bindShopButtons) window.Cart.bindShopButtons();
    }
    function renderShopProducts() {
      const grid = document.getElementById('shop-products-grid');
      if (!grid) return;
      if (!SHOP_ITEMS.length) { grid.innerHTML = '<div class="stream-empty col-span-full">暂无在售商品</div>'; return; }
      grid.innerHTML = SHOP_ITEMS.map(p => `
        <div data-shop-cat="${p.category}" data-id="${shopEsc(p.sku)}" data-name="${shopEsc(p.name)}" data-price-cents="${p.price_cents}" class="shop-product-card card-modern bg-card border border-border/60 p-4 hover:border-primary/60 transition-all flex flex-col justify-between group">
          <div>
            <div class="relative overflow-hidden rounded-xl aspect-square mb-3 border border-border">
              <img src="${shopEsc(p.image_url)}" alt="${shopEsc(p.name)}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
              ${p.badge ? `<span class="absolute top-2 right-2 px-2 py-0.5 bg-black/70 text-white text-[11px] rounded font-bold">${shopEsc(p.badge)}</span>` : ''}
            </div>
            <h4 class="font-bold text-sm text-foreground mb-1">${shopEsc(shopLangPick(p, 'name', 'name_en'))}</h4>
            <p class="text-[11px] text-muted-foreground line-clamp-2 mb-2">${shopEsc(shopLangPick(p, 'description', 'description_en'))}</p>
            <div class="text-lg font-black text-primary mb-3">¥ ${shopYuan(p.price_cents)}</div>
          </div>
          <button class="w-full py-2.5 bg-primary text-white text-xs font-bold rounded-xl hover:bg-primary/90 transition-all flex items-center justify-center gap-1.5 shadow-sm">
            <i data-lucide="shopping-cart" class="w-3.5 h-3.5"></i> 加入购物车
          </button>
        </div>`).join('');
      if (window.lucide) lucide.createIcons();
    }
    function updateShopCatCounts() {
      document.querySelectorAll('.shop-cat-btn').forEach(btn => {
        const m = (btn.getAttribute('onclick') || '').match(/filterShopProducts\\('([a-z]+)'/);
        if (!m) return;
        const n = m[1] === 'all' ? SHOP_ITEMS.length : SHOP_ITEMS.filter(p => p.category === m[1]).length;
        const nodes = [...btn.childNodes].filter(nd => nd.nodeType === 3 && /\\(\\d+\\)/.test(nd.nodeValue));
        if (nodes.length) nodes[nodes.length - 1].nodeValue = nodes[nodes.length - 1].nodeValue.replace(/\\(\\d+\\)/, `(${n})`);
      });
    }
    window.addEventListener('app:langchange', () => { if (SHOP_ITEMS.length) renderShopProducts(); });
    loadShopProducts();

'''
s = s.replace(anchor, block + anchor)

# A3) cart.js 缓存版本 bump
s = s.replace('cart.js?v=20260910', 'cart.js?v=20260929')
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('A) index.html 完成 (T6 + 版本 bump)')

# ============ B. frontend/assets/js/cart.js（T7 适配） ============
p = 'frontend/assets/js/cart.js'
s = io.open(p, encoding='utf-8').read()

old = """  /* ── 商品提取：从店铺卡片 DOM 读取 id/名称/价格 ────────── */
  function productFromCard(card) {
    const img = card.querySelector('img');
    const name = (card.querySelector('h4') || {}).textContent || '商品';
    const priceEl = card.querySelector('.text-lg.font-black');
    const yuan = parseFloat((priceEl ? priceEl.textContent : '0').replace(/[^\\d.]/g, '')) || 0;
    const id = img ? (img.getAttribute('src').split('/').pop() || '').replace(/\\.\\w+$/, '') : name;
    return { id, name: name.trim(), price_cents: Math.round(yuan * 100), qty: 1 };
  }"""
new = """  /* ── 商品提取：优先读卡片 data-*（后端化渲染），旧静态卡回退 DOM 解析 ── */
  function productFromCard(card) {
    if (card.dataset.id) {
      return { id: card.dataset.id, name: card.dataset.name || '商品',
               price_cents: parseInt(card.dataset.priceCents || '0', 10) || 0, qty: 1 };
    }
    const img = card.querySelector('img');
    const name = (card.querySelector('h4') || {}).textContent || '商品';
    const priceEl = card.querySelector('.text-lg.font-black');
    const yuan = parseFloat((priceEl ? priceEl.textContent : '0').replace(/[^\\d.]/g, '')) || 0;
    const id = img ? (img.getAttribute('src').split('/').pop() || '').replace(/\\.\\w+$/, '') : name;
    return { id, name: name.trim(), price_cents: Math.round(yuan * 100), qty: 1 };
  }

  /* ── 购物车升级清理：旧版 id 为图片文件名，与新 sku 体系不兼容 ── */
  function legacyCartCleanup() {
    try {
      if (items.some(i => !/^SHOP-\\d+/.test(i.id))) {
        items = []; save();
        setTimeout(() => { if (window.showToast) window.showToast('🛒 ' + t('cart_upgraded')); }, 600);
      }
    } catch (e) { /* 忽略 */ }
  }"""
assert s.count(old) == 1
s = s.replace(old, new)

# I18N 加 cart_upgraded
old = "zh: { title: '购物车', empty: '购物车还是空的，去逛逛吧～', checkout: '去结算', clear: '清空', total: '合计', added: '已加入购物车' },"
new = "zh: { title: '购物车', empty: '购物车还是空的，去逛逛吧～', checkout: '去结算', clear: '清空', total: '合计', added: '已加入购物车', cart_upgraded: '购物车已升级，请重新加购' },"
assert s.count(old) == 1
s = s.replace(old, new)
old = "en: { title: 'Cart', empty: 'Your cart is empty.', checkout: 'Checkout', clear: 'Clear', total: 'Total', added: 'Added to cart' },"
new = "en: { title: 'Cart', empty: 'Your cart is empty.', checkout: 'Checkout', clear: 'Clear', total: 'Total', added: 'Added to cart', cart_upgraded: 'Cart upgraded — please add items again' },"
assert s.count(old) == 1
s = s.replace(old, new)

# 初始化两分支挂 legacyCartCleanup + 导出 bindShopButtons
old = """  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { buildUI(); bindShopButtons(); });
  } else {
    buildUI();
    bindShopButtons();
  }

  window.Cart = { add, remove: setQty, setQty, count, totalCents, openDrawer, closeDrawer, clear };"""
new = """  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { buildUI(); bindShopButtons(); legacyCartCleanup(); });
  } else {
    buildUI();
    bindShopButtons();
    legacyCartCleanup();
  }

  window.Cart = { add, remove: setQty, setQty, count, totalCents, openDrawer, closeDrawer, clear, bindShopButtons };"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('B) cart.js 完成 (T7)')

# ============ C. admin/index.html（T5 管理台商品页） ============
p = 'admin/index.html'
s = io.open(p, encoding='utf-8').read()

# C1) 导航项
old = '<a data-nav="voices"><span class="nav-icon">♪</span><span class="lbl">音色管理</span></a>'
new = old + '\n      <a data-nav="products"><span class="nav-icon">▩</span><span class="lbl">商品管理</span></a>'
assert s.count(old) == 1
s = s.replace(old, new)

# C2) editId
old = 'let editId = { program: null, earphone: null, liveShow: null };'
new = 'let editId = { program: null, earphone: null, liveShow: null, product: null };'
assert s.count(old) == 1
s = s.replace(old, new)

# C3) titles/eyebrows/dispatch
old = "const titles={programs:'节目管理',"
assert s.count(old) == 1
s = s.replace(old, "const titles={products:'商品管理',programs:'节目管理',")
old = "earphones:'耳机管理',voices:'音色管理'};"
assert s.count(old) == 1
s = s.replace(old, "earphones:'耳机管理',voices:'音色管理',products:'商品管理'};")
old = "eyebrows={programs:'PROGRAMS · 内容运营',"
assert s.count(old) == 1
s = s.replace(old, "eyebrows={products:'SHOP · 文创商品',programs:'PROGRAMS · 内容运营',")
old = "voices:'VOICE · 语音资产'};"
assert s.count(old) == 1
s = s.replace(old, "voices:'VOICE · 语音资产',products:'SHOP · 文创商品'};")
old = "else if(nav==='voices')renderVoices();\n}"
assert s.count(old) == 1
s = s.replace(old, "else if(nav==='voices')renderVoices();\n  else if(nav==='products')renderProducts();\n}")

# C4) 商品管理函数块（插在 showNav 之后）
anchor = "  else if(nav==='voices')renderVoices();\n  else if(nav==='products')renderProducts();\n}"
assert s.count(anchor) == 1
block = anchor + """

// ---------- 商品管理 ----------
let prodList = [];
function shopImgUrl(u) { return (u || '').startsWith('./') ? '/' + u.slice(2) : (u || ''); }
const PR_CAT = { embroidery: '蜀绣丝绸', accessory: '非遗饰品', lacquer: '手绘漆器', bamboo: '竹编文房' };
async function renderProducts(){
  document.getElementById('header-actions').innerHTML = '<button class="btn" onclick="openProductModal()">+ 新增商品</button>';
  const box = document.getElementById('page-content');
  box.innerHTML = '<div class="empty">加载中...</div>';
  try{
    const j = await api('/admin/products');
    prodList = j.data || [];
    if(!prodList.length){ box.innerHTML = '<div class="empty">暂无商品，点右上角新增</div>'; return; }
    box.innerHTML = `<div class="card"><table><tr><th>图</th><th>SKU</th><th>名称</th><th>分类</th><th>价格</th><th>排序</th><th>状态</th><th>操作</th></tr>
      ${prodList.map(p => `<tr>
        <td><img src="${esc(shopImgUrl(p.image_url))}" style="width:44px;height:44px;object-fit:cover;border-radius:8px" onerror="this.style.visibility='hidden'"></td>
        <td><small>${esc(p.sku)}</small></td>
        <td><b>${esc(p.name)}</b>${p.name_en ? `<br><small style="color:var(--muted)">${esc(p.name_en)}</small>` : ''}</td>
        <td>${PR_CAT[p.category] || p.category}</td>
        <td>¥${(p.price_cents/100).toFixed(p.price_cents % 100 ? 2 : 0)}${p.orig_price_cents ? ` <small style="color:var(--muted);text-decoration:line-through">¥${(p.orig_price_cents/100).toFixed(2)}</small>` : ''}</td>
        <td>${p.sort}</td>
        <td><span class="badge ${p.status === 1 ? 'on' : 'off'}">${p.status === 1 ? '已上架' : '已下架'}</span></td>
        <td><div class="actions">
          <button class="btn sm ghost" onclick="openProductModal(${p.id})">编辑</button>
          <button class="btn sm ghost" onclick="toggleProduct(${p.id})">${p.status === 1 ? '下架' : '上架'}</button>
        </div></td></tr>`).join('')}</table></div>`;
  }catch(e){ box.innerHTML = `<div class="empty">${e.message}</div>`; }
}
function openProductModal(id){
  editId.product = id || null;
  document.getElementById('product-modal-title').textContent = id ? '编辑商品' : '新增商品';
  ['pr-name','pr-name-en','pr-price','pr-orig','pr-badge','pr-stock','pr-sort','pr-desc','pr-desc-en'].forEach(n => document.getElementById(n).value = '');
  document.getElementById('pr-img').style.visibility = 'hidden';
  document.getElementById('pr-file').value = '';
  if(id){
    const p = prodList.find(x => x.id === id);
    if(p){
      document.getElementById('pr-name').value = p.name;
      document.getElementById('pr-name-en').value = p.name_en || '';
      document.getElementById('pr-cat').value = p.category;
      document.getElementById('pr-price').value = (p.price_cents / 100).toFixed(2);
      document.getElementById('pr-orig').value = p.orig_price_cents != null ? (p.orig_price_cents / 100).toFixed(2) : '';
      document.getElementById('pr-badge').value = p.badge || '';
      document.getElementById('pr-stock').value = p.stock != null ? p.stock : '';
      document.getElementById('pr-sort').value = p.sort;
      document.getElementById('pr-status').value = String(p.status);
      document.getElementById('pr-desc').value = p.description || '';
      document.getElementById('pr-desc-en').value = p.description_en || '';
      const img = document.getElementById('pr-img');
      if(p.image_url){ img.src = shopImgUrl(p.image_url); img.style.visibility = 'visible'; }
    }
  }
  document.getElementById('product-modal').classList.remove('hidden');
}
function closeProductModal(){ document.getElementById('product-modal').classList.add('hidden'); }
async function saveProduct(){
  const price = Math.round(parseFloat(document.getElementById('pr-price').value || '0') * 100);
  if(!document.getElementById('pr-name').value.trim() || !(price >= 0)) { toast('名称与售价必填'); return; }
  const orig = parseFloat(document.getElementById('pr-orig').value);
  const stock = document.getElementById('pr-stock').value;
  const body = {
    name: document.getElementById('pr-name').value.trim(),
    name_en: document.getElementById('pr-name-en').value.trim(),
    category: document.getElementById('pr-cat').value,
    price_cents: price,
    orig_price_cents: isNaN(orig) ? null : Math.round(orig * 100),
    badge: document.getElementById('pr-badge').value.trim(),
    stock: stock === '' ? null : parseInt(stock, 10),
    sort: parseInt(document.getElementById('pr-sort').value || '0', 10),
    status: parseInt(document.getElementById('pr-status').value, 10),
    description: document.getElementById('pr-desc').value,
    description_en: document.getElementById('pr-desc-en').value,
  };
  try{
    if(editId.product){ await api('/admin/products/' + editId.product, 'PUT', body); }
    else { await api('/admin/products', 'POST', body); }
    closeProductModal();
    toast('已保存');
    renderProducts();
  }catch(e){ toast(e.message); }
}
async function toggleProduct(id){
  const p = prodList.find(x => x.id === id);
  if(!p) return;
  try{ await api('/admin/products/' + id, 'PUT', { status: p.status === 1 ? 0 : 1 }); renderProducts(); }
  catch(e){ toast(e.message); }
}
async function uploadProductImage(){
  const id = editId.product;
  if(!id){ toast('请先保存商品后再上传图片'); return; }
  const f = document.getElementById('pr-file').files[0];
  if(!f){ toast('请选择图片文件'); return; }
  const fd = new FormData(); fd.append('file', f);
  try{
    const r = await fetch(API + '/admin/products/' + id + '/image', { method: 'POST', headers: { 'Authorization': 'Bearer ' + TOKEN }, body: fd });
    const j = await r.json();
    if(j.data && j.data.image_url){
      const img = document.getElementById('pr-img');
      img.src = shopImgUrl(j.data.image_url) + '?t=' + Date.now(); img.style.visibility = 'visible';
      const p = prodList.find(x => x.id === id); if(p) p.image_url = j.data.image_url;
      toast('图片已更新');
    } else { toast(j.detail || '上传失败'); }
  }catch(e){ toast('上传失败'); }
}"""
s = s.replace(anchor, block)

# C5) 弹窗 HTML（插在二维码脚本之前）
old = '<script src="./assets/qrcode.js"></script>'
assert s.count(old) == 1
modal = '''<div id="product-modal" class="modal hidden">
  <div class="modal-box">
    <h3 id="product-modal-title">新增商品</h3>
    <div class="form-grid">
      <div class="full"><label>商品名称 *</label><input id="pr-name" maxlength="128"></div>
      <div class="full"><label>英文名称</label><input id="pr-name-en" maxlength="128"></div>
      <div><label>分类</label>
        <select id="pr-cat">
          <option value="accessory">非遗饰品</option>
          <option value="embroidery">蜀绣丝绸</option>
          <option value="lacquer">手绘漆器</option>
          <option value="bamboo">竹编文房</option>
        </select>
      </div>
      <div><label>售价(元) *</label><input id="pr-price" type="number" min="0" step="0.01"></div>
      <div><label>划线原价(元)</label><input id="pr-orig" type="number" min="0" step="0.01"></div>
      <div><label>角标</label><input id="pr-badge" maxlength="32" placeholder="如：非遗工艺"></div>
      <div><label>库存(留空=不限)</label><input id="pr-stock" type="number" min="0"></div>
      <div><label>排序</label><input id="pr-sort" type="number"></div>
      <div><label>状态</label>
        <select id="pr-status"><option value="1">已上架</option><option value="0">已下架</option></select>
      </div>
      <div class="full"><label>中文描述</label><textarea id="pr-desc" rows="2"></textarea></div>
      <div class="full"><label>英文描述</label><textarea id="pr-desc-en" rows="2"></textarea></div>
      <div class="full"><label>商品图片</label>
        <div style="display:flex;gap:12px;align-items:center">
          <img id="pr-img" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid var(--border)">
          <input id="pr-file" type="file" accept=".jpg,.jpeg,.png,.webp">
          <button class="btn sm ghost" onclick="uploadProductImage()">上传</button>
        </div>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn ghost" onclick="closeProductModal()">取消</button>
      <button class="btn" onclick="saveProduct()">保存</button>
    </div>
  </div>
</div>

''' + old
s = s.replace(old, modal)
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('C) admin/index.html 完成 (T5)')

import subprocess, shutil
for f in ['frontend/assets/js/cart.js']:
    if shutil.which('node'):
        r = subprocess.run(['node', '--check', f], capture_output=True, text=True)
        print('node --check', f, ':', 'OK' if r.returncode == 0 else r.stderr[:300])
