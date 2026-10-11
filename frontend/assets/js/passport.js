/* 川剧护照（集章）模块（passport.js）
 *
 * 业务目标：把「连耳机 → 听介绍 → 看同传 → 问伴游 → 收直播 → 旅拍 → 下单 → 竞答」
 *   的完整游程串成可收集的电子印章，提升停留时长与传播（离场后可展示）。
 *
 * 高内聚：印章定义、授予逻辑、印章墙弹层、个人中心入口卡，全部收敛于此。
 * 低耦合：只监听既有事件 / DOM（不改动各业务模块）：
 *   - ble:connected（ble-guard 派发）            → headset 印章
 *   - app:order:paid（checkout 派发）            → order 印章
 *   - app:live:joined（live-listen 派发）        → live 印章
 *   - app:quiz:passed（quiz.js 派发）            → quiz 印章
 *   - 委托点击：剧场介绍播放 / 皮金滚灯播放 / 伴游发送 → intro/pijin/agent 印章
 *   - 包装 generateAiPhoto（index.html 全局函数）→ photoshoot 印章
 * 状态存 localStorage('chuan_passport')：{ 印章id: 授予时间戳 }，纯前端、无后端依赖。
 *
 * 入口（不打扰主线）：个人中心护照卡 + 授章 toast + 各业务完成时的轻提示。
 */
