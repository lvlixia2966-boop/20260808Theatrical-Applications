/* 观剧记忆分享卡（memory-card.js）
 *
 * 业务目标：补上"离场后传播"环节——把游客今天的体验数据合成一张可保存/分享的
 *   竖版海报：日期 + 脸谱插画 + 护照章数 + 竞答/眼力最佳成绩 + 剧院落款。
 *
 * 高内聚：入口注入（个人中心）、Canvas 海报绘制、弹层，全部收敛于此。
 * 低耦合：数据只读 localStorage（chuan_passport / chuan_quiz_best / chuan_face_best）
 *   与 window.Passport（存在则用其计数）；不依赖后端；图片同源无 canvas 污染。
 */
(function () {
  'use strict';

  var UI = {
    zh: {
      cardTitle: '观剧记忆 · 分享卡', cardCta: '生成今晚的纪念海报 🖼',
      sub: '观剧纪念', brand: '四川省川剧院', footer: '百年川剧戏楼 · AI 智能同传伴你入戏',
      stampLine: function (n, total) { return '川剧护照 ' + n + ' / ' + total + ' 章'; },
      quizLine: function (n) { return '观演竞答最佳 ' + n + ' / 5'; },
      faceLine: function (n) { return '极限眼力 ' + n + ' / 3 关'; },
      applaudLine: function (n) { return '📣 全场叫好 ' + n + ' 次'; },
      capsLine: function (n) { return '字幕陪你听懂 ' + n + ' 句'; },
      save: '保存图片', close: '关闭', hint: '也可以长按图片保存 / 分享',
      emptyHint: '去看一场戏，再来生成纪念卡吧',
    },
    en: {
      cardTitle: 'Opera Memory Card', cardCta: 'Make tonight\'s poster 🖼',
      sub: 'OPERA MEMORY', brand: '四川省川剧院', footer: 'Century-old opera house · AI live interpretation',
      stampLine: function (n, total) { return 'Passport ' + n + ' / ' + total + ' stamps'; },
      quizLine: function (n) { return 'Quiz best ' + n + ' / 5'; },
      faceLine: function (n) { return 'Sharp eyes ' + n + ' / 3'; },
      applaudLine: function (n) { return 'Applause x' + n; },
      capsLine: function (n) { return n + ' lines captioned live'; },
      save: 'Save image', close: 'Close', hint: 'Long-press the image to save / share',
      emptyHint: 'Come enjoy a show first, then make your card',
    },
  };
  function lang() {
    var l = localStorage.getItem('app_lang') || 'zh';
    return l.indexOf('zh') === 0 ? 'zh' : (UI[l] ? l : 'en');
  }
  function t(k) { var d = UI[lang()] || UI.en; return d[k] !== undefined ? d[k] : UI.en[k]; }

  var CSS = [
    '#mc-mask{position:fixed;inset:0;background:rgba(20,12,8,.6);z-index:430;opacity:0;pointer-events:none;transition:opacity .3s}',
    '#mc-mask.open{opacity:1;pointer-events:auto}',
    '#mc-panel{position:fixed;left:50%;top:50%;transform:translate(-50%,-46%) scale(.96);opacity:0;pointer-events:none;',
      'z-index:431;width:min(92vw,400px);max-height:90vh;overflow-y:auto;transition:all .32s cubic-bezier(.2,.8,.25,1);',
      'background:#FFFDF8;border:1px solid rgba(139,26,26,.25);border-radius:20px;box-shadow:0 24px 64px rgba(20,12,8,.4)}',
    '#mc-panel.open{transform:translate(-50%,-50%) scale(1);opacity:1;pointer-events:auto}',
    '.dark #mc-panel{background:#211812;border-color:rgba(199,62,58,.3)}',
    '#mc-panel img{display:block;width:100%;border-radius:12px;border:1px solid rgba(224,168,62,.25)}',
    '.mc-actions{display:flex;gap:10px;padding:12px 16px calc(16px + env(safe-area-inset-bottom))}',
    '.mc-save{flex:1.3;padding:12px;border:none;border-radius:12px;background:#8B1A1A;color:#FFF9F2;',
      'font-size:14px;font-weight:700;cursor:pointer}',
    '.mc-close{flex:1;padding:12px;border-radius:12px;border:1px solid rgba(139,26,26,.3);background:transparent;',
      'color:#8B1A1A;font-size:13px;font-weight:700;cursor:pointer}',
    '.dark .mc-close{color:#F5C557;border-color:rgba(224,168,62,.4)}',
    '.mc-hint{text-align:center;font-size:11px;color:#8A7B6A;padding:0 16px 6px}',
    /* 个人中心入口卡 */
    '.mc-entry{display:flex;align-items:center;gap:14px;padding:16px;border-radius:14px;cursor:pointer;transition:all .2s;',
      'background:linear-gradient(135deg,rgba(200,134,30,.08),rgba(139,26,26,.05));border:1px solid rgba(200,134,30,.35)}',
    '.mc-entry:hover{border-color:rgba(200,134,30,.7);box-shadow:0 4px 16px rgba(200,134,30,.12)}',
    '.mc-entry-ico{width:44px;height:44px;border-radius:12px;flex-shrink:0;display:flex;align-items:center;justify-content:center;',
      'background:linear-gradient(135deg,#E0A83E,#C8861E);color:#241610;transform:rotate(-3deg);box-shadow:0 2px 10px rgba(200,134,30,.3)}',
    '@media(prefers-reduced-motion:reduce){#mc-panel{transition:none}}'
  ].join('\n');

  /* ── 入口卡（个人中心） ── */
  function ensureStyles() {
    if (document.getElementById('mc-style')) return;
    var style = document.createElement('style');
    style.id = 'mc-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function injectEntry() {
    ensureStyles(); // 入口卡即渲染，样式需先行
    if (document.getElementById('mc-entry')) return;
    var host = document.getElementById('view-user-profile');
    if (!host) return;
    var anchor = document.getElementById('pp-entry') || host.querySelector('.grid.grid-cols-1');
    if (!anchor) return;
    var card = document.createElement('div');
    card.id = 'mc-entry';
    card.className = 'mc-entry';
    card.innerHTML =
      '<div class="mc-entry-ico"><i data-lucide="image" class="w-5 h-5"></i></div>' +
      '<div class="flex-1 min-w-0">' +
        '<div class="font-bold text-sm text-foreground">' + t('cardTitle') + '</div>' +
        '<div class="text-xs text-muted-foreground mt-0.5">' + t('sub') + '</div>' +
      '</div>' +
      '<span class="text-[11px] font-bold text-primary bg-primary/10 px-2 py-1 rounded-full whitespace-nowrap">' + t('cardCta') + '</span>';
    card.addEventListener('click', open);
    anchor.insertAdjacentElement('afterend', card);
    if (window.lucide) lucide.createIcons();
  }

  /* ── 数据收集 ── */
  function collect() {
    var data = { stamps: 0, stampTotal: 8, quiz: 0, face: 0 };
    try {
      var p = JSON.parse(localStorage.getItem('chuan_passport')) || {};
      data.stamps = Object.keys(p).length;
    } catch (e) { /* ignore */ }
    if (window.Passport) data.stampTotal = window.Passport.total || 8;
    data.quiz = parseInt(localStorage.getItem('chuan_quiz_best') || '0', 10) || 0;
    data.face = parseInt(localStorage.getItem('chuan_face_best') || '0', 10) || 0;
    data.applaud = parseInt(localStorage.getItem('chuan_applaud_last') || '0', 10) || 0;
    data.caps = parseInt(localStorage.getItem('chuan_caps_last') || '0', 10) || 0;
    return data;
  }

  /* ── Canvas 海报（1080x1560） ── */
  function drawPoster(data, cb) {
    var W = 1080, H = 1560;
    var canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext('2d');
    var zh = lang() === 'zh';

    var finish = function () {
      // 底：深色戏台
      var bg = ctx.createLinearGradient(0, 0, W * 0.4, H);
      bg.addColorStop(0, '#2A1710'); bg.addColorStop(0.55, '#190E08'); bg.addColorStop(1, '#160B06');
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
      // 顶/底金线
      ctx.fillStyle = 'rgba(224,168,62,.65)';
      ctx.fillRect(0, 26, W, 3); ctx.fillRect(0, H - 26, W, 3);
      // 舞台追光
      var glow = ctx.createRadialGradient(W / 2, 300, 60, W / 2, 300, 720);
      glow.addColorStop(0, 'rgba(255,205,120,.16)'); glow.addColorStop(1, 'rgba(255,205,120,0)');
      ctx.fillStyle = glow; ctx.fillRect(0, 0, W, 900);
      // 眉题
      ctx.textAlign = 'center';
      ctx.fillStyle = 'rgba(245,222,180,.85)';
      ctx.font = '30px Outfit, sans-serif';
      ctx.fillText('SICHUAN OPERA · ' + fmtDate(new Date()), W / 2, 96);
      // 脸谱主视觉
      var mask = new Image();
      mask.onload = function () {
        ctx.save();
        ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 46; ctx.shadowOffsetY = 26;
        var mw = 560, mh = mw * (mask.height / mask.width);
        ctx.drawImage(mask, (W - mw) / 2, 170, mw, mh);
        ctx.restore();
        // 标题
        ctx.fillStyle = '#E8564E';
        ctx.font = '96px "Ma Shan Zheng", serif';
        ctx.fillText(zh ? '四川省川剧院' : '四 川 省 川 剧 院', W / 2, 920);
        ctx.fillStyle = 'rgba(224,168,62,.9)';
        ctx.font = '52px "Ma Shan Zheng", serif';
        ctx.fillText(t('sub'), W / 2, 1010);
        ctx.fillStyle = 'rgba(200,134,30,.8)';
        ctx.fillRect(W / 2 - 60, 1052, 120, 3);
        // 数据行（最多三行）
        ctx.font = '40px Outfit, "PingFang SC", sans-serif';
        ctx.fillStyle = 'rgba(245,237,224,.92)';
        var lines = [t('stampLine')(data.stamps, data.stampTotal)];
        if (data.quiz > 0) lines.push(t('quizLine')(data.quiz));
        if (data.face > 0) lines.push(t('faceLine')(data.face));
        if (data.applaud > 0) lines.push(t('applaudLine')(data.applaud));
        if (data.caps > 0) lines.push(t('capsLine')(data.caps));
        var onlyStamps = data.stamps > 0 && data.quiz === 0 && data.face === 0 && data.applaud === 0 && data.caps === 0;
        if (data.stamps === 0 && data.quiz === 0 && data.face === 0 && data.applaud === 0) lines = [t('emptyHint')];
        var startY = lines.length >= 5 ? 1108 : 1150;
        var step = lines.length >= 5 ? 68 : 74;
        lines.forEach(function (line, i) { ctx.fillText(line, W / 2, startY + i * step); });
        // 落款印章
        ctx.save();
        ctx.translate(W - 168, H - 150);
        ctx.rotate(-0.09);
        ctx.fillStyle = '#A31E1C';
        ctx.fillRect(-58, -58, 116, 116);
        ctx.strokeStyle = 'rgba(255,249,242,.7)'; ctx.lineWidth = 4;
        ctx.strokeRect(-48, -48, 96, 96);
        ctx.fillStyle = '#FFF9F2';
        ctx.font = '58px "Ma Shan Zheng", serif';
        ctx.fillText('川', 0, 20);
        ctx.restore();
        // 底部落款
        ctx.fillStyle = 'rgba(245,237,224,.6)';
        ctx.font = '30px "Ma Shan Zheng", serif';
        ctx.fillText(t('brand') + ' · ' + t('footer'), W / 2, H - 78);
        cb(canvas);
      };
      mask.src = './assets/mask-red-ai-transparent.png?v=3';
    };
    // 书法字体就绪后再画（避免 canvas 回退到系统衬线）
    if (document.fonts && document.fonts.load) {
      Promise.all([
        document.fonts.load('96px "Ma Shan Zheng"'),
        document.fonts.load('30px Outfit'),
      ]).then(finish).catch(finish);
    } else finish();
  }

  function fmtDate(d) {
    var p = function (x) { return (x < 10 ? '0' : '') + x; };
    return d.getFullYear() + '.' + p(d.getMonth() + 1) + '.' + p(d.getDate());
  }

  /* ── 弹层 ── */
  function open() {
    if (!document.getElementById('mc-panel')) {
      ensureStyles();
      var mask = document.createElement('div');
      mask.id = 'mc-mask';
      mask.addEventListener('click', close);
      document.body.appendChild(mask);
      var panel = document.createElement('div');
      panel.id = 'mc-panel';
      panel.setAttribute('role', 'dialog');
      panel.innerHTML = '<img id="mc-img" alt="观剧记忆卡">' +
        '<div class="mc-hint">' + t('hint') + '</div>' +
        '<div class="mc-actions"><button class="mc-save" id="mc-save"></button><button class="mc-close" id="mc-close"></button></div>';
      document.body.appendChild(panel);
      panel.querySelector('#mc-close').addEventListener('click', close);
      panel.querySelector('#mc-save').addEventListener('click', savePng);
    }
    document.getElementById('mc-save').innerHTML = '<i data-lucide="download" class="w-4 h-4 inline-block"></i> ' + t('save');
    if (window.lucide) lucide.createIcons();
    document.getElementById('mc-close').textContent = t('close');
    var img = document.getElementById('mc-img');
    img.src = '';
    drawPoster(collect(), function (canvas) {
      img.src = canvas.toDataURL('image/png');
    });
    document.getElementById('mc-mask').classList.add('open');
    document.getElementById('mc-panel').classList.add('open');
  }
  function close() {
    var m = document.getElementById('mc-mask'), p = document.getElementById('mc-panel');
    if (m) m.classList.remove('open');
    if (p) p.classList.remove('open');
  }
  function savePng() {
    var img = document.getElementById('mc-img');
    if (!img.src) return;
    var a = document.createElement('a');
    a.href = img.src;
    a.download = 'sichuan-opera-memory-' + fmtDate(new Date()).replace(/\./g, '') + '.png';
    a.click();
  }

  window.addEventListener('app:langchange', injectEntry);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', injectEntry);
  else injectEntry();

  window.MemoryCard = { open: open, close: close };
})();
