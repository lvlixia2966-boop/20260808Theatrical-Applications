/* 情境引擎（context-engine.js）——「此情此刻此景」
 *
 * 把应用从工具升级为随身陪看：感知游客所处阶段（此刻）、所在界面（此景）、
 * 个人状态（此情），在黄金干预时刻主动给出 30 字内的对的内容。
 *
 * 阶段判定（优先级从高到低）：
 *   live     已开播（app:live:joined 事件，含场次时间字段）
 *   ├ inter  中场/冷场：字幕静默 > 4 分钟且已播 > 10 分钟（推中场卡，字幕恢复即撤）
 *   └ finale 压轴临近：距收播 ≤ 8 分钟（推 30 字预警卡，一次性）
 *   pre      候场：/api/live/shows/next 返回 90 分钟内待演场次（大厅倒计时横幅）
 *   idle     无场次
 *
 * 调度原则：演出中仅短卡、同时最多 1 张、每类每场最多 1 次、默认 8s 自净。
 * 调试：URL 带 ?debug 时暴露 window.__Ctx（状态与 force(phase)）。
 */
(function () {
  'use strict';

  var I18N = {
    zh: {
      pre: '距开演', entering: '已到开演时间 · 刷新场次', liveNow: '进入收听 →',
      preSub: '观剧页可预习今晚节目 · 竞答赢文创礼遇',
      interTitle: '🍵 中场休息', interBody: '约 15 分钟 · 来局竞答，或看看散场去哪逛',
      interLow: '🎧 耳机低电量，中场可到服务台换电', quiz: '来局竞答', shop: '购物点',
      finale: '🎭 压轴将至 · 变脸吐火，坐稳了', progress: '本场进度',
    },
    en: {
      pre: 'Show starts in', entering: 'Showtime · refresh sessions', liveNow: 'Enter listening →',
      preSub: 'Preview tonight\'s programme on the Spectate page · quiz for perks',
      interTitle: '🍵 Intermission', interBody: 'About 15 min — try the quiz, or browse where to go after',
      interLow: '🎧 Headset low — swap it at the desk during the break', quiz: 'Take the quiz', shop: 'Shopping',
      finale: '🎭 Finale ahead — face-changing & fire-spitting. Hold tight', progress: 'Progress',
    },
  };
  function lang() {
    var l = localStorage.getItem('app_lang') || 'zh';
    return l.indexOf('zh') === 0 ? 'zh' : 'en';
  }
  function t(k) { var d = I18N[lang()] || I18N.en; return d[k] || I18N.en[k] || k; }

  var S = {
    mode: 'idle',        // idle | pre | live
    show: null,          // pre: 待演场次；live: 当前场次（start_at/duration_min/title/session_code）
    startAt: 0, endAt: 0,
    lastCap: 0,          // 最近一次字幕到达时间
    low: false,          // 耳机低电量
    phase: '',           // live | inter | finale
    interDone: false, finDone: false,
    entered: false,      // 已进入过本场的收听页
  };

  var MARKS = { empty: 'ld-empty-ico' };

  /* ── 样式（自包含注入，深色收听席主题） ── */
  var CSS = [
    '.ctx-preshow{margin-bottom:12px;padding:14px 16px;border-radius:12px;',
      'background:linear-gradient(135deg,rgba(199,62,58,.18),rgba(224,168,62,.10));',
      'border:1px solid rgba(224,168,62,.4);color:#F5EDE0;font-size:13px;line-height:1.7}',
    '.ctx-preshow .ctx-pre-row{font-weight:700;display:flex;align-items:center;gap:6px;flex-wrap:wrap}',
    '.ctx-preshow b.ctx-clock{color:#F5C557;font-size:18px;font-variant-numeric:tabular-nums;letter-spacing:1px}',
    '.ctx-preshow .ctx-pre-sub{font-size:11px;color:rgba(245,237,224,.6);margin-top:4px}',
    '.ctx-go{padding:6px 14px;border-radius:999px;border:none;background:#E0A83E;color:#241610;',
      'font-size:12px;font-weight:800;cursor:pointer}',
    '.ctx-card{position:relative;padding:14px 34px 14px 16px;border-radius:14px;margin-bottom:4px;',
      'background:linear-gradient(135deg,rgba(199,62,58,.16),rgba(224,168,62,.08));',
      'border:1px solid rgba(224,168,62,.45);color:#F5EDE0;animation:ctxIn .45s cubic-bezier(.2,.8,.3,1)}',
    '.ctx-card .ctx-x{position:absolute;top:8px;right:10px;width:24px;height:24px;border-radius:50%;',
      'border:none;background:transparent;color:rgba(245,237,224,.6);cursor:pointer;font-size:13px}',
    '.ctx-card .ctx-title{font-family:"Ma Shan Zheng",serif;font-size:20px;letter-spacing:2px;color:#F5C557}',
    '.ctx-card .ctx-title.finale{color:#E8564E}',
    '.ctx-card .ctx-body{font-size:13px;line-height:1.7;color:rgba(245,237,224,.85);margin-top:4px}',
    '.ctx-card .ctx-low{font-size:11px;color:#F5C557;margin-top:6px}',
    '.ctx-card .ctx-actions{display:flex;gap:8px;margin-top:10px}',
    '.ctx-btn{padding:7px 14px;border-radius:999px;border:none;background:#C73E3A;color:#FFF9F2;',
      'font-size:12px;font-weight:700;cursor:pointer}',
    '.ctx-btn.ghost{background:transparent;border:1px solid rgba(224,168,62,.5);color:#F5C557}',
    '@keyframes ctxIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}',
    '#live-progress{height:4px;border-radius:999px;background:rgba(224,168,62,.15);margin-bottom:8px;overflow:hidden;transition:opacity .5s}',
    '#live-progress-fill{height:100%;width:0;border-radius:999px;background:linear-gradient(90deg,#C73E3A,#E0A83E);transition:width 1s linear}',
    '@media(prefers-reduced-motion:reduce){.ctx-card{animation:none}}'
  ].join('\n');
  function ensureCtxStyles() {
    if (document.getElementById('ctx-style')) return;
    var st = document.createElement('style');
    st.id = 'ctx-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function scroller() { return document.scrollingElement || document.documentElement; }
  function inListen() {
    var v = document.getElementById('view-listen');
    return !!v && !v.classList.contains('hidden');
  }

  /* ── 候场横幅（收听大厅，位于场次列表之上） ── */
  function showBanner(show, startMs) {
    var list = document.getElementById('live-list');
    if (!list) return;
    var b = document.getElementById('ctx-preshow');
    if (!b) {
      b = document.createElement('div');
      b.id = 'ctx-preshow';
      b.className = 'ctx-preshow';
      list.parentNode.insertBefore(b, list);
    }
    var left = startMs - Date.now();
    var title = (show && show.title) ? show.title : '';
    if (left <= 0) {
      b.innerHTML = '<div class="ctx-pre-row">🏮 ' + t('entering') +
        ' <button class="ctx-go" id="ctx-enter">' + t('liveNow') + '</button></div>';
      var btn = document.getElementById('ctx-enter');
      if (btn && !btn.__wired) {
        btn.__wired = true;
        btn.addEventListener('click', function () { window.dispatchEvent(new CustomEvent('app:live:refresh')); });
      }
    } else {
      var mm = Math.floor(left / 60000);
      var disp = mm >= 60 ? Math.floor(mm / 60) + ' h ' + (mm % 60) + ' min' : fmtMS(left);
      b.innerHTML = '<div class="ctx-pre-row">🏮 ' + t('pre') + ' 《' + escapeHtml(title) + '》 <b class="ctx-clock">' + disp + '</b></div>' +
        '<div class="ctx-pre-sub">' + t('preSub') + '</div>';
    }
  }
  function hideBanner() {
    var b = document.getElementById('ctx-preshow');
    if (b) b.remove();
  }
  function fmtMS(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    var m = Math.floor(s / 60);
    return (m < 10 ? '0' : '') + m + ':' + ('0' + (s % 60)).slice(-2);
  }

  /* ── 情境卡（收听页字幕流内，同时最多 1 张） ── */
  function card(html, opts) {
    opts = opts || {};
    var stream = document.getElementById('stream');
    if (!stream || !inListen()) return null;
    removeCard(opts.cls || '');
    var el = document.createElement('div');
    el.className = 'ctx-card' + (opts.cls ? ' ' + opts.cls : '');
    el.innerHTML =
      '<button class="ctx-x" aria-label="close">✕</button>' + html;
    stream.insertBefore(el, stream.firstChild);
    el.querySelector('.ctx-x').addEventListener('click', function () { el.remove(); });
    if (window.lucide) lucide.createIcons();
    if (opts.ttl > 0) setTimeout(function () { el.remove(); }, opts.ttl);
    return el;
  }
  function removeCard(cls) {
    var stream = document.getElementById('stream');
    if (!stream) return;
    var sel = cls ? '.ctx-card.' + cls : '.ctx-card:not(.inter)';
    stream.querySelectorAll(sel).forEach(function (e) { e.remove(); });
  }

  function showInter() {
    var el = card(
      '<div class="ctx-title">' + t('interTitle') + '</div>' +
      '<div class="ctx-body">' + t('interBody') + '</div>' +
      (S.low ? '<div class="ctx-low">' + t('interLow') + '</div>' : '') +
      '<div class="ctx-actions">' +
        '<button class="ctx-btn" id="ctx-quiz">' + t('quiz') + '</button>' +
        '<button class="ctx-btn ghost" id="ctx-shop">' + t('shop') + '</button>' +
      '</div>',
      { cls: 'inter', ttl: 0 });
    if (!el) return;
    el.querySelector('#ctx-quiz').addEventListener('click', function () {
      if (window.OperaQuiz) window.OperaQuiz.open();
    });
    el.querySelector('#ctx-shop').addEventListener('click', function () {
      if (window.switchView) { window.switchView('wenchuang'); window.switchWenchuangSubView('shopping-spots', null); }
    });
  }
  function showFinale() {
    card('<div class="ctx-title finale">' + t('finale') + '</div>', { cls: 'finale', ttl: 8000 });
  }

  /* ── 进度细条（实时字幕卡顶部） ── */
  function ensureProgress() {
    var stream = document.getElementById('stream');
    if (!stream || document.getElementById('live-progress')) return;
    var bar = document.createElement('div');
    bar.id = 'live-progress';
    bar.title = t('progress');
    bar.innerHTML = '<div id="live-progress-fill"></div>';
    stream.parentNode.insertBefore(bar, stream);
  }
  function updateProgress(ratio) {
    var f = document.getElementById('live-progress-fill');
    if (f) f.style.width = Math.min(100, Math.max(0, ratio * 100)).toFixed(1) + '%';
  }

  /* ── 心跳：阶段判定 ── */
  function tick() {
    if (S.mode !== 'live' || !S.startAt) return;
    var now = Date.now();
    var elapsed = now - S.startAt;
    var remaining = S.endAt - now;
    updateProgress(elapsed / Math.max(1, S.endAt - S.startAt));
    var phase = 'live';
    if (remaining <= 8 * 60 * 1000) phase = 'finale';
    else if (S.lastCap && now - S.lastCap > 4 * 60 * 1000 && elapsed > 10 * 60 * 1000) phase = 'inter';
    if (phase !== S.phase) {
      if (phase === 'inter' && !S.interDone) { S.interDone = true; showInter(); window.dispatchEvent(new CustomEvent('app:live:inter')); }
      if (phase === 'finale' && !S.finDone) { S.finDone = true; showFinale(); }
      S.phase = phase;
    }
  }

  /* ── 候场轮询 ── */
  function pollNext() {
    if (S.mode === 'live') return;
    fetch('/api/live/shows/next').then(function (r) { return r.json(); }).then(function (b) {
      var show = b.data;
      if (show && show.start_at) {
        var startMs = new Date(show.start_at).getTime();
        if (startMs - Date.now() < 90 * 60 * 1000) {
          S.mode = 'pre'; S.show = show;
          showBanner(show, startMs);
          return;
        }
      }
      if (S.mode === 'pre') hideBanner();
      S.mode = 'idle';
    }).catch(function () { /* 网络异常静默 */ });
  }

  /* ── 事件接线 ── */
  window.addEventListener('app:live:joined', function (ev) {
    var show = (ev.detail && ev.detail.show) || null;
    if (!show || !show.start_at) return;
    S.mode = 'live'; S.show = show;
    S.startAt = new Date(show.start_at).getTime();
    S.endAt = S.startAt + (show.duration_min || 90) * 60000;
    S.lastCap = Date.now();
    S.interDone = false; S.finDone = false; S.phase = '';
    hideBanner();
    ensureProgress();
  });
  window.addEventListener('app:live:caption', function () { S.lastCap = Date.now(); removeCard('inter'); });
  window.addEventListener('app:live:ended', function () {
    S.mode = 'idle'; S.phase = '';
    removeCard('');
    var p = document.getElementById('live-progress');
    if (p) { p.style.opacity = '0.25'; }
  });
  window.addEventListener('ble:connected', function (ev) {
    if (ev.detail && ev.detail.lowBattery) S.low = true;
  });
  window.addEventListener('app:langchange', function () {
    if (S.mode === 'pre' && S.show && S.show.start_at) showBanner(S.show, new Date(S.show.start_at).getTime());
  });
  window.addEventListener('app:live:refresh', function () { if (S.mode === 'pre') pollNext(); });

  setInterval(tick, 1000);
  setInterval(pollNext, 30000);

  function boot() { ensureCtxStyles(); pollNext(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* ── 调试钩子（?debug）：强制阶段用于验收 ── */
  if (new URLSearchParams(location.search).has('debug')) {
    window.__Ctx = {
      state: S,
      force: function (phase) {
        if (phase === 'inter') { S.lastCap = Date.now() - 5 * 60 * 1000; S.startAt = Date.now() - 20 * 60 * 1000; S.endAt = Date.now() + 40 * 60 * 1000; S.mode = 'live'; S.interDone = false; }
        if (phase === 'finale') { S.startAt = Date.now() - 80 * 60 * 1000; S.endAt = Date.now() + 5 * 60 * 1000; S.mode = 'live'; S.finDone = false; }
        tick();
      },
    };
  }

  function escapeHtml(x) {
    return String(x).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
})();
