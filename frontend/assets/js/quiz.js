/* 观演知识竞答模块（quiz.js）
 *
 * 业务目标：填补「候场 / 中场 / 离场」空白时段——5 道川剧小题，
 *   通关（≥3 题）解锁「懂戏之人」护照印章 + 文创九折邀请码。
 *
 * 高内聚：入口卡注入、题库（zh/en 双语）、答题抽屉、判定与结果页，全部收敛于此。
 * 低耦合：
 *   - 入口卡由本模块注入 #view-spectate 的伴游卡之后，不改 index.html 结构；
 *   - 抽屉复用伴游弹层的视觉语言（底部抽屉 + 深红描边），样式独立命名 qz-*；
 *   - 通关后派发 window 事件 'app:quiz:passed'，印章授予由 passport.js 完成；
 *   - 最佳成绩存 localStorage('chuan_quiz_best')。
 */
(function () {
  'use strict';

  var BEST_KEY = 'chuan_quiz_best';
  var QUESTIONS_PER_ROUND = 5;
  var PASS_LINE = 3;

  /* ── 题库（q: 题干, opts: 选项, a: 正确下标）── */
  var BANK = [
    { q: { zh: '「变脸」属于川剧的哪一类技艺？', en: 'Bianlian (face-changing) is a kind of…' },
      opts: [{ zh: '表演特技', en: 'Stage trick' }, { zh: '唱腔流派', en: 'Singing style' }, { zh: '乐器演奏', en: 'Instrumental art' }], a: 0 },
    { q: { zh: '川剧三大绝技是变脸、吐火，以及《皮金滚灯》中的——', en: 'Besides face-changing and fire-spitting, "Pijin Rolling the Lantern" features…' },
      opts: [{ zh: '顶碗', en: 'Bowl balancing' }, { zh: '滚灯', en: 'Rolling the lantern' }, { zh: '走索', en: 'Rope walking' }], a: 1 },
    { q: { zh: '脸谱中，红色通常象征人物的——', en: 'A red face mask usually symbolizes…' },
      opts: [{ zh: '忠勇正义', en: 'Loyalty and bravery' }, { zh: '奸诈多疑', en: 'Treachery' }, { zh: '滑稽诙谐', en: 'Comic relief' }], a: 0 },
    { q: { zh: '「川剧高腔」最鲜明的特色是——', en: 'The signature of Sichuan "Gaoqiang" singing is…' },
      opts: [{ zh: '纯器乐伴奏', en: 'Purely instrumental' }, { zh: '一人唱、众人帮腔', en: 'Lead voice with chorus backing' }, { zh: '只念不唱', en: 'Spoken only, no singing' }], a: 1 },
    { q: { zh: '剧场观演礼仪正确的是——', en: 'Which is proper theatre etiquette?' },
      opts: [{ zh: '迟到后于幕间入场', en: 'Enter between acts if late' }, { zh: '随时走动拍照', en: 'Walk around and photograph freely' }, { zh: '开闪光灯录像', en: 'Use flash while recording' }], a: 0 },
    { q: { zh: '四川盖碗茶的「三件套」指的是——', en: 'A gaiwan tea set consists of…' },
      opts: [{ zh: '壶、杯、盘', en: 'Pot, cup and plate' }, { zh: '茶碗、茶盖、茶船', en: 'Bowl, lid and saucer' }, { zh: '碗、筷、勺', en: 'Bowl, chopsticks and spoon' }], a: 1 },
    { q: { zh: '川剧《白蛇传》里最具特色的桥段是——', en: 'The most celebrated scene of the Sichuan-opera "White Snake" is…' },
      opts: [{ zh: '大闹天宫', en: 'Havoc in Heaven' }, { zh: '三打白骨精', en: 'Thrice beating the skeleton demon' }, { zh: '水漫金山', en: 'Flooding Jinshan Temple' }], a: 2 },
    { q: { zh: '「蜀戏冠天下」这句话形容的是——', en: '"Shu opera crowns the world" praises…' },
      opts: [{ zh: '川剧历史悠久、影响深远', en: 'The opera\'s long history and influence' }, { zh: '蜀锦冠绝天下', en: 'Shu brocade craftsmanship' }, { zh: '四川火锅天下第一', en: 'Sichuan hotpot being No.1' }], a: 0 },
    { q: { zh: '川剧锣鼓中的「大锣大钹」属于——', en: 'The big gong and cymbals in Sichuan opera belong to…' },
      opts: [{ zh: '拉弦乐器', en: 'Bowed strings' }, { zh: '吹管乐器', en: 'Wind instruments' }, { zh: '打击乐器', en: 'Percussion' }], a: 2 },
    { q: { zh: '观看变脸时，观众正确的做法是——', en: 'While watching face-changing, you should…' },
      opts: [{ zh: '紧盯演员面部找破绽', en: 'Stare at the face to spot the trick' }, { zh: '欣赏整体身段与锣鼓配合', en: 'Enjoy the moves with the percussion' }, { zh: '上台近距离观察', en: 'Step on stage for a closer look' }], a: 1 },
  ];

  var UI = {
    zh: {
      cardTitle: '观演小试 · 川剧知音挑战', cardSub: '五道小题认识川剧，通关解锁护照印章与文创礼遇',
      cardBtn: '开始挑战', panelTitle: '川剧知音挑战', panelSub: '观演知识 · 五题速答',
      startHead: '怎么玩', rule1: '随机 5 题，每题 3 选 1，即时揭晓对错',
      rule2: '答对 3 题即通关', rule3: '通关解锁「懂戏之人」护照印章 + 文创九折邀请码',
      best: '最佳成绩', startBtn: '开 始', qProgress: function (i, n) { return '第 ' + i + ' / ' + n + ' 题'; },
      right: '答对了！', wrong: '差一点，正确答案已标出', next: '下一题', seeResult: '查看结果',
      resultHead: '挑战结果', score: function (n) { return '答对 ' + n + ' / 5 题'; },
      rank5: '巴蜀名角', rank4: '川剧知音', rank3: '戏剧新秀', rankLow: '初入门',
      rankSub5: '满分开场，川剧的门票你拿捏了', rankSub4: '只差一步登台，令人敬佩',
      rankSub3: '通关！川剧的大门为你敞开', rankSubLow: '多看看伴游问答，下次必过',
      couponTitle: '文创九折邀请码', couponUse: '结账时向工作人员出示即可',
      passedExtra: '🪪 已解锁护照印章「懂戏之人」',
      retry: '再来一轮', close: '收起',
    },
    en: {
      cardTitle: 'Opera Quiz · Know Your Sichuan Opera', cardSub: 'Five quick questions — pass to unlock a passport stamp and a merch treat',
      cardBtn: 'Start', panelTitle: 'Opera Quiz', panelSub: 'Five questions, instant fun',
      startHead: 'How it works', rule1: '5 random questions, 3 choices each, instant feedback',
      rule2: 'Answer 3 correctly to pass', rule3: 'Passing unlocks the "Opera Insider" stamp + a 10% merch code',
      best: 'Best score', startBtn: 'Start', qProgress: function (i, n) { return 'Question ' + i + ' / ' + n; },
      right: 'Correct!', wrong: 'Not quite — the answer is highlighted', next: 'Next', seeResult: 'See result',
      resultHead: 'Your result', score: function (n) { return n + ' / 5 correct'; },
      rank5: 'Opera Star', rank4: 'Opera Insider', rank3: 'Rising Fan', rankLow: 'Newcomer',
      rankSub5: 'A perfect round — the stage is yours', rankSub4: 'One step from the spotlight, impressive',
      rankSub3: 'Passed! The world of Sichuan opera opens for you', rankSubLow: 'Ask the AI companion, then try again',
      couponTitle: '10% merch invite code', couponUse: 'Show this code at the souvenir desk',
      passedExtra: '🪪 Passport stamp "Opera Insider" unlocked',
      retry: 'Play again', close: 'Close',
    },
  };

  function lang() {
    var l = localStorage.getItem('app_lang') || 'zh';
    return l.indexOf('zh') === 0 ? 'zh' : (UI[l] ? l : 'en');
  }
  function t(key) {
    var d = UI[lang()] || UI.en;
    var v = d[key] !== undefined ? d[key] : UI.en[key];
    return typeof v === 'function' ? v : v;
  }
  function pick(obj) { return obj ? (obj[lang()] || obj.en || obj.zh || '') : ''; }

  /* ── 状态 ── */
  var round = null; // { qs: [题], idx, score, picked, passed }

  function loadBest() { return parseInt(localStorage.getItem(BEST_KEY) || '0', 10) || 0; }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function newRound() {
    var qs = shuffle(BANK).slice(0, QUESTIONS_PER_ROUND).map(function (item) {
      var order = shuffle(item.opts.map(function (_, k) { return k; }));
      return { q: item.q, opts: item.opts, a: order.indexOf(item.a), order: order };
    });
    round = { qs: qs, idx: 0, score: 0, picked: null, passed: false };
  }

  /* ── 入口卡 ── */
  function injectEntry() {
    if (document.getElementById('section-quiz')) return;
    var ref = document.getElementById('section-subtitles');
    var host = document.getElementById('view-spectate');
    if (!ref || !host) return;
    var sec = document.createElement('section');
    sec.id = 'section-quiz';
    sec.className = 'card-modern bg-card border border-accent/30 p-5 sm:p-6 relative overflow-hidden';
    sec.innerHTML =
      '<div class="flex items-center gap-3 sm:gap-4">' +
        '<div class="w-10 h-10 rounded-full bg-accent/10 border border-accent/25 flex items-center justify-center flex-shrink-0">' +
          '<i data-lucide="trophy" class="w-5 h-5 text-accent"></i>' +
        '</div>' +
        '<div class="flex-1 min-w-0">' +
          '<h3 class="font-display text-base sm:text-lg font-bold text-foreground" id="qz-card-title"></h3>' +
          '<p class="text-xs text-muted-foreground truncate" id="qz-card-sub"></p>' +
        '</div>' +
        '<button id="qz-open" class="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition-all shadow-sm whitespace-nowrap flex-shrink-0"></button>' +
      '</div>';
    ref.insertAdjacentElement('afterend', sec);
    sec.querySelector('#qz-open').addEventListener('click', openPanel);
    renderEntryTexts();
    if (window.lucide) lucide.createIcons();
  }

  function renderEntryTexts() {
    var title = document.getElementById('qz-card-title');
    var sub = document.getElementById('qz-card-sub');
    var btn = document.getElementById('qz-open');
    if (title) title.textContent = t('cardTitle');
    if (sub) sub.textContent = t('cardSub');
    if (btn) btn.textContent = t('cardBtn');
  }

  /* ── 抽屉 ── */
  var CSS = [
    '#qz-mask{position:fixed;inset:0;background:rgba(20,12,8,.45);z-index:400;opacity:0;pointer-events:none;transition:opacity .3s}',
    '#qz-mask.open{opacity:1;pointer-events:auto}',
    '#qz-panel{position:fixed;left:0;right:0;bottom:0;z-index:410;max-width:560px;margin:0 auto;',
      'background:#FFFDF8;border:1px solid rgba(139,26,26,.18);border-bottom:none;',
      'border-radius:22px 22px 0 0;box-shadow:0 -12px 40px rgba(20,12,8,.25);',
      'transform:translateY(105%);transition:transform .38s cubic-bezier(.2,.8,.25,1)}',
    '#qz-panel.open{transform:translateY(0)}',
    '#qz-panel .qz-head{display:flex;align-items:center;justify-content:space-between;padding:14px 18px 10px;border-bottom:1px solid rgba(139,26,26,.10)}',
    '#qz-panel .qz-head h3{font-family:"Ma Shan Zheng",serif;font-size:22px;color:#8B1A1A;letter-spacing:2px;line-height:1}',
    '#qz-panel .qz-sub{font-size:11px;color:#6b6b6b;margin-top:3px}',
    '#qz-close{width:30px;height:30px;border-radius:50%;border:1px solid rgba(139,26,26,.2);background:transparent;color:#8B1A1A;font-size:14px;cursor:pointer}',
    '#qz-body{padding:16px 18px calc(18px + env(safe-area-inset-bottom));min-height:280px}',
    '.qz-rules{list-style:none;padding:0;margin:0 0 16px;display:flex;flex-direction:column;gap:9px}',
    '.qz-rules li{display:flex;gap:9px;align-items:flex-start;font-size:13px;color:#1c1c1c;line-height:1.6}',
    '.qz-rules .n{width:20px;height:20px;border-radius:50%;background:rgba(139,26,26,.08);color:#8B1A1A;',
      'font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}',
    '.qz-best{font-size:12px;color:#C8861E;font-weight:700;margin-bottom:14px}',
    '.qz-go{display:block;width:100%;padding:13px;border:none;border-radius:12px;font-size:15px;font-weight:700;cursor:pointer;',
      'background:#8B1A1A;color:#FFF9F2;transition:all .15s}',
    '.qz-go:hover{filter:brightness(1.1)}',
    '.qz-dots{display:flex;gap:6px;justify-content:center;margin-bottom:14px}',
    '.qz-dot{width:22px;height:5px;border-radius:999px;background:#F3EDE4;transition:all .3s}',
    '.qz-dot.cur{background:#C8861E}',
    '.qz-dot.ok{background:#3D8B4F}', '.qz-dot.bad{background:#B03A2E}',
    '.qz-question{font-size:16px;font-weight:700;color:#1c1c1c;line-height:1.65;margin-bottom:14px}',
    '.qz-opt{display:flex;align-items:center;gap:10px;width:100%;text-align:left;padding:12px 14px;margin-bottom:9px;',
      'border-radius:12px;border:1.5px solid #E8DCC8;background:#FFFDF8;cursor:pointer;',
      'font-size:14px;color:#1c1c1c;transition:all .15s;line-height:1.5}',
    '.qz-opt:hover:not(:disabled){border-color:rgba(139,26,26,.45)}',
    '.qz-opt:disabled{cursor:default}',
    '.qz-opt .k{width:22px;height:22px;border-radius:50%;border:1px solid #E8DCC8;',
      'font-size:11px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:#6b6b6b}',
    '.qz-opt.right{border-color:#3D8B4F;background:rgba(61,139,79,.08);font-weight:700}',
    '.qz-opt.right .k{background:#3D8B4F;border-color:#3D8B4F;color:#fff}',
    '.qz-opt.wrong{border-color:#B03A2E;background:rgba(176,58,46,.06)}',
    '.qz-opt.wrong .k{background:#B03A2E;border-color:#B03A2E;color:#fff}',
    '.qz-fb{font-size:12px;font-weight:700;margin:2px 0 10px;min-height:16px}',
    '.qz-fb.ok{color:#3D8B4F}', '.qz-fb.bad{color:#B03A2E}',
    '.qz-rank{font-family:"Ma Shan Zheng",serif;font-size:34px;color:#8B1A1A;text-align:center;letter-spacing:4px}',
    '.qz-score{text-align:center;font-size:13px;color:#6b6b6b;margin:4px 0 2px}',
    '.qz-rank-sub{text-align:center;font-size:12px;color:#5C4A3A;margin-bottom:14px;line-height:1.6}',
    '.qz-coupon{position:relative;margin:0 auto 12px;max-width:300px;padding:12px 16px;border-radius:12px;text-align:center;',
      'border:1.5px dashed rgba(200,134,30,.6);background:rgba(224,168,62,.08)}',
    '.qz-coupon .ct{font-size:10px;color:#5C4A3A;font-weight:700}',
    '.qz-coupon .cc{font-size:18px;font-weight:800;letter-spacing:2px;color:#C8861E;margin:2px 0;font-variant-numeric:tabular-nums}',
    '.qz-coupon .cu{font-size:10px;color:#6b6b6b}',
    '.qz-passed{font-size:12px;font-weight:700;color:#3D8B4F;text-align:center;margin-bottom:14px}',
    '.qz-row{display:flex;gap:10px}',
    '.qz-ghost{flex:1;padding:12px;border-radius:12px;border:1px solid rgba(139,26,26,.3);background:transparent;',
      'color:#8B1A1A;font-size:13px;font-weight:700;cursor:pointer}',
    '.dark #qz-panel{background:#211812;border-color:rgba(199,62,58,.3)}',
    '.dark #qz-panel .qz-head{border-color:rgba(224,168,62,.15)}',
    '.dark .qz-opt{background:#2A2018;border-color:#3A2C20;color:#F5EDE0}',
    '.dark .qz-opt:hover:not(:disabled){border-color:rgba(224,168,62,.5)}',
    '.dark .qz-question{color:#F5EDE0}',
    '.dark .qz-rules li,.dark #qz-body h4{color:#F5EDE0}',
    '.dark .qz-dot{background:#3A2C20}',
    '#qz-body{color:#3A2E24}',
    '.qz-sec-head{font-size:14px;font-weight:700;margin-bottom:10px;color:#1A1410}',
    '.dark #qz-body{color:#C4B5A5}',
    '.dark .qz-sec-head{color:#F5EDE0}',
    '.dark .qz-rank-sub{color:#C4B5A5}',
    '.dark .qz-score{color:#8A7B6A}',
    '.dark .qz-coupon .ct{color:#C4B5A5}',
    '.dark .qz-coupon .cu{color:#8A7B6A}',
    '.dark .qz-rank{color:#E0584E}',
    '@media(prefers-reduced-motion:reduce){#qz-panel{transition:none}}'
  ].join('\n');

  function buildPanel() {
    if (document.getElementById('qz-panel')) return;
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    var mask = document.createElement('div');
    mask.id = 'qz-mask';
    mask.addEventListener('click', closePanel);
    document.body.appendChild(mask);

    var panel = document.createElement('div');
    panel.id = 'qz-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', '川剧知音挑战');
    panel.innerHTML =
      '<div class="qz-head">' +
        '<div><h3 id="qz-title"></h3><div class="qz-sub" id="qz-subtitle"></div></div>' +
        '<button id="qz-close" aria-label="关闭">✕</button>' +
      '</div>' +
      '<div id="qz-body"></div>';
    document.body.appendChild(panel);
    panel.querySelector('#qz-close').addEventListener('click', closePanel);
    renderHead();
  }

  function renderHead() {
    var h = document.getElementById('qz-title');
    var s = document.getElementById('qz-subtitle');
    if (h) h.textContent = t('panelTitle');
    if (s) s.textContent = t('panelSub');
  }

  function showStart() {
    var body = document.getElementById('qz-body');
    if (!body) return;
    var best = loadBest();
    body.innerHTML =
      '<h4 class="qz-sec-head">' + t('startHead') + '</h4>' +
      '<ul class="qz-rules">' +
        '<li><span class="n">1</span><span>' + t('rule1') + '</span></li>' +
        '<li><span class="n">2</span><span>' + t('rule2') + '</span></li>' +
        '<li><span class="n">3</span><span>' + t('rule3') + '</span></li>' +
      '</ul>' +
      (best > 0 ? '<div class="qz-best">🏆 ' + t('best') + '：' + best + ' / 5</div>' : '') +
      '<button class="qz-go" id="qz-start">' + t('startBtn') + '</button>';
    body.querySelector('#qz-start').addEventListener('click', function () { showQuestion(); });
  }

  function showQuestion() {
    var body = document.getElementById('qz-body');
    if (!body || !round) return;
    if (round.idx >= round.qs.length) { showResult(); return; }
    var item = round.qs[round.idx];
    var dots = round.qs.map(function (_, k) {
      var cls = 'qz-dot';
      if (k < round.idx) cls += round.marks && round.marks[k] ? ' ok' : ' bad';
      if (k === round.idx) cls += ' cur';
      return '<span class="' + cls + '"></span>';
    }).join('');
    body.innerHTML =
      '<div class="qz-dots">' + dots + '</div>' +
      '<div style="font-size:11px;color:#6b6b6b;font-weight:700;margin-bottom:6px">' + t('qProgress')(round.idx + 1, round.qs.length) + '</div>' +
      '<div class="qz-question">' + escapeHtml(pick(item.q)) + '</div>' +
      '<div id="qz-opts">' +
        item.order.map(function (oi, pos) {
          return '<button class="qz-opt" data-oi="' + oi + '"><span class="k">' + 'ABC'[pos] + '</span><span>' + escapeHtml(pick(item.opts[oi])) + '</span></button>';
        }).join('') +
      '</div>' +
      '<div class="qz-fb" id="qz-fb"></div>' +
      '<button class="qz-go" id="qz-next" style="visibility:hidden"></button>';
    if (!round.marks) round.marks = {};
    var fb = body.querySelector('#qz-fb');
    var next = body.querySelector('#qz-next');

    body.querySelectorAll('.qz-opt').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (round.picked !== null) return;
        round.picked = parseInt(btn.getAttribute('data-oi'), 10);
        var ok = round.picked === item.a;
        if (ok) round.score++;
        round.marks[round.idx] = ok;
        body.querySelectorAll('.qz-opt').forEach(function (b) {
          b.disabled = true;
          var oi = parseInt(b.getAttribute('data-oi'), 10);
          if (oi === item.a) b.classList.add('right');
          else if (oi === round.picked) b.classList.add('wrong');
        });
        fb.textContent = ok ? t('right') : t('wrong');
        fb.className = 'qz-fb ' + (ok ? 'ok' : 'bad');
        next.style.visibility = 'visible';
        next.textContent = round.idx === round.qs.length - 1 ? t('seeResult') : t('next');
      });
    });
    next.addEventListener('click', function () {
      round.idx++;
      round.picked = null;
      showQuestion();
    });
  }

  function showResult() {
    var body = document.getElementById('qz-body');
    if (!body || !round) return;
    var n = round.score;
    var best = loadBest();
    if (n > best) { best = n; localStorage.setItem(BEST_KEY, String(best)); }
    var passed = n >= PASS_LINE;
    var rank = n === 5 ? t('rank5') : n === 4 ? t('rank4') : passed ? t('rank3') : t('rankLow');
    var sub = n === 5 ? t('rankSub5') : n === 4 ? t('rankSub4') : passed ? t('rankSub3') : t('rankSubLow');
    round.passed = passed;

    body.innerHTML =
      '<div class="qz-rank">' + rank + '</div>' +
      '<div class="qz-score">' + t('score')(n) + '</div>' +
      '<div class="qz-rank-sub">' + sub + '</div>' +
      (passed
        ? '<div class="qz-coupon"><div class="ct">' + t('couponTitle') + '</div>' +
          '<div class="cc">CHUAN-GOLD-9</div><div class="cu">' + t('couponUse') + '</div></div>' +
          '<div class="qz-passed">' + t('passedExtra') + '</div>'
        : '') +
      '<div class="qz-row">' +
        '<button class="qz-ghost" id="qz-retry">' + t('retry') + '</button>' +
        '<button class="qz-go" id="qz-done" style="flex:1.4">' + t('close') + '</button>' +
      '</div>';
    body.querySelector('#qz-retry').addEventListener('click', function () {
      newRound();
      showQuestion();
    });
    body.querySelector('#qz-done').addEventListener('click', closePanel);

    if (passed) {
      // 通关：广播事件（passport.js 监听授章），幂等
      window.dispatchEvent(new CustomEvent('app:quiz:passed', { detail: { score: n } }));
    }
  }

  function openPanel() {
    if (window.Passport) window.Passport.close();
    buildPanel();
    newRound();
    showStart();
    document.getElementById('qz-mask').classList.add('open');
    document.getElementById('qz-panel').classList.add('open');
  }
  function closePanel() {
    var m = document.getElementById('qz-mask'), p = document.getElementById('qz-panel');
    if (m) m.classList.remove('open');
    if (p) p.classList.remove('open');
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  window.addEventListener('app:langchange', function () {
    renderEntryTexts();
    renderHead();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', injectEntry);
  else injectEntry();

  window.OperaQuiz = { open: openPanel, close: closePanel };
})();
