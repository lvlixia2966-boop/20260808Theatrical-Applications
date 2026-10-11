/* 变脸小游戏 · 极限眼力（face-game.js）
 *
 * 玩法：三关递进——脸谱连续快变（复用归一化脸谱素材，瞬时切换正是"变脸"的劲道），
 *   每关考一题：「一共变了几次脸」或「最后一张脸是什么色」，答对 2 关即通关，
 *   解锁「火眼金睛」称号 + 文创邀请码 CHUAN-FACE-7（与竞答九折码同柜台核销口径）。
 *
 * 高内聚：入口卡注入（观剧视图竞答卡之后）、关卡引擎、抽屉 UI 全部收敛于此。
 * 低耦合：样式独立 fg-* 前缀；与 quiz.js 抽屉互斥打开；零后端依赖；
 *   最佳成绩存 localStorage('chuan_face_best')。
 */
(function () {
  'use strict';

  var BEST_KEY = 'chuan_face_best';
  var MASKS = [
    { c: 'red',   zh: '红脸', en: 'Red' },
    { c: 'gold',  zh: '金脸', en: 'Gold' },
    { c: 'blue',  zh: '蓝脸', en: 'Blue' },
    { c: 'green', zh: '绿脸', en: 'Green' },
    { c: 'black', zh: '黑脸', en: 'Black' },
    { c: 'white', zh: '白脸', en: 'White' },
  ];
  var img = function (c) { return './assets/mask-' + c + '-ai-transparent.png?v=3'; };
  var LEVELS = [
    { flips: 7,  interval: 560 }, // 第一关：慢速数变
    { flips: 10, interval: 420 }, // 第二关：提速，改考末脸颜色
    { flips: 13, interval: 320 }, // 第三关：极速数变
  ];

  var UI = {
    zh: {
      cardTitle: '变脸挑战 · 极限眼力', cardSub: '脸谱快变，考你眼力——三关过两关赢礼遇', cardBtn: '接受挑战',
      panelTitle: '极限眼力', panelSub: '变脸挑战 · 三关',
      startHead: '怎么玩', r1: '脸谱连续快变，盯紧了', r2: '每关一题：数变脸次数 / 认最后一张脸',
      r3: '过 2 关解锁「火眼金睛」称号 + 文创邀请码',
      best: '最佳', startBtn: '开 始', prep: '记住这张脸…', watch: '盯紧 ——',
      qCount: '一共变了几次脸？', qFinal: '最后一张脸是什么色？',
      right: '眼力了得！', wrong: '可惜！正确答案是',
      next: '下一关', seeResult: '看结果', level: function (i, n) { return '第 ' + i + ' / ' + n + ' 关'; },
      resultHead: '挑战结束', pass: function (n) { return '通过 ' + n + ' / 3 关'; },
      rankTop: '火眼金睛', rankMid: '观戏行家', rankLow: '再来练练',
      rankSubTop: '三关全过！变脸师傅看了都点头', rankSubMid: '两关通过，眼力不俗', rankSubLow: '川剧变脸，快得不讲道理',
      couponTitle: '文创邀请码', couponUse: '结账时向工作人员出示即可', passedExtra: '🏆 解锁称号「火眼金睛」',
      retry: '再来一轮', close: '收起',
    },
    en: {
      cardTitle: 'Face-Change Challenge', cardSub: 'Masks flip in a blink — pass 2 of 3 rounds to win', cardBtn: 'Take the challenge',
      panelTitle: 'Sharp Eyes', panelSub: 'Face-change challenge · 3 rounds',
      startHead: 'How it works', r1: 'Masks flip rapidly — keep your eyes on them', r2: 'One question per round: count flips / name the last mask',
      r3: 'Pass 2 rounds to earn "Eagle Eye" + a merch code',
      best: 'Best', startBtn: 'Start', prep: 'Remember this face…', watch: 'Watch closely —',
      qCount: 'How many face-changes did you count?', qFinal: 'What color was the LAST face?',
      right: 'Sharp eyes!', wrong: 'So close! The answer was',
      next: 'Next round', seeResult: 'See result', level: function (i, n) { return 'Round ' + i + ' / ' + n; },
      resultHead: 'Round over', pass: function (n) { return 'Passed ' + n + ' / 3 rounds'; },
      rankTop: 'Eagle Eye', rankMid: 'Opera Regular', rankLow: 'Keep practising',
      rankSubTop: 'All three! The face-changers salute you', rankSubMid: 'Two rounds — sharp indeed', rankSubLow: 'Bianlian is unfairly fast',
      couponTitle: 'Merch invite code', couponUse: 'Show this code at the souvenir desk', passedExtra: '🏆 Title unlocked: Eagle Eye',
      retry: 'Play again', close: 'Close',
    },
  };

  function lang() {
    var l = localStorage.getItem('app_lang') || 'zh';
    return l.indexOf('zh') === 0 ? 'zh' : (UI[l] ? l : 'en');
  }
  function t(key) { var d = UI[lang()] || UI.en; return d[key] !== undefined ? d[key] : UI.en[key]; }
  function pick(o) { return o ? (o[lang()] || o.en || o.zh || '') : ''; }
  function maskName(c) {
    for (var i = 0; i < MASKS.length; i++) if (MASKS[i].c === c) return pick(MASKS[i]);
    return c;
  }

  var round = null; // { level, flips, final, answer, score, idx }

  function loadBest() { return parseInt(localStorage.getItem(BEST_KEY) || '0', 10) || 0; }

  function buildRound(levelIdx) {
    var lv = LEVELS[levelIdx];
    var start = MASKS[Math.floor(Math.random() * MASKS.length)].c;
    var cur = start, flips = 0, last = start;
    var seq = [start];
    for (var i = 0; i < lv.flips; i++) {
      var next;
      do { next = MASKS[Math.floor(Math.random() * MASKS.length)].c; } while (next === cur);
      cur = next; flips++; last = cur; seq.push(cur);
    }
    var askCount = levelIdx !== 1; // 第一/三关数次数，第二关认末脸
    var answer = askCount ? flips : last;
    return { level: levelIdx, seq: seq, flips: flips, final: last, askCount: askCount, answer: answer, score: round ? round.score : 0 };
  }

  /* ── 入口卡 ── */
  function injectEntry() {
    if (document.getElementById('section-facegame')) return;
    var ref = document.getElementById('section-quiz');
    if (!ref) return;
    var sec = document.createElement('section');
    sec.id = 'section-facegame';
    sec.className = 'card-modern bg-card border border-primary/25 p-5 sm:p-6';
    sec.innerHTML =
      '<div class="flex items-center gap-3 sm:gap-4">' +
        '<div class="w-10 h-10 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0">' +
          '<i data-lucide="drama" class="w-5 h-5 text-accent"></i>' +
        '</div>' +
        '<div class="flex-1 min-w-0">' +
          '<h3 class="font-display text-base sm:text-lg font-bold text-foreground" id="fg-card-title"></h3>' +
          '<p class="text-xs text-muted-foreground truncate" id="fg-card-sub"></p>' +
        '</div>' +
        '<button id="fg-open" class="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition-all shadow-sm whitespace-nowrap flex-shrink-0"></button>' +
      '</div>';
    ref.insertAdjacentElement('afterend', sec);
    sec.querySelector('#fg-open').addEventListener('click', openPanel);
    renderEntryTexts();
    if (window.lucide) lucide.createIcons();
  }
  function renderEntryTexts() {
    var el = function (id) { return document.getElementById(id); };
    if (el('fg-card-title')) el('fg-card-title').textContent = t('cardTitle');
    if (el('fg-card-sub')) el('fg-card-sub').textContent = t('cardSub');
    if (el('fg-open')) el('fg-open').textContent = t('cardBtn');
  }

  /* ── 抽屉 ── */
  var CSS = [
    '#fg-mask{position:fixed;inset:0;background:rgba(20,12,8,.45);z-index:400;opacity:0;pointer-events:none;transition:opacity .3s}',
    '#fg-mask.open{opacity:1;pointer-events:auto}',
    '#fg-panel{position:fixed;left:0;right:0;bottom:0;z-index:410;max-width:560px;margin:0 auto;',
      'background:#FFFDF8;border:1px solid rgba(139,26,26,.18);border-bottom:none;',
      'border-radius:22px 22px 0 0;box-shadow:0 -12px 40px rgba(20,12,8,.25);',
      'transform:translateY(105%);transition:transform .38s cubic-bezier(.2,.8,.25,1)}',
    '#fg-panel.open{transform:translateY(0)}',
    '.dark #fg-panel{background:#211812;border-color:rgba(199,62,58,.3)}',
    '#fg-panel .fg-head{display:flex;align-items:center;justify-content:space-between;padding:14px 18px 10px;border-bottom:1px solid rgba(139,26,26,.10)}',
    '.dark #fg-panel .fg-head{border-color:rgba(224,168,62,.15)}',
    '#fg-panel .fg-head h3{font-family:"Ma Shan Zheng",serif;font-size:22px;color:#8B1A1A;letter-spacing:2px;line-height:1}',
    '.dark #fg-panel .fg-head h3{color:#E0584E}',
    '#fg-panel .fg-sub{font-size:11px;color:#6b6b6b;margin-top:3px}',
    '.dark #fg-panel .fg-sub{color:#8A7B6A}',
    '#fg-close{width:30px;height:30px;border-radius:50%;border:1px solid rgba(139,26,26,.2);background:transparent;color:#8B1A1A;font-size:14px;cursor:pointer}',
    '.dark #fg-close{color:#F5C557;border-color:rgba(224,168,62,.4)}',
    '#fg-body{padding:16px 18px calc(18px + env(safe-area-inset-bottom));color:#3A2E24;min-height:260px}',
    '.dark #fg-body{color:#C4B5A5}',
    '.fg-rules{list-style:none;padding:0;margin:0 0 16px;display:flex;flex-direction:column;gap:9px}',
    '.fg-rules li{display:flex;gap:9px;align-items:flex-start;font-size:13px;line-height:1.6;color:#1A1410}',
    '.dark .fg-rules li{color:#F5EDE0}',
    '.fg-rules .n{width:20px;height:20px;border-radius:50%;background:rgba(139,26,26,.08);color:#8B1A1A;',
      'font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}',
    '.fg-best{font-size:12px;color:#C8861E;font-weight:700;margin-bottom:14px}',
    '.fg-go{display:block;width:100%;padding:13px;border:none;border-radius:12px;font-size:15px;font-weight:700;cursor:pointer;',
      'background:#8B1A1A;color:#FFF9F2;transition:filter .15s}',
    '.fg-go:hover{filter:brightness(1.1)}',
    '.fg-stage{position:relative;margin:6px auto 14px;width:min(220px,60vw);aspect-ratio:1/1.05;',
      'border-radius:16px;background:radial-gradient(60% 80% at 50% 30%,#3A2018,#190E08);',
      'border:1px solid rgba(224,168,62,.3);box-shadow:inset 0 0 30px rgba(0,0,0,.5);overflow:hidden}',
    '.fg-stage img{width:100%;height:100%;object-fit:contain}',
    '.fg-stage .fg-tag{position:absolute;left:10px;top:8px;padding:3px 10px;border-radius:999px;',
      'background:rgba(20,12,8,.55);color:#FFE9C8;font-size:11px;letter-spacing:1px}',
    '.fg-stage.flip img{animation:fgFlip .18s ease}',
    '@keyframes fgFlip{0%{transform:scaleX(1)}50%{transform:scaleX(.06)}100%{transform:scaleX(1)}}',
    '@media (prefers-reduced-motion:reduce){.fg-stage.flip img{animation:none}}',
    '.fg-q{font-size:16px;font-weight:700;color:#1A1410;text-align:center;margin-bottom:14px;line-height:1.6}',
    '.dark .fg-q{color:#F5EDE0}',
    '.fg-opt{display:flex;align-items:center;justify-content:center;width:100%;padding:12px;margin-bottom:9px;',
      'border-radius:12px;border:1.5px solid #E8DCC8;background:#FFFDF8;cursor:pointer;font-size:15px;font-weight:700;color:#1A1410;transition:all .15s}',
    '.dark .fg-opt{background:#2A2018;border-color:#3A2C20;color:#F5EDE0}',
    '.fg-opt:hover:not(:disabled){border-color:rgba(139,26,26,.5)}',
    '.fg-opt.right{border-color:#3D8B4F;background:rgba(61,139,79,.1);color:#2E6B3D}',
    '.fg-opt.wrong{border-color:#B03A2E;background:rgba(176,58,46,.07);color:#8F2E23}',
    '.fg-fb{font-size:13px;font-weight:700;text-align:center;margin-bottom:10px;min-height:18px}',
    '.fg-fb.ok{color:#3D8B4F}.fg-fb.bad{color:#B03A2E}',
    '.fg-dots{display:flex;gap:6px;justify-content:center;margin-bottom:12px}',
    '.fg-dot{width:22px;height:5px;border-radius:999px;background:#F3EDE4}',
    '.fg-dot.cur{background:#C8861E}.fg-dot.ok{background:#3D8B4F}.fg-dot.bad{background:#B03A2E}',
    '.dark .fg-dot{background:#3A2C20}',
    '.fg-rank{font-family:"Ma Shan Zheng",serif;font-size:34px;color:#8B1A1A;text-align:center;letter-spacing:4px}',
    '.dark .fg-rank{color:#E0584E}',
    '.fg-score{text-align:center;font-size:13px;color:#6b6b6b;margin:4px 0 2px}',
    '.fg-rank-sub{text-align:center;font-size:12px;color:#5C4A3A;margin-bottom:14px}',
    '.fg-coupon{margin:0 auto 12px;max-width:300px;padding:12px 16px;border-radius:12px;text-align:center;',
      'border:1.5px dashed rgba(200,134,30,.6);background:rgba(224,168,62,.08)}',
    '.fg-coupon .ct{font-size:10px;color:#5C4A3A;font-weight:700}',
    '.fg-coupon .cc{font-size:18px;font-weight:800;letter-spacing:2px;color:#C8861E;margin:2px 0}',
    '.fg-coupon .cu{font-size:10px;color:#6b6b6b}',
    '.fg-passed{font-size:12px;font-weight:700;color:#3D8B4F;text-align:center;margin-bottom:14px}',
    '.fg-row{display:flex;gap:10px}',
    '.fg-ghost{flex:1;padding:12px;border-radius:12px;border:1px solid rgba(139,26,26,.3);background:transparent;',
      'color:#8B1A1A;font-size:13px;font-weight:700;cursor:pointer}',
    '@media(prefers-reduced-motion:reduce){#fg-panel{transition:none}}'
  ].join('\n');

  function buildPanel() {
    if (document.getElementById('fg-panel')) return;
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);
    var mask = document.createElement('div');
    mask.id = 'fg-mask';
    mask.addEventListener('click', closePanel);
    document.body.appendChild(mask);
    var panel = document.createElement('div');
    panel.id = 'fg-panel';
    panel.setAttribute('role', 'dialog');
    panel.innerHTML =
      '<div class="fg-head">' +
        '<div><h3 id="fg-title"></h3><div class="fg-sub" id="fg-subtitle"></div></div>' +
        '<button id="fg-close" aria-label="close">✕</button>' +
      '</div><div id="fg-body"></div>';
    document.body.appendChild(panel);
    panel.querySelector('#fg-close').addEventListener('click', closePanel);
    renderHead();
  }
  function renderHead() {
    var h = document.getElementById('fg-title'), s2 = document.getElementById('fg-subtitle');
    if (h) h.textContent = t('panelTitle');
    if (s2) s2.textContent = t('panelSub');
  }

  function showStart() {
    var body = document.getElementById('fg-body');
    var best = loadBest();
    body.innerHTML =
      '<h4 style="font-size:14px;font-weight:700;margin-bottom:10px;color:#1A1410">' + t('startHead') + '</h4>' +
      '<ul class="fg-rules">' +
        '<li><span class="n">1</span><span>' + t('r1') + '</span></li>' +
        '<li><span class="n">2</span><span>' + t('r2') + '</span></li>' +
        '<li><span class="n">3</span><span>' + t('r3') + '</span></li>' +
      '</ul>' +
      (best > 0 ? '<div class="fg-best">🏆 ' + t('best') + ': ' + best + ' / 3</div>' : '') +
      '<button class="fg-go" id="fg-start">' + t('startBtn') + '</button>';
    document.getElementById('fg-start').addEventListener('click', function () {
      round = { score: 0, idx: 0 };
      playLevel(0);
    });
  }

  function playLevel(levelIdx) {
    round.level = levelIdx;
    var lv = buildRound(levelIdx);
    round.flips = lv.flips; round.final = lv.final; round.askCount = lv.askCount; round.answer = lv.answer;
    var body = document.getElementById('fg-body');
    var dots = LEVELS.map(function (_, k) {
      var cls = 'fg-dot' + (k === levelIdx ? ' cur' : '');
      return '<span class="' + cls + '"></span>';
    }).join('');
    body.innerHTML =
      '<div class="fg-dots">' + dots + '</div>' +
      '<div style="font-size:11px;font-weight:700;color:#6b6b6b;margin-bottom:6px">' + t('level')(levelIdx + 1, LEVELS.length) + '</div>' +
      '<div class="fg-stage" id="fg-stage"><span class="fg-tag" id="fg-stage-tag"></span><img id="fg-stage-img" alt="脸谱"></div>' +
      '<div id="fg-play-area"></div>';
    var stage = body.querySelector('#fg-stage');
    var imgEl = body.querySelector('#fg-stage-img');
    var tag = body.querySelector('#fg-stage-tag');
    tag.textContent = t('prep');
    imgEl.src = img(lv.seq[0]);
    var playArea = body.querySelector('#fg-play-area');

    // 预备 1.2s → 连续变脸 → 出题
    setTimeout(function () {
      tag.textContent = t('watch');
      var i = 1;
      var timer = setInterval(function () {
        if (i >= lv.seq.length) {
          clearInterval(timer);
          setTimeout(function () { askQuestion(); }, 350);
          return;
        }
        stage.classList.add('flip');
        var idx = i; // 闭包捕获当前帧（i 会继续自增）
        setTimeout(function () {
          imgEl.src = img(lv.seq[idx]);
          stage.classList.remove('flip');
        }, 90);
        i++;
      }, LEVELS[levelIdx].interval);
    }, 1200);

    function askQuestion() {
      var opts;
      if (lv.askCount) {
        var a = lv.answer;
        opts = shuffle([a, a + 1 + Math.floor(Math.random() * 2), Math.max(2, a - 1 - Math.floor(Math.random() * 2))]);
        opts = dedupeNumbers(opts, a);
      } else {
        var others = MASKS.filter(function (m) { return m.c !== lv.final; })
          .sort(function () { return Math.random() - 0.5; }).slice(0, 2)
          .map(function (m) { return m.c; });
        opts = shuffle([lv.final].concat(others));
      }
      playArea.innerHTML =
        '<div class="fg-q">' + (lv.askCount ? t('qCount') : t('qFinal')) + '</div>' +
        '<div id="fg-opts">' + opts.map(function (o) {
          var label = lv.askCount ? o + (lang() === 'zh' ? ' 次' : (o > 1 ? ' times' : ' time')) : maskName(o);
          return '<button class="fg-opt" data-v="' + o + '">' + label + '</button>';
        }).join('') + '</div>' +
        '<div class="fg-fb" id="fg-fb"></div>' +
        '<button class="fg-go" id="fg-next" style="visibility:hidden"></button>';
      var fb = playArea.querySelector('#fg-fb');
      var next = playArea.querySelector('#fg-next');
      playArea.querySelectorAll('.fg-opt').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var v = btn.getAttribute('data-v');
          var ok = lv.askCount ? parseInt(v, 10) === lv.answer : v === lv.answer;
          if (ok) round.score++;
          playArea.querySelectorAll('.fg-opt').forEach(function (b) {
            b.disabled = true;
            var bv = b.getAttribute('data-v');
            var isRight = lv.askCount ? parseInt(bv, 10) === lv.answer : bv === lv.answer;
            if (isRight) b.classList.add('right');
            else if (b === btn) b.classList.add('wrong');
          });
          fb.textContent = ok ? t('right') : t('wrong') + (lv.askCount ? lv.answer : maskName(lv.final));
          fb.className = 'fg-fb ' + (ok ? 'ok' : 'bad');
          next.style.visibility = 'visible';
          next.textContent = levelIdx === LEVELS.length - 1 ? t('seeResult') : t('next');
        });
      });
      next.addEventListener('click', function () {
        if (levelIdx === LEVELS.length - 1) showResult();
        else playLevel(levelIdx + 1);
      });
    }
  }

  function dedupeNumbers(arr, answer) {
    var seen = {};
    return arr.map(function (v) {
      if (v === answer) { seen[v] = true; return v; } // 正确答案保持原值
      while (seen[v]) v++; // 仅干扰项去重
      seen[v] = true;
      return v;
    });
  }
  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function showResult() {
    var body = document.getElementById('fg-body');
    var n = round.score;
    var best = loadBest();
    if (n > best) { best = n; localStorage.setItem(BEST_KEY, String(best)); }
    var passed = n >= 2;
    var rank = n === 3 ? t('rankTop') : passed ? t('rankMid') : t('rankLow');
    var sub = n === 3 ? t('rankSubTop') : passed ? t('rankSubMid') : t('rankSubLow');
    body.innerHTML =
      '<div class="fg-rank">' + rank + '</div>' +
      '<div class="fg-score">' + t('pass')(n) + '</div>' +
      '<div class="fg-rank-sub">' + sub + '</div>' +
      (passed
        ? '<div class="fg-coupon"><div class="ct">' + t('couponTitle') + '</div>' +
          '<div class="cc">CHUAN-FACE-7</div><div class="cu">' + t('couponUse') + '</div></div>' +
          '<div class="fg-passed">' + t('passedExtra') + '</div>'
        : '') +
      '<div class="fg-row">' +
        '<button class="fg-ghost" id="fg-retry">' + t('retry') + '</button>' +
        '<button class="fg-go" id="fg-done" style="flex:1.4">' + t('close') + '</button>' +
      '</div>';
    body.querySelector('#fg-retry').addEventListener('click', function () {
      round = { score: 0, idx: 0 };
      playLevel(0);
    });
    body.querySelector('#fg-done').addEventListener('click', closePanel);
  }

  function openPanel() {
    if (window.OperaQuiz) window.OperaQuiz.close();
    if (window.Passport) window.Passport.close();
    buildPanel();
    round = { score: 0, idx: 0 };
    showStart();
    document.getElementById('fg-mask').classList.add('open');
    document.getElementById('fg-panel').classList.add('open');
  }
  function closePanel() {
    var m = document.getElementById('fg-mask'), p = document.getElementById('fg-panel');
    if (m) m.classList.remove('open');
    if (p) p.classList.remove('open');
  }

  window.addEventListener('app:langchange', function () {
    renderEntryTexts();
    renderHead();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', injectEntry);
  else injectEntry();

  window.FaceGame = { open: openPanel, close: closePanel };
})();
