/* 文创视图 · 中国川剧磁贴面板（wenchuang-launcher.js）
 *
 * 把文创 11 个子板块重组为「中国川剧」磁贴菜单：进入文创默认见面板，
 * 点磁贴进入对应板块；板块内保留原子导航（可直接互跳）+「← 中国川剧」返回钮。
 *
 * 低耦合实现：注入面板 DOM；包装全局 switchWenchuangSubView（先原逻辑后切面板可见性）；
 * MutationObserver 监听 #view-wenchuang 显隐（进入文创且无目标子视图时回面板）；
 * 磁贴名称取自子导航按钮的 data-i18n 文案（自动跟随 7 语切换）；简介 zh/en。
 */
(function () {
  'use strict';

  /* 面板磁贴定义（name 走子导航 data-i18n 文案；desc zh/en） */
  const TILES = [
    { id: 'asset-library',   icon: 'database',     status: 'live', desc: { zh: '非遗数字资产与 AI 提示词 IP 授权库', en: 'Heritage digital assets & AI prompt licensing' } },
    { id: 'cultural-mall',   icon: 'shopping-bag', status: 'live', desc: { zh: '川剧文创好物 · 购物车与收银台', en: 'Cultural merchandise with cart & checkout' } },
    { id: 'ai-photoshoot',   icon: 'camera',       status: 'live', desc: { zh: '一键换装，生成你的川剧旅拍', en: 'AI opera photoshoot with one-tap outfit swap' } },
    { id: 'shopping-spots',  icon: 'map-pin',      status: 'live', desc: { zh: '散场去哪逛：剧院内外 6 处好去处', en: 'Six spots in and around the theatre' } },
    { id: 'knowledge-graph', icon: 'network',      status: 'demo', desc: { zh: '川剧知识的关系图谱', en: 'Knowledge graph of Sichuan opera' } },
    { id: 'creator-hub',     icon: 'users',        status: 'demo', desc: { zh: '创作者共建共享的数字内容平台', en: 'Co-creation platform for creators' } },
    { id: 'ip-minting',      icon: 'coins',        status: 'demo', desc: { zh: '数字藏品铸造与确权', en: 'Mint and certify digital collectibles' } },
    { id: 'vr-exhibition',   icon: 'rotate-3d',    status: 'demo', desc: { zh: '360° 全景虚拟展厅', en: '360° virtual gallery' } },
    { id: 'opera-life',      icon: 'coffee',       status: 'demo', desc: { zh: '剧场周边的川式生活方式', en: 'Sichuan lifestyle around the theatre' } },
    { id: 'opera-world',     icon: 'globe-2',      status: 'demo', desc: { zh: '川剧的历史与世界', en: 'History and world of Sichuan opera' } },
    { id: 'heritage-relics', icon: 'gem',          status: 'demo', desc: { zh: '传世信物数字典藏', en: 'Digital heirloom collection' } },
  ];

  const I18N = {
    zh: { title: '中国川剧', sub: '川剧体验 · 全部功能', back: '中国川剧', cur: '当前',
          live: '正式可用', demo: '概念演示', count: function (l, d) { return `${l} 项正式 · ${d} 项概念`; } },
    en: {
      title: 'China Chuanju', sub: 'Sichuan opera · every experience', back: 'China Chuanju', cur: 'Now viewing',
      live: 'Ready', demo: 'Concept', count: function (l, d) { return `${l} ready · ${d} concepts`; } },
  };
  const lang = () => (localStorage.getItem('app_lang') || 'zh').startsWith('zh') ? 'zh' : 'en';
  const t = (k) => { const d = I18N[lang()] || I18N.en; return d[k] !== undefined ? d[k] : I18N.en[k]; };
  const pick = (o) => o ? (o[lang()] || o.en || o.zh || '') : '';

  const CSS = `
  #wg-backbar{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:12px;
    background:hsl(var(--card));border:1px solid hsl(var(--border));margin-bottom:12px}
  #wg-backbar.hidden{display:none}
  #wg-back{border:none;background:transparent;color:hsl(var(--primary));font-size:13px;font-weight:700;
    cursor:pointer;padding:4px 8px;border-radius:8px}
  #wg-back:hover{background:rgba(139,26,26,.08)}
  #wg-cur{font-size:12px;color:hsl(var(--muted-foreground))}
  #wg-launcher.hidden{display:none}
  .wg-head{display:flex;align-items:baseline;gap:12px;margin-bottom:16px}
  .wg-head h3{font-family:'Noto Serif SC',serif;font-weight:900;font-size:22px;color:hsl(var(--foreground))}
  .wg-head .sub{font-size:12px;color:hsl(var(--muted-foreground))}
  .wg-head .cnt{margin-left:auto;font-size:11px;color:hsl(var(--muted-foreground))}
  .wg-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
  @media(min-width:768px){.wg-grid{grid-template-columns:repeat(3,1fr)}}
  @media(min-width:1200px){.wg-grid{grid-template-columns:repeat(4,1fr)}}
  .wg-tile{position:relative;display:flex;flex-direction:column;gap:10px;padding:18px 16px 14px;
    background:hsl(var(--card));border:1px solid hsl(var(--border));border-radius:16px;cursor:pointer;
    text-align:left;transition:border-color .2s,box-shadow .2s,transform .2s;font-family:inherit}
  .wg-tile:hover{border-color:hsl(var(--primary));box-shadow:0 8px 24px rgba(139,26,26,.10);transform:translateY(-3px)}
  .wg-tile .ico{width:40px;height:40px;border-radius:12px;background:rgba(139,26,26,.08);
    display:flex;align-items:center;justify-content:center;color:hsl(var(--primary))}
  .wg-tile .nm{font-size:14px;font-weight:700;color:hsl(var(--foreground));line-height:1.4}
  .wg-tile .ds{font-size:11px;line-height:1.6;color:hsl(var(--muted-foreground))}
  .wg-tile .st{position:absolute;top:12px;right:12px;font-size:9px;font-weight:800;letter-spacing:.06em;
    padding:2px 7px;border-radius:999px;white-space:nowrap}
  .wg-tile .st.live{color:#2E7D32;background:rgba(46,125,50,.1);border:1px solid rgba(46,125,50,.3)}
  .wg-tile .st.demo{color:hsl(var(--muted-foreground));background:hsl(var(--secondary));border:1px solid hsl(var(--border))}
  .wg-tile.demo-t .ico{background:hsl(var(--secondary));color:hsl(var(--muted-foreground))}
  .dark .wg-tile .st.live{color:#81C995;background:rgba(129,201,149,.08);border-color:rgba(129,201,149,.3)}
  `;

  /* ── DOM 构建 ── */
  function build() {
    if (document.getElementById('wg-launcher')) return;
    const style = document.createElement('style');
    style.id = 'wg-style';
    style.textContent = CSS;
    document.head.appendChild(style);

    const view = document.getElementById('view-wenchuang');
    const subnav = document.getElementById('wenchuang-subnav-bar');
    if (!view || !subnav) return;

    // 返回钮（插入子导航条内，仅在子板块中显示）
    const back = document.createElement('button');
    back.id = 'wg-back';
    back.className = 'hidden';
    back.addEventListener('click', (e) => {
      e.stopPropagation();
      if (window.WenchuangLauncher) window.WenchuangLauncher.open(); // 全局稳定引用
      else showLauncher();
    });
    const row = subnav.firstElementChild || subnav;
    row.insertBefore(back, row.firstChild);

    // 面板（插在子导航条之后）
    const launcher = document.createElement('div');
    launcher.id = 'wg-launcher';
    launcher.className = 'hidden';
    view.insertBefore(launcher, subnav.nextSibling);

    renderTiles();
  }

  function renderTiles() {
    const launcher = document.getElementById('wg-launcher');
    if (!launcher) return;
    const live = TILES.filter(x => x.status === 'live').length;
    launcher.innerHTML =
      `<div class="wg-head"><h3>${t('title')}</h3><span class="sub">${t('sub')}</span>` +
      `<span class="cnt">${t('count')(live, TILES.length - live)}</span></div>` +
      `<div class="wg-grid">` +
      TILES.map(x => {
        const navName = document.querySelector(`#wc-btn-${x.id} [data-i18n]`);
        const name = navName ? navName.textContent.trim() : x.id;
        return `<button class="wg-tile${x.status === 'demo' ? ' demo-t' : ''}" data-wg="${x.id}">` +
          `<span class="ico"><i data-lucide="${x.icon}" class="w-5 h-5"></i></span>` +
          `<span class="st ${x.status}">${x.status === 'live' ? t('live') : t('demo')}</span>` +
          `<span class="nm">${name}</span>` +
          `<span class="ds">${escapeHtml(pick(x.desc))}</span>` +
          `</button>`;
      }).join('') +
      `</div>`;
    launcher.querySelectorAll('.wg-tile').forEach(tile => {
      tile.addEventListener('click', () => switchWenchuangSubView(tile.dataset.wg, null));
    });
    if (window.lucide) lucide.createIcons();
  }

  function escapeHtml(x) {
    return String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* ── 面板 / 子板块 切换 ── */
  function showLauncher() {
    build();
    document.querySelectorAll('#view-wenchuang .wc-subview').forEach(sv => sv.classList.add('hidden'));
    const launcher = document.getElementById('wg-launcher');
    const subnav = document.getElementById('wenchuang-subnav-bar');
    const back = document.getElementById('wg-back');
    launcher.classList.remove('hidden');
    if (subnav) subnav.style.display = 'none';
    if (back) back.classList.add('hidden');
    renderTiles();
  }
  function enterSub(id) {
    build();
    const launcher = document.getElementById('wg-launcher');
    const subnav = document.getElementById('wenchuang-subnav-bar');
    const back = document.getElementById('wg-back');
    if (launcher) launcher.classList.add('hidden');
    if (subnav) subnav.style.display = '';
    if (back) {
      back.classList.remove('hidden');
      const navName = document.querySelector(`#wc-btn-${id} [data-i18n]`);
      back.textContent = '← ' + t('back');
      const cur = document.getElementById('wg-cur');
      if (cur) cur.textContent = (lang() === 'zh' ? '当前：' : 'Now: ') + (navName ? navName.textContent.trim() : id);
    }
  }

  /* ── 包装全局切换函数：原逻辑先行，随后同步面板可见性 ── */
  const origSwitch = window.switchWenchuangSubView;
  if (typeof origSwitch === 'function') {
    window.switchWenchuangSubView = function (subViewId, e) {
      if (subViewId === 'appmenu') { showLauncher(); return; }
      origSwitch(subViewId, e);
      enterSub(subViewId);
    };
  }

  /* ── 进入文创视图时：无目标子板块则回面板 ── */
  let lastSub = null;
  const origEnter = enterSub;
  enterSub = function (id) { lastSub = id; origEnter(id); };
  const origLauncher = showLauncher;
  showLauncher = function () { lastSub = null; origLauncher(); };

  const view = document.getElementById('view-wenchuang');
  if (view) {
    new MutationObserver(() => {
      const visible = !view.classList.contains('hidden');
      if (visible && !lastSub) showLauncher();
    }).observe(view, { attributes: true, attributeFilter: ['class'] });
  }
  /* 主触发源：包装 switchView（比 observer 可靠——真实导航必经）。
     有 sub 参数（深链）时不排队 showLauncher——避免吞掉子视图 */
  const origSwitchView = window.switchView;
  if (typeof origSwitchView === 'function') {
    window.switchView = function (viewName) {
      const r = origSwitchView.apply(this, arguments);
      const hasSub = new URLSearchParams(location.search).get('sub');
      if (viewName === 'wenchuang' && !lastSub && !hasSub) setTimeout(function () {
        if (!lastSub) showLauncher(); // 双检：深链可能已设 lastSub
      }, 0);
      return r;
    };
  }

  window.addEventListener('app:langchange', () => {
    if (document.getElementById('wg-launcher')) renderTiles();
    if (lastSub) enterSub(lastSub);
  });

  window.WenchuangLauncher = { open: showLauncher };
})();
