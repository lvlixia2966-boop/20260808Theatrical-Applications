/* 文创面具典故语音：独立小模块，负责典故文案与 TTS 播放控制。
 *
 * 高内聚：典故文案（中英预置，杜绝机翻错典故）+ 播放互斥 + 按钮状态，全部收敛于此。
 * 低耦合：只通过 data-story 按钮属性与 window.StoryAudio 接口与页面交互；
 *        语音复用后端 /api/tts/synthesize；语言跟随全局 app_lang（zh 之外的语种回退英文典故）。
 * 页面在视图/语言切换时调用 StoryAudio.stop() 停止，避免「看不见的卡片还在响」。
 * 关屏播放：<audio> + MediaSession（media-session.js），Android 锁屏可续播。
 */
(function () {
  'use strict';

  // 商品 ID -> 典故（title 供锁屏媒体卡片展示；文案手写预置，机翻典故必错）
  var STORIES = {
    'mask-fan': {
      title: '脸谱折扇典故',
      zh: '川剧脸谱以色识人：红色代表忠义，如三国名将关羽，红脸长髯，义薄云天；黑色代表耿直刚猛，如猛将张飞；包公的黑脸额缀月牙，铁面无私。一柄竹编脸谱扇在手，读懂巴蜀千年的忠义观。',
      en: 'In Sichuan Opera, mask colours speak: red stands for loyalty, like Guan Yu, the famed general of the Three Kingdoms; black means forthright valour, like Zhang Fei; Judge Bao\'s black face bears a moon, symbol of impartial justice. Hold this bamboo fan, and read a thousand years of Sichuan valour.',
    },
    'mask-pendant': {
      title: '火凤金枪挂件典故',
      zh: '朱红火凤浴火重生，是巴蜀人坚韧图腾；金枪则取自川剧武生枪牌绝技，靠旗翻飞、银枪如龙。大漆髹饰八道而成，一件挂件，藏着台上的一团火与一杆枪。',
      en: 'The crimson phoenix rises reborn from flame — the emblem of Sichuan resilience; the golden spear evokes the acrobatic spear-play of Sichuan Opera\'s warrior roles. Lacquered in eight coats by hand, this pendant carries the fire and the spear of the stage.',
    },
  };

  var currentAudio = null;
  var currentBtn = null;

  function storyText(id) {
    var story = STORIES[id];
    if (!story) return null;
    var lang = (localStorage.getItem('app_lang') || 'zh');
    return lang.indexOf('zh') === 0 ? story.zh : story.en;
  }

  function storyTitle(id) {
    var story = STORIES[id];
    return story ? story.title : '文创典故';
  }

  function resetButton() {
    if (currentBtn) {
      currentBtn.textContent = currentBtn.dataset.label || '🔊 听典故';
      currentBtn.disabled = false;
      currentBtn = null;
    }
  }

  function stop() {
    if (currentAudio) {
      if (window.MediaHelper) MediaHelper.clear(currentAudio);
      try { currentAudio.pause(); } catch (e) { /* ignore */ }
      currentAudio = null;
    }
    resetButton();
  }

  function toggle(btn, id) {
    if (currentBtn === btn) { stop(); return; } // 再点同按钮 = 停止
    stop(); // 播放互斥：同时只播一个典故
    var text = storyText(id);
    if (!text) return;
    currentBtn = btn;
    btn.dataset.label = btn.textContent;
    btn.textContent = '合成中…';
    btn.disabled = true;
    var lang = (localStorage.getItem('app_lang') || 'zh').indexOf('zh') === 0 ? 'zh-CN' : 'en';
    var qs = new URLSearchParams({ text: text, lang: lang });
    fetch('/api/tts/synthesize?' + qs)
      .then(function (r) { if (!r.ok) throw new Error('tts ' + r.status); return r.blob(); })
      .then(function (blob) {
        if (currentBtn !== btn) return; // 期间已被停止/切换
        var audio = new Audio(URL.createObjectURL(blob));
        currentAudio = audio;
        if (window.MediaHelper) MediaHelper.bind(audio, { title: storyTitle(id), album: '文创典故' });
        btn.textContent = '⏸ 停止';
        btn.disabled = false;
        audio.onended = stop;
        audio.onerror = stop;
        audio.play().catch(stop); // 浏览器拦截自动播放等：回到未播放态
      })
      .catch(function () { stop(); });
  }

  // 事件委托：所有 data-story 按钮统一接管（卡片增删无需改本模块）
  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('[data-story]');
    if (btn) { ev.stopPropagation(); toggle(btn, btn.dataset.story); }
  });

  // 语言切换时停止当前典故（文案按语言固定，避免播到一半换语种）
  window.addEventListener('app:langchange', stop);

  // 专用耳机断连时停止（音频本体由 ble-guard 兜底暂停，此处复位按钮状态）
  window.addEventListener('ble:disconnected', stop);

  window.StoryAudio = { stop: stop };
})();
