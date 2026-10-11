/**
 * agent-companion.js —— Agent 伴游问答前端（报价单 #12-14）
 *
 * 高内聚：会话生命周期（创建/复用/重建）、文本与语音提问、历史回放、
 *         引用与降级态渲染、回答 TTS 播报，全部收敛在本模块。
 * 低耦合：与页面仅通过 #ag-* DOM 与 'app:langchange' 事件交互；
 *         语言口径与全局一致（localStorage app_lang），zh/en 双语字典、
 *         其余语言回退英文；后端契约见 backend/app/schemas/agent.py。
 *
 * 依赖：index.html 内 #section-agent-companion 入口与 #ag-panel 弹层标记。
 */
(function () {
  'use strict';

  const API = '/api';
  const TOKEN_KEY = 'ag_token';

  /* ── 多语文案（zh/en 双语字典，其余语言回退英文） ── */
  const DICT = {
    zh: {
      title: '智能伴游', sub: '川剧知识 · 观演服务',
      empty: '问点什么，伴游随身答', close: '关闭',
      placeholder: '输入您的问题…', send: '发送', mic: '语音提问',
      listening: '听录中…点此结束', thinking: '伴游正在翻资料…',
      heardPrefix: '🎤 您问的是：',
      sources: '依据', say: '播报', playing: '播报中…',
      degraded: '智能问答暂时不可用，已为您转人工引导：请前往一层服务台咨询工作人员。',
      netErr: '网络不给力，请稍后再试',
      emptyReply: '这个问题我还没学过，换个问法试试？',
      micErr: '无法启动麦克风：请检查浏览器权限与 HTTPS 环境',
      tooShort: '说话时间太短，请按一下话筒后正常提问',
    },
    en: {
      title: 'AI Companion', sub: 'Opera lore · Venue services',
      empty: 'Ask anything, the companion answers', close: 'Close',
      placeholder: 'Type your question…', send: 'Send', mic: 'Voice question',
      listening: 'Recording… tap to stop', thinking: 'Looking it up…',
      heardPrefix: '🎤 You asked: ',
      sources: 'Sources', say: 'Play', playing: 'Playing…',
      degraded: 'AI Q&A is temporarily unavailable — please ask our staff at the ground-floor service desk.',
      netErr: 'Network hiccup, please try again',
      emptyReply: 'I have not learned that one yet — try rephrasing?',
      micErr: 'Microphone unavailable: check browser permission and HTTPS',
      tooShort: 'Too short — tap the mic and ask naturally',
    },
  };

  /* 快捷问题（点击即提问） */
  const CHIPS = {
    zh: ['变脸是怎么变的？', '今晚上演什么剧目？', '洗手间在哪里？'],
    en: ['How does face-changing work?', "What's on tonight?", 'Where is the restroom?'],
  };

  /* ── 运行时状态 ── */
  const state = {
    token: localStorage.getItem(TOKEN_KEY) || '',
    recording: false,
    recorder: null,
    recChunks: [],
    busy: false,          // 有一次问答在途（防并发提问）
    audio: null,          // 回答播报 <audio> 复用
  };

  /* ── DOM ── */
  const $ = (id) => document.getElementById(id);
  const els = {
    mask: $('ag-mask'), panel: $('ag-panel'), close: $('ag-close'),
    title: $('ag-title'), sub: $('ag-sub'),
    stream: $('ag-stream'), empty: $('ag-empty'), emptyText: $('ag-empty-text'),
    chips: $('ag-chips'), input: $('ag-input'),
    send: $('ag-send'), mic: $('ag-mic'), openBtn: $('btn-agent-open'),
  };

  /* ── 工具 ── */
  function t(key) {
    const lang = (localStorage.getItem('app_lang') || 'zh') !== 'zh' ? 'en' : 'zh';
    return (DICT[lang] && DICT[lang][key]) || DICT.zh[key] || key;
  }
  function chipsLang() { return (localStorage.getItem('app_lang') || 'zh') !== 'zh' ? 'en' : 'zh'; }
  function sessionLang() {
    const lang = localStorage.getItem('app_lang') || 'zh';
    return lang === 'zh' ? 'zh-CN' : lang; // 后端语言码口径：中文为 zh-CN
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  /** 回答文本里的 [n] 引用标记渲染为上标角标 */
  function renderAnswer(text) {
    return escapeHtml(text).replace(/\[(\d+)\]/g, '<sup class="ag-cite">[$1]</sup>');
  }
  function scrollBottom() { els.stream.scrollTop = els.stream.scrollHeight; }
  function nodeCode() { return new URLSearchParams(location.search).get('node') || ''; }

  /* ── 会话：创建 / 复用 / 失效重建 ── */
  async function ensureSession() {
    if (state.token) return state.token;
    const resp = await fetch(`${API}/agent/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lang: sessionLang(), node_code: nodeCode() }),
    });
    if (!resp.ok) throw new Error('session');
    const body = await resp.json();
    state.token = body.data.token;
    localStorage.setItem(TOKEN_KEY, state.token);
    return state.token;
  }

  /** 会话失效（404）时清空令牌重建并重试一次 */
  async function withSession(fn) {
    await ensureSession();
    try {
      return await fn(state.token);
    } catch (err) {
      if (err && err.status === 404) {
        localStorage.removeItem(TOKEN_KEY);
        state.token = '';
        await ensureSession();
        return await fn(state.token);
      }
      throw err;
    }
  }

  async function apiJson(resp) {
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const e = new Error(body.detail || 'http');
      e.status = resp.status;
      e.detail = body.detail || '';
      throw e;
    }
    return body.data;
  }

  /* ── 渲染 ── */
  function hideEmpty() { if (els.empty) els.empty.style.display = 'none'; }

  function bubbleRow(role) {
    const row = document.createElement('div');
    row.className = `ag-row ${role}`;
    const avatar = document.createElement('div');
    avatar.className = 'ag-avatar';
    avatar.textContent = role === 'agent' ? '川' : '我';
    const bubble = document.createElement('div');
    bubble.className = 'ag-bubble';
    row.appendChild(avatar);
    row.appendChild(bubble);
    els.stream.appendChild(row);
    scrollBottom();
    return bubble;
  }

  function appendUser(text) {
    hideEmpty();
    bubbleRow('user').textContent = text;
  }

  function appendAgent(reply) {
    hideEmpty();
    const bubble = bubbleRow('agent');
    bubble.innerHTML = reply.text ? renderAnswer(reply.text) : t('emptyReply');
    if (reply.degraded) {
      const tip = document.createElement('div');
      tip.className = 'ag-degraded';
      tip.textContent = t('degraded');
      bubble.appendChild(tip);
    }
    const srcs = (reply.sources || []).filter((s) => s && s.title);
    if (srcs.length) {
      const wrap = document.createElement('div');
      wrap.className = 'ag-srcs';
      srcs.forEach((s) => {
        const chip = document.createElement('span');
        chip.className = 'ag-src';
        chip.textContent = `[${s.n}] ${s.title}`;
        wrap.appendChild(chip);
      });
      bubble.appendChild(wrap);
    }
    // 回答播报：未降级且有文本时提供 TTS 按钮（豆包整段合成）
    if (reply.text && !reply.degraded) {
      const tools = document.createElement('div');
      tools.className = 'ag-tools';
      const say = document.createElement('button');
      say.className = 'ag-say';
      say.textContent = t('say');
      say.onclick = () => speak(reply.text, say);
      tools.appendChild(say);
      bubble.appendChild(tools);
    }
    scrollBottom();
    return bubble;
  }

  function appendThinking() {
    const bubble = bubbleRow('agent');
    bubble.textContent = t('thinking');
    bubble.classList.add('ag-wait');
    return bubble;
  }

  function showError(text) {
    hideEmpty();
    const bubble = bubbleRow('agent');
    bubble.textContent = text;
    bubble.style.opacity = '.75';
  }

  /* ── 回答播报（复用 /api/tts/synthesize 整段 MP3） ── */
  function speak(text, btn) {
    if (state.audio) { state.audio.pause(); state.audio = null; }
    document.querySelectorAll('.ag-say.playing').forEach((b) => { b.classList.remove('playing'); b.textContent = t('say'); });
    const url = `${API}/tts/synthesize?text=${encodeURIComponent(text.slice(0, 300))}&lang=${encodeURIComponent(sessionLang())}`;
    const audio = new Audio(url);
    state.audio = audio;
    btn.classList.add('playing');
    btn.textContent = t('playing');
    audio.onended = audio.onerror = () => {
      btn.classList.remove('playing');
      btn.textContent = t('say');
      state.audio = null;
    };
    audio.play().catch(() => {
      btn.classList.remove('playing');
      btn.textContent = t('say');
    });
  }

  /* ── 问答 ── */
  async function ask(text) {
    const q = String(text || '').trim();
    if (!q || state.busy) return;
    state.busy = true;
    els.send.disabled = true;
    els.input.value = '';
    appendUser(q);
    const waiting = appendThinking();
    try {
      const reply = await withSession(async (token) =>
        apiJson(await fetch(`${API}/agent/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, text: q }),
        })));
      waiting.remove();
      appendAgent(reply);
    } catch (err) {
      waiting.remove();
      showError(err && err.detail ? String(err.detail) : t('netErr'));
    } finally {
      state.busy = false;
      els.send.disabled = false;
      els.input.focus();
    }
  }

  /* ── 历史回放（重开面板 / 换机回连时恢复对话） ── */
  async function loadHistory() {
    if (!state.token) return;
    try {
      const rows = await withSession(async (token) =>
        apiJson(await fetch(`${API}/agent/history?token=${encodeURIComponent(token)}&limit=50`)));
      if (!rows || !rows.length) return;
      hideEmpty();
      rows.forEach((m) => {
        if (m.role === 'user') appendUser(m.content);
        else appendAgent({ text: m.content, sources: m.sources, degraded: m.degraded });
      });
    } catch { /* 历史拉取失败不打断新提问 */ }
  }

  /* ── 语音提问：录音 → /api/agent/voice（服务端豆包 ASR 转写 + 作答） ── */
  async function toggleRecord() {
    if (state.recording) { state.recorder && state.recorder.stop(); return; }
    if (state.busy) return;
    if (!navigator.mediaDevices || !window.MediaRecorder) { showError(t('micErr')); return; }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      showError(t('micErr'));
      return;
    }
    state.recChunks = [];
    state.recorder = new MediaRecorder(stream);
    state.recorder.ondataavailable = (e) => { if (e.data && e.data.size) state.recChunks.push(e.data); };
    state.recorder.onstop = () => {
      stream.getTracks().forEach((tk) => tk.stop());
      state.recording = false;
      els.mic.classList.remove('rec');
      els.mic.title = t('mic');
      submitRecording();
    };
    state.recorder.start();
    state.recording = true;
    els.mic.classList.add('rec');
    els.mic.title = t('listening');
  }

  async function submitRecording() {
    const blob = new Blob(state.recChunks, { type: state.recChunks[0] ? state.recChunks[0].type : 'audio/webm' });
    if (!blob.size) { showError(t('tooShort')); return; }
    state.busy = true;
    els.send.disabled = true;
    const waiting = appendThinking();
    try {
      const reply = await withSession(async (token) => {
        const form = new FormData();
        form.append('audio', blob, 'question.webm');
        return apiJson(await fetch(`${API}/agent/voice?token=${encodeURIComponent(token)}`, { method: 'POST', body: form }));
      });
      waiting.remove();
      appendUser(`${t('heardPrefix')}${reply.heard}`);
      appendAgent(reply);
    } catch (err) {
      waiting.remove();
      if (err && err.detail) showError(String(err.detail));
      else if (err && err.status === 413) showError(t('tooShort'));
      else showError(t('netErr'));
    } finally {
      state.busy = false;
      els.send.disabled = false;
    }
  }

  /* ── 弹层开关 ── */
  function open() {
    els.mask.classList.add('open');
    els.panel.classList.add('open');
    renderChips();
    loadHistory();
    setTimeout(() => els.input && els.input.focus(), 380);
  }
  function close() {
    els.mask.classList.remove('open');
    els.panel.classList.remove('open');
    if (state.audio) { state.audio.pause(); state.audio = null; }
  }

  /* ── 文案装配 ── */
  function applyLang() {
    els.title.textContent = t('title');
    els.sub.textContent = t('sub');
    els.emptyText.textContent = t('empty');
    els.close.title = t('close');
    els.close.setAttribute('aria-label', t('close'));
    els.input.placeholder = t('placeholder');
    els.send.title = t('send');
    els.mic.title = t('mic');
    els.panel.setAttribute('aria-label', t('title'));
    renderChips();
  }
  function renderChips() {
    els.chips.innerHTML = '';
    CHIPS[chipsLang()].forEach((q) => {
      const chip = document.createElement('button');
      chip.className = 'ag-chip';
      chip.type = 'button';
      chip.textContent = q;
      chip.onclick = () => ask(q);
      els.chips.appendChild(chip);
    });
  }

  /* ── 初始化 ── */
  (function init() {
    if (!els.panel) return;
    applyLang();
    els.openBtn.addEventListener('click', open);
    els.close.addEventListener('click', close);
    els.mask.addEventListener('click', close);
    els.send.addEventListener('click', () => ask(els.input.value));
    els.input.addEventListener('keydown', (e) => { if (e.key === 'Enter') ask(els.input.value); });
    els.mic.addEventListener('click', toggleRecord);
    window.addEventListener('app:langchange', applyLang);
    window.AgentCompanion = { open, close };
  })();
})();
