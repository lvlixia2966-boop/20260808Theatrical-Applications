/* 视听 × 文创联动（context-shop.js）
 *
 * 「合理推送」三时机（全程零新增弹层）：
 *   1) 演出中：绝技看点卡底部追加一行「相关文创 →」小链接（只在命中映射的绝技出现；
 *      点击跳文创旗舰店，收听 via 耳机不断）
 *   2) 中场休息：情境卡内追加一行「本场上演：…」（由 context-engine 派发 app:live:inter 时注入）
 *   3) 散场：收播卡「把这些带回家」商品条——按本场实际看过的绝技推送 2-3 件相关文创
 *
 * 数据：TERM 商品格映射（静态）；看过的绝技 live-listen 持久化 chuan_seen_terms。
 * 原则：演出中零打扰——不新增任何卡片，只在既有卡片上加一行小字。
 */
(function () {
  'use strict';

  /* 绝技/关键词 → 相关文创（图片均在 assets/products） */
  const MAPPING = [
    { keys: ['变脸', '脸谱', '川剧变脸'], products: [
      { name: { zh: '金脸龙王面具', en: 'Golden Dragon Mask' }, img: './assets/products/mask_gold_dragon.jpg' },
      { name: { zh: '脸谱挂件', en: 'Mask Pendant' }, img: './assets/products/furong_mask_pendant.jpg' },
    ]},
    { keys: ['滚灯', '皮金'], products: [
      { name: { zh: '川剧陶偶摆件', en: 'Opera Pottery Figure' }, img: './assets/products/furong_opera_pottery.jpg' },
    ]},
    { keys: ['吐火', '火'], products: [
      { name: { zh: '武生佩剑工艺剑', en: 'Wusheng Sword Replica' }, img: './assets/products/furong_wusheng_sword.jpg' },
    ]},
    { keys: ['高腔', '帮腔', '声腔', '唱'], products: [
      { name: { zh: '蜀绣双面绣框画', en: 'Shu Embroidery Frame' }, img: './assets/products/furong_embroidery_frame.jpg' },
    ]},
    { keys: ['茶', '盖碗', '长嘴壶'], products: [
      { name: { zh: '盖碗茶具', en: 'Gaiwan Tea Set' }, img: './assets/products/furong_gaiwan_teaset.jpg' },
    ]},
  ];
  const DEFAULT_PRODUCT = { name: { zh: '金脸龙王面具', en: 'Golden Dragon Mask' }, img: './assets/products/mask_gold_dragon.jpg' };

  const I18N = {
    zh: { related: '相关文创', takeHome: '把这些带回家', seen: '本场上演', go: '去逛逛 →' },
    en: { related: 'Related keepsake', takeHome: 'Take tonight home', seen: 'On stage tonight', go: 'Browse →' },
  };
  const lang = () => (localStorage.getItem('app_lang') || 'zh').startsWith('zh') ? 'zh' : 'en';
  const t = (k) => { const d = I18N[lang()] || I18N.en; return d[k] !== undefined ? d[k] : I18N.en[k]; };
  const pick = (o) => o ? (o[lang()] || o.en || o.zh || '') : '';

  /* 一次演出看过的绝技（内存；收播时由 live-listen 落盘） */
  const seen = new Set();

  /* 绝技 → 相关商品（命中的第一组映射；无命中给镇店默认） */
  function productsForTerm(term) {
    const s = String(term || '');
    for (const m of MAPPING) {
      if (m.keys.some(k => s.includes(k))) return m.products;
    }
    return [DEFAULT_PRODUCT];
  }
  /* 看过的绝技集合 → 去重商品列表（≤3） */
  function relatedFromSeen(seenTerms) {
    const out = [];
    const used = new Set();
    for (const term of seenTerms || []) {
      for (const p of productsForTerm(term)) {
        if (!used.has(p.img)) { used.add(p.img); out.push(p); }
      }
      if (out.length >= 3) break;
    }
    return out;
  }

  /* ── 1) 看点卡底部的「相关文创」小链接（由 live-listen 渲染时调用） ── */
  function shopLinkFor(term) {
    const ps = productsForTerm(term);
    return `<a class="hl-shop" href="javascript:void(0)" ` +
           `onclick="event.stopPropagation();switchView('wenchuang');switchWenchuangSubView('cultural-mall',null)">` +
           `${t('related')} · ${escapeHtml(pick(ps[0].name))} →</a>`;
  }

  /* ── 2) 中场卡注入「本场上演」行（context-engine 派发 app:live:inter 时调用） ── */
  function fillInter() {
    const card = document.querySelector('.ctx-card.inter');
    if (!card || card.querySelector('.ctx-seen')) return;
    const terms = [...seen].slice(0, 4);
    if (!terms.length) return;
    const div = document.createElement('div');
    div.className = 'ctx-seen';
    div.textContent = (lang() === 'zh' ? '本场上演：' : 'On stage: ') + terms.join(' · ');
    card.querySelector('.ctx-actions').before(div);
  }

  /* ── 3) 散场商品条（收播卡 #end-shop 容器由 live-listen 提供） ── */
  function fillEndShop() {
    const host = document.getElementById('end-shop');
    if (!host) return;
    const seenTerms = [];
    try { seenTerms.push(...JSON.parse(localStorage.getItem('chuan_seen_terms') || '[]')); } catch (e) {}
    const picks = relatedFromSeen(seenTerms).slice(0, 3);
    if (!picks.length) return;
    host.innerHTML =
      `<div class="es-title">${t('takeHome')}</div>` +
      `<div class="es-row">` + picks.map(p =>
        `<figure class="es-item" onclick="switchView('wenchuang');switchWenchuangSubView('cultural-mall',null)">` +
        `<img src="${p.img}" alt=""><figcaption>${escapeHtml(pick(p.name))}</figcaption></figure>`
      ).join('') + `</div>`;
  }

  function escapeHtml(x) {
    return String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* ── 事件接线 ── */
  window.addEventListener('app:live:highlight', (ev) => {
    const term = ev.detail && ev.detail.term;
    if (term && !seen.has(term)) seen.add(term);
  });
  window.addEventListener('app:live:inter', fillInter);
  window.addEventListener('app:live:ended', () => setTimeout(fillEndShop, 400));

  window.ContextShop = {
    forTerm: productsForTerm,
    shopLinkFor,
    relatedFromSeen,
    fillEndShop,
    seen: () => [...seen],
  };
})();
