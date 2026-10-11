/* 剧场介绍模块：观众入场前在首页收听多语言剧场介绍。
 *
 * 高内聚：介绍卡片全部逻辑（文案加载、语言跟随、TTS 播放控制）收敛于此文件。
 * 低耦合：与页面其余逻辑仅通过 DOM id（intro-*）与 window 'app:langchange'
 *        事件通信；数据经 GET /api/live/intro，语音复用 /api/tts/synthesize。
 *
 * 语言跟随：首页右上角语言下拉切换时派发事件，本模块自动重载文案并停止旧音频。
 * 关屏播放：<audio> + MediaSession（media-session.js），Android 锁屏可续播。
 */
(function () {
  'use strict';

  const API = '/api';

  // 介绍语言显示名（与后端预置语言一致；未列出语言由后端回退英文）
  const LANG_LABELS = {
    zh: '中文', en: 'English', ja: '日本語', ko: '한국어',
    es: 'Español', fr: 'Français', de: 'Deutsch', ru: 'Русский',
  };

  // 模块自身 UI 标签多语言（按钮/状态文案），与页面语言保持一致
  const UI = {
    zh: { loading: '正在加载介绍…', fail: '介绍加载失败，请稍后刷新重试', synth: '语音合成中…', synthFail: '合成失败，请重试', play: '播放剧场介绍', stop: '停止播放' },
    en: { loading: 'Loading introduction…', fail: 'Failed to load intro, please refresh later', synth: 'Synthesizing voice…', synthFail: 'Synthesis failed, please retry', play: 'Play Theatre Intro', stop: 'Stop Playing' },
    ja: { loading: '紹介を読み込み中…', fail: '紹介の読み込みに失敗しました', synth: '音声合成中…', synthFail: '合成に失敗しました、再試行してください', play: '劇場紹介を再生', stop: '再生を停止' },
    ko: { loading: '소개를 불러오는 중…', fail: '소개 로드에 실패했습니다. 새로고침 후 다시 시도하세요', synth: '음성 합성 중…', synthFail: '합성에 실패했습니다. 다시 시도하세요', play: '극장 소개 재생', stop: '재생 중지' },
    es: { loading: 'Cargando introducción…', fail: 'Error al cargar la introducción, actualice más tarde', synth: 'Sintetizando voz…', synthFail: 'Fallo de síntesis, reintente', play: 'Reproducir introducción del teatro', stop: 'Detener reproducción' },
    fr: { loading: 'Chargement de la présentation…', fail: 'Échec du chargement, veuillez rafraîchir plus tard', synth: 'Synthèse vocale…', synthFail: 'Échec de la synthèse, veuillez réessayer', play: 'Écouter la présentation du théâtre', stop: 'Arrêter la lecture' },
    de: { loading: 'Einführung wird geladen…', fail: 'Laden der Einführung fehlgeschlagen, bitte später neu laden', synth: 'Sprachsynthese läuft…', synthFail: 'Synthese fehlgeschlagen, bitte erneut versuchen', play: 'Theater-Einführung abspielen', stop: 'Wiedergabe stoppen' },
    ru: { loading: 'Загрузка представления…', fail: 'Не удалось загрузить представление, обновите позже', synth: 'Синтез речи…', synthFail: 'Ошибка синтеза, повторите попытку', play: 'Слушать о театре', stop: 'Остановить воспроизведение' },
  };

  // UI 文案取词：跟随用户所选语言（state.uiLang），内容回退不影响界面语言
  function ui(key) {
    const d = UI[state.uiLang] || UI.zh;
    return d[key] || UI.zh[key] || key;
  }

  const state = {
    lang: 'zh',        // 当前介绍语言（后端确认后回写）
    uiLang: 'zh',      // 用户所选界面语言（UI 标签用）
    text: '',          // 当前语言介绍文案
    audio: null,       // 正在播放的 <audio>
    playing: false,
  };

  const els = {
    card: document.getElementById('section-theatre-intro'),
    textBox: document.getElementById('intro-text-box'),
    langBadge: document.getElementById('intro-lang-badge'),
    btn: document.getElementById('btn-theatre-intro-play'),
    playLabel: document.getElementById('intro-play-label'),
    playIcon: document.getElementById('intro-play-icon'),
  };

  if (!els.card || !els.textBox || !els.btn) return; // 页面无介绍卡片则不启用

  /* ── 文案加载 ─────────────────────────────── */
  async function loadIntro(lang) {
    state.uiLang = lang;
    // 非播放态下同步按钮文案到当前界面语言
    if (!state.playing) els.playLabel.textContent = ui('play');
    els.textBox.classList.add('intro-loading');
    els.textBox.textContent = ui('loading');
    try {
      const resp = await fetch(`${API}/live/intro?lang=${encodeURIComponent(lang)}`);
      const body = await resp.json();
      if (body.code !== 0 || !body.data) throw new Error(body.message || 'load failed');
      state.lang = body.data.lang; // 后端可能回退语言（如不支持时回退 en）
      state.text = body.data.text;
      els.textBox.classList.remove('intro-loading');
      els.textBox.textContent = state.text;
      els.langBadge.textContent = LANG_LABELS[state.lang] || state.lang.toUpperCase();
    } catch {
      els.textBox.classList.remove('intro-loading');
      els.textBox.textContent = ui('fail');
    }
  }

  /* ── 语音播放（复用后端 TTS） ─────────────── */
  function ttsUrl() {
    // 中文内容用 zh-CN 音色，其余语言码与 TTS 注册表一致
    const ttsLang = state.lang === 'zh' ? 'zh-CN' : state.lang;
    return `${API}/tts/synthesize?${new URLSearchParams({ text: state.text, lang: ttsLang })}`;
  }

  function stopIntro() {
    if (state.audio) {
      if (window.MediaHelper) MediaHelper.clear(state.audio);
      state.audio.onended = null;
      state.audio.onerror = null;
      state.audio.pause();
      state.audio.src = '';
      state.audio = null;
    }
    // 浏览器本地朗读兜底（speechSynthesis）也要随停止清理
    if (state.speech) {
      try { speechSynthesis.cancel(); } catch (e) { /* ignore */ }
      state.speech = null;
    }
    state.playing = false;
    setPlayingUI(false);
  }

  /* ── 演示兜底链：后端 TTS 不可用（503，豆包凭据未配置）时保证仍可出声 ──
   * 1) 预合成演示音频 assets/audio/intro_demo_{lang}.mp3（CosyVoice3 本地烘焙，中/英）
   * 2) 浏览器 speechSynthesis 朗读当前介绍文本（任意语言，随设备音质浮动）
   * 正式链路（豆包 TTS）恢复后自动优先，无需改动。 */
  function demoFiles() {
    if (state.lang === 'zh') return ['./assets/audio/intro_demo_zh.mp3?v=2'];
    const list = ['./assets/audio/intro_demo_en.mp3?v=2'];
    if (state.lang !== 'en') list.push('./assets/audio/intro_demo_zh.mp3?v=2'); // 其余语言回退英文，再回退中文
    return list;
  }

  function speakFallback() {
    if (!('speechSynthesis' in window)) {
      stopIntro();
      els.playLabel.textContent = ui('synthFail');
      return;
    }
    try {
      const u = new SpeechSynthesisUtterance(state.text);
      u.lang = state.lang === 'zh' ? 'zh-CN' : state.lang;
      u.rate = 0.95;
      u.onend = () => stopIntro();
      u.onerror = () => stopIntro();
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
      state.speech = u;
      state.playing = true;
      setPlayingUI(true);
    } catch (e) {
      stopIntro();
      els.playLabel.textContent = ui('synthFail');
    }
  }

  function playDemoFile(i) {
    const files = demoFiles();
    if (i >= files.length) { speakFallback(); return; }
    const audio = new Audio(files[i]);
    state.audio = audio;
    let advanced = false;
    const next = () => {
      if (advanced) return; // onerror 与 play().catch 只走一次
      advanced = true;
      playDemoFile(i + 1);
    };
    audio.onended = () => stopIntro();
    audio.onerror = next;
    audio.play().then(() => {
      if (window.MediaHelper) {
        MediaHelper.bind(audio, { title: '剧场介绍 · ' + (LANG_LABELS[state.lang] || state.lang), album: '四川省川剧院' });
      }
      state.playing = true;
      setPlayingUI(true);
      if (window.showToast && !state.demoToasted) {
        state.demoToasted = true;
        window.showToast('TTS 未配置，播放演示语音');
      }
    }).catch(next);
  }

  async function toggleIntroPlay() {
    if (state.playing) { stopIntro(); return; }
    if (!state.text) return;
    els.btn.disabled = true;
    els.playLabel.textContent = ui('synth');
    const audio = new Audio(ttsUrl());
    state.audio = audio;
    audio.onended = () => stopIntro();
    audio.onerror = () => {
      // 后端 TTS 不可用：转演示兜底（不清 state.playing 链路，保持按钮状态机一致）
      state.audio = null;
      playDemoFile(0);
    };
    try {
      await audio.play();
      if (window.MediaHelper) {
        MediaHelper.bind(audio, { title: '剧场介绍 · ' + (LANG_LABELS[state.lang] || state.lang), album: '四川省川剧院' });
      }
      state.playing = true;
      setPlayingUI(true);
    } catch {
      // 浏览器拦截自动播放等场景：尝试兜底而非直接哑掉
      state.audio = null;
      playDemoFile(0);
    } finally {
      els.btn.disabled = false;
    }
  }

  function setPlayingUI(playing) {
    els.playLabel.textContent = playing ? ui('stop') : ui('play');
    els.playIcon.setAttribute('data-lucide', playing ? 'square' : 'play');
    els.btn.classList.toggle('intro-playing', playing);
    if (window.lucide) lucide.createIcons();
  }

  els.btn.addEventListener('click', toggleIntroPlay);

  // 专用耳机断连时停止剧场介绍（音频本体由 ble-guard 兜底暂停，此处复位播放按钮）
  window.addEventListener('ble:disconnected', stopIntro);

  /* ── 语言跟随：全局语言切换事件驱动 ───────── */
  window.addEventListener('app:langchange', (ev) => {
    const lang = (ev.detail && ev.detail.lang) || 'zh';
    stopIntro(); // 切语言先停旧音频，避免中英混播
    loadIntro(lang);
  });

  // 初始语言与全局语言保持一致（localStorage 由 setLanguage 持久化）
  loadIntro(localStorage.getItem('app_lang') || 'zh');
})();