(function () {
  'use strict';

  var STORE_KEY = 'chuan_passport';

  /* ── 印章定义（zh/en 双语，未列语言回退英文） ── */
  var STAMPS = [
    { id: 'headset',    icon: '🎧', name: { zh: '耳机接引', en: 'Headset Connected' },
      desc: { zh: '连接专用同传耳机', en: 'Connect the interpretation headset' } },
    { id: 'intro',      icon: '🏮', name: { zh: '初识剧场', en: 'First Steps Inside' },
      desc: { zh: '收听剧场介绍与观演须知', en: 'Listen to the theatre intro' } },
    { id: 'pijin',      icon: '🎭', name: { zh: '滚灯一瞥', en: 'Rolling Lantern' },
      desc: { zh: '试听《皮金滚灯》双语同传', en: 'Preview the Pijin rolling-lantern act' } },
    { id: 'agent',      icon: '🧭', name: { zh: '伴游问津', en: 'Ask the Guide' },
      desc: { zh: '向智能伴游提一个问题', en: 'Ask the AI companion a question' } },
    { id: 'live',       icon: '📻', name: { zh: '现场收听', en: 'In the Live Seat' },
      desc: { zh: '进入场次直播收听席', en: 'Join a live show listening seat' } },
    { id: 'photoshoot', icon: '📸', name: { zh: '锦城旅拍', en: 'AI Photoshoot' },
      desc: { zh: '生成一张 AI 川剧旅拍', en: 'Generate an AI opera photo' } },
    { id: 'order',      icon: '🛍', name: { zh: '文创雅集', en: 'Cultural Keepsake' },
      desc: { zh: '完成一次文创下单', en: 'Complete a cultural order' } },
    { id: 'quiz',       icon: '🏆', name: { zh: '懂戏之人', en: 'Opera Insider' },
      desc: { zh: '观演知识竞答通关', en: 'Pass the opera quiz' } },
  ];

  var UI = {
    zh: {
      title: '川剧护照', subtitle: 'SICHUAN OPERA PASSPORT',
      tagline: '集齐印章，解锁「川剧知音」礼遇',
      progress: function (n, total) { return '已集 ' + n + ' / ' + total + ' 枚印章'; },
      gotOn: '获得于', close: '合上护照', allDone: '集齐了！川剧知音就是你 🎉',
      awardToast: function (name) { return '🪪 川剧护照 +1 ·「' + name + '」'; },
      cardTitle: '川剧护照', cardCta: '点击查看印章墙 🪪',
      cardProgress: function (n, total) { return n + ' / ' + total + ' 枚印章'; },
    },
    en: {
      title: '川剧护照', subtitle: 'SICHUAN OPERA PASSPORT',
      tagline: 'Collect every stamp to earn the Opera Insider treat',
      progress: function (n, total) { return n + ' / ' + total + ' stamps collected'; },
      gotOn: 'Earned', close: 'Close', allDone: 'All collected — a true Opera Insider! 🎉',
      awardToast: function (name) { return '🪪 Passport +1 · "' + name + '"'; },
      cardTitle: 'Opera Passport', cardCta: 'Open the stamp wall 🪪',
      cardProgress: function (n, total) { return n + ' / ' + total + ' stamps'; },
    },
  };

  function lang() {
    var l = localStorage.getItem('app_lang') || 'zh';
    return l.indexOf('zh') === 0 ? 'zh' : (UI[l] ? l : 'en');
  }
  function t(key) { var d = UI[lang()] || UI.en; return d[key] || UI.en[key] || key; }
  function pick(obj) { return obj ? (obj[lang()] || obj.en || obj.zh || '') : ''; }

  /* ── 状态 ── */
  function load() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function save(state) { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }

  function earnedCount(state) { return STAMPS.filter(function (s) { return state[s.id]; }).length; }

  /* ── 授章：已持有则静默，新授章 toast + 事件 ── */
  function award(id, silent) {
    var def = null;
    for (var i = 0; i < STAMPS.length; i++) if (STAMPS[i].id === id) def = STAMPS[i];
    if (!def) return false;
    var state = load();
    if (state[id]) return false;
    state[id] = Date.now();
    save(state);
    if (!silent && window.showToast) window.showToast(t('awardToast')(pick(def.name)));
    renderProfileCard();
    if (panelOpen) renderWall();
    if (earnedCount(state) === STAMPS.length && !silent && window.showToast) {
      setTimeout(function () { window.showToast(t('allDone')); }, 1600);
    }
    window.dispatchEvent(new CustomEvent('app:passport:stamp', { detail: { id: id } }));
    return true;
  }

  /* ── 弹层（印章墙） ── */
  var panelOpen = false;

  var CSS = [
    '#pp-mask{position:fixed;inset:0;background:rgba(20,12,8,.55);z-index:420;opacity:0;pointer-events:none;transition:opacity .3s}',
    '#pp-mask.open{opacity:1;pointer-events:auto}',
    '#pp-panel{position:fixed;left:50%;top:50%;z-index:421;width:min(92vw,420px);max-height:88vh;overflow-y:auto;',
      'transform:translate(-50%,-46%) scale(.96);opacity:0;pointer-events:none;transition:all .32s cubic-bezier(.2,.8,.25,1);',
      'background:#FFFDF8;border:1px solid rgba(139,26,26,.25);border-radius:20px;',
      'box-shadow:0 24px 64px rgba(20,12,8,.35)}',
    '#pp-panel.open{transform:translate(-50%,-50%) scale(1);opacity:1;pointer-events:auto}',
    '#pp-cover{position:relative;padding:22px 20px 18px;border-radius:20px 20px 0 0;overflow:hidden;',
      'background:linear-gradient(150deg,#8B1A1A 0%,#6E1212 60%,#4E0C0C 100%);color:#FFF9F2}',
    '#pp-cover::after{content:"";position:absolute;inset:0;pointer-events:none;',
      'background:radial-gradient(circle at 85% 15%,rgba(224,168,62,.22),transparent 45%)}',
    '.pp-cover-row{display:flex;align-items:center;justify-content:space-between;gap:10px;position:relative;z-index:1}',
    '.pp-title{font-family:"Ma Shan Zheng",serif;font-size:30px;letter-spacing:6px;line-height:1.1}',
    '.pp-sub{font-size:9px;letter-spacing:3px;opacity:.75;margin-top:4px}',
    '.pp-seal{width:46px;height:46px;border-radius:10px;background:linear-gradient(135deg,#C73E3A,#8B1A1A);border:1.5px solid rgba(255,249,242,.5);',
      'display:flex;align-items:center;justify-content:center;font-family:"Ma Shan Zheng",serif;font-size:22px;',
      'transform:rotate(-4deg);box-shadow:0 4px 14px rgba(0,0,0,.35);flex-shrink:0}',
    '#pp-tagline{position:relative;z-index:1;font-size:11px;opacity:.85;margin-top:10px}',
    '#pp-progress-wrap{padding:12px 20px 2px}',
    '#pp-progress-text{font-size:11px;color:#6b6b6b;margin-bottom:6px;font-weight:600}',
    '#pp-progress-bar{height:6px;border-radius:999px;background:#F3EDE4;overflow:hidden}',
    '#pp-progress-fill{height:100%;width:0;border-radius:999px;transition:width .5s ease;',
      'background:linear-gradient(90deg,#C73E3A,#E0A83E)}',
    '#pp-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;padding:12px 20px 8px}',
    '@media(min-width:480px){#pp-grid{grid-template-columns:repeat(4,1fr)}}',
    '.pp-stamp{position:relative;border-radius:12px;padding:10px 6px 8px;text-align:center;min-height:96px;',
      'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;',
      'border:1.5px dashed #E8DCC8;background:transparent;transition:all .2s}',
    '.pp-stamp .pp-icon{font-size:24px;filter:grayscale(1);opacity:.45;line-height:1}',
    '.pp-stamp .pp-name{font-size:11px;font-weight:700;color:#9A8B7A;line-height:1.3}',
    '.pp-stamp .pp-desc{font-size:9px;color:#9A8B7A;opacity:.8;line-height:1.4}',
    '.pp-stamp.earned{border:1.5px solid rgba(139,26,26,.55);background:rgba(139,26,26,.05);',
      'box-shadow:inset 0 0 14px rgba(139,26,26,.08);transform:rotate(-1.5deg)}',
    '.pp-stamp.earned:nth-child(even){transform:rotate(1.8deg)}',
    '.pp-stamp.earned .pp-icon{filter:none;opacity:1}',
    '.pp-stamp.earned .pp-name{color:#8B1A1A}',
    '.pp-stamp.earned .pp-desc{color:#5C4A3A;opacity:1}',
    '.pp-stamp.earned::before{content:"";position:absolute;top:5px;right:6px;width:7px;height:7px;border-radius:50%;',
      'background:radial-gradient(circle at 35% 35%,#E0584E,#8B1A1A);box-shadow:0 1px 3px rgba(139,26,26,.4)}',
    '.pp-date{font-size:9px;color:#C8861E;font-weight:700;font-variant-numeric:tabular-nums}',
    '.pp-foot{padding:10px 20px calc(16px + env(safe-area-inset-bottom));display:flex;justify-content:flex-end}',
    '#pp-close{padding:8px 18px;border-radius:999px;border:1px solid rgba(139,26,26,.3);background:transparent;',
      'color:#8B1A1A;font-size:12px;font-weight:700;cursor:pointer;transition:all .15s}',
    '#pp-close:hover{background:rgba(139,26,26,.06)}',
    /* 个人中心入口卡 */
    '.pp-entry-card{display:flex;align-items:center;gap:14px;padding:16px;border-radius:14px;cursor:pointer;transition:all .2s;',
      'background:linear-gradient(135deg,rgba(139,26,26,.06),rgba(200,134,30,.07));',
      'border:1px solid rgba(139,26,26,.25)}',
    '.pp-entry-card:hover{border-color:rgba(139,26,26,.5);box-shadow:var(--shadow-md,0 4px 16px rgba(139,26,26,.08))}',
    '.pp-entry-seal{width:44px;height:44px;border-radius:10px;flex-shrink:0;display:flex;align-items:center;justify-content:center;',
      'background:linear-gradient(135deg,#C73E3A,#8B1A1A);color:#FFF9F2;font-family:"Ma Shan Zheng",serif;font-size:20px;',
      'transform:rotate(-3deg);box-shadow:0 2px 10px rgba(139,26,26,.3)}',
    '.dark #pp-panel{background:#211812;border-color:rgba(199,62,58,.3)}',
    '.dark .pp-stamp{border-color:#3A2C20}',
    '.dark .pp-stamp.earned{border-color:rgba(224,168,62,.55);background:rgba(224,168,62,.07)}',
    '.dark #pp-progress-bar{background:#3A2C20}',
    '.dark #pp-progress-text{color:#C4B5A5}',
    '.dark .pp-stamp .pp-name{color:#8A7B6A}',
    '.dark .pp-stamp .pp-desc{color:#8A7B6A}',
    '.dark .pp-stamp.earned .pp-name{color:#F5C557}',
    '.dark .pp-stamp.earned .pp-desc{color:#C4B5A5}',
    '.dark #pp-close{color:#F5C557;border-color:rgba(224,168,62,.4)}',
    '#pp-panel{color:#3A2E24}',
    '.dark #pp-panel{color:#C4B5A5}',
    '@media(prefers-reduced-motion:reduce){#pp-panel{transition:none}}'
  ].join('\n');

  function ensureStyles() {
    if (document.getElementById('pp-style')) return;
    var style = document.createElement('style');
    style.id = 'pp-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function buildPanel() {
    if (document.getElementById('pp-panel')) return;
    ensureStyles();

    var mask = document.createElement('div');
    mask.id = 'pp-mask';
    mask.addEventListener('click', closePanel);
    document.body.appendChild(mask);

    var panel = document.createElement('div');
    panel.id = 'pp-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', '川剧护照');
    panel.innerHTML =
      '<div id="pp-cover">' +
        '<div class="pp-cover-row">' +
          '<div><div class="pp-title">川剧护照</div><div class="pp-sub">' + UI[lang()].subtitle + '</div></div>' +
          '<div class="pp-seal">川</div>' +
        '</div>' +
        '<div id="pp-tagline"></div>' +
      '</div>' +
      '<div id="pp-progress-wrap">' +
        '<div id="pp-progress-text"></div>' +
        '<div id="pp-progress-bar"><div id="pp-progress-fill"></div></div>' +
      '</div>' +
      '<div id="pp-grid"></div>' +
      '<div class="pp-foot"><button id="pp-close"></button></div>';
    document.body.appendChild(panel);
    panel.querySelector('#pp-close').addEventListener('click', closePanel);
  }

  function fmtDate(ts) {
    var d = new Date(ts);
    var p = function (x) { return (x < 10 ? '0' : '') + x; };
    return d.getFullYear() + '.' + p(d.getMonth() + 1) + '.' + p(d.getDate());
  }

  function renderWall() {
    var state = load();
    var grid = document.getElementById('pp-grid');
    if (!grid) return;
    var n = earnedCount(state);
    grid.innerHTML = STAMPS.map(function (s) {
      var ts = state[s.id];
      return '<div class="pp-stamp' + (ts ? ' earned' : '') + '">' +
        '<div class="pp-icon">' + s.icon + '</div>' +
        '<div class="pp-name">' + escapeHtml(pick(s.name)) + '</div>' +
        '<div class="pp-desc">' + escapeHtml(pick(s.desc)) + '</div>' +
        (ts ? '<div class="pp-date">' + t('gotOn') + ' ' + fmtDate(ts) + '</div>' : '') +
        '</div>';
    }).join('');
    var bar = document.getElementById('pp-progress-fill');
    if (bar) bar.style.width = (n / STAMPS.length * 100) + '%';
    var pt = document.getElementById('pp-progress-text');
    if (pt) pt.textContent = t('progress')(n, STAMPS.length);
    var tag = document.getElementById('pp-tagline');
    if (tag) tag.textContent = t('tagline');
    var close = document.getElementById('pp-close');
    if (close) close.textContent = t('close');
  }

  function openPanel() {
    if (window.OperaQuiz) window.OperaQuiz.close();
    buildPanel();
    panelOpen = true;
    renderWall();
    document.getElementById('pp-mask').classList.add('open');
    document.getElementById('pp-panel').classList.add('open');
  }
  function closePanel() {
    panelOpen = false;
    var m = document.getElementById('pp-mask'), p = document.getElementById('pp-panel');
    if (m) m.classList.remove('open');
    if (p) p.classList.remove('open');
  }

  /* ── 个人中心入口卡 ── */
  function renderProfileCard() {
    var host = document.getElementById('view-user-profile');
    if (!host) return;
    var anchor = host.querySelector('.grid.grid-cols-1');
    if (!anchor) return;
    var card = document.getElementById('pp-entry');
    if (!card) {
      card = document.createElement('div');
      card.id = 'pp-entry';
      card.className = 'pp-entry-card';
      card.addEventListener('click', openPanel);
      anchor.insertAdjacentElement('afterend', card);
    }
    var n = earnedCount(load());
    card.innerHTML =
      '<div class="pp-entry-seal">川</div>' +
      '<div class="flex-1 min-w-0">' +
        '<div class="font-bold text-sm text-foreground">' + t('cardTitle') + '</div>' +
        '<div class="text-xs text-muted-foreground mt-0.5">' + t('cardProgress')(n, STAMPS.length) + '</div>' +
      '</div>' +
      '<span class="text-[11px] font-bold text-primary bg-primary/10 px-2 py-1 rounded-full whitespace-nowrap">' + t('cardCta') + '</span>';
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ── 事件挂钩 ── */
  window.addEventListener('ble:connected', function () { award('headset'); });
  window.addEventListener('app:order:paid', function () { award('order'); });
  window.addEventListener('app:live:joined', function () { award('live'); });
  window.addEventListener('app:quiz:passed', function () { award('quiz'); });
  window.addEventListener('app:langchange', function () {
    renderProfileCard();
    if (panelOpen) renderWall();
  });

  // 委托点击：剧场介绍 / 皮金滚灯 / 伴游发送（元素由各模块渲染，委托最稳）
  document.addEventListener('click', function (e) {
    var el = e.target;
    if (!(el instanceof Element)) return;
    if (el.closest('#btn-theatre-intro-play')) award('intro');
    else if (el.closest('#pijin-audio-play-btn')) award('pijin');
    else if (el.closest('#ag-send')) award('agent');
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target && e.target.id === 'ag-input' && e.target.value.trim()) award('agent');
  }, true);

  // AI 旅拍：包装全局 generateAiPhoto，成功返回后授章（原函数异常不阻断）
  function wrapPhotoshoot() {
    if (typeof window.generateAiPhoto !== 'function' || window.generateAiPhoto.__ppWrapped) return;
    var orig = window.generateAiPhoto;
    var wrapped = function () {
      try {
        var r = orig.apply(this, arguments);
        if (r && typeof r.then === 'function') {
          r.then(function () { award('photoshoot'); }, function () {});
        } else {
          award('photoshoot');
        }
        return r;
      } catch (err) { throw err; }
    };
    wrapped.__ppWrapped = true;
    window.generateAiPhoto = wrapped;
  }

  function init() {
    ensureStyles(); // 入口卡在页面加载即渲染，样式不能等弹层首开才注入
    wrapPhotoshoot();
    // creator-hub.js 晚于本模块加载时，等它就绪后再包装
    setTimeout(wrapPhotoshoot, 800);
    renderProfileCard();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  // 个人中心为动态显示，切回时刷新数字
  window.addEventListener('app:passport:stamp', renderProfileCard);

  window.Passport = {
    award: award,
    open: openPanel,
    close: closePanel,
    count: function () { return earnedCount(load()); },
    total: STAMPS.length,
  };
})();
