/* 实时翻译会话双端逻辑：扫码直入 → WebRTC 对讲 + 双语字幕（报价单 #14）。
 *
 * 高内聚：会话接入、媒体协商、按住说话（PTT）、字幕渲染、重连全部收敛于此文件。
 * 低耦合：与后端仅通过 REST 契约（/api/rtc/token-info、/captions）与信令 WS 协议
 *        （schemas/rtc.py 定义）通信；页面侧仅依赖 #view-rtc 内 DOM id 与 app:langchange。
 *
 * 媒体流（与 rtc_gateway.py 对应）：
 *   上行：本端麦克风 → WebRTC Opus → 服务端 ASR（仅 PTT 按住期间喂入）
 *   下行：工作人员端经 WebRTC 音频轨收「游客语音的译文 TTS 播报」；
 *        游客端无下行音频轨，凭字幕阅读译文。
 * 信令：客户端发起 offer；服务端 answer + 服务器候选一次性下发；
 *      本端候选走 trickle（逐条上行）。
 */
(function () {
  'use strict';

  const API = '/api';
  const HEARTBEAT_MS = 25000;   // WS 保活心跳间隔
  const RECONNECT_MS = 3000;    // 断线重连间隔
  // 局内网部署默认走 host 候选；与后端 rtc_stun_urls 口径一致（留空即可互通）
  const ICE_SERVERS = [];

  /* ── 多语文案（zh/en 双语字典，其余语言回退英文） ── */
  const DICT = {
    zh: {
      title: '实时翻译会话', badge: { visitor: '游客', staff: '工作人员' },
      mine: '我', peer: '对方', start: '进入会话', startHint: '需要使用麦克风 · 请允许浏览器弹出的权限请求',
      ptt: '说', pttHint: '按住印章开始说话，松开即结束一句<br>对方说话时字幕自动出现在上方',
      peerWaiting: '对方尚未接入', peerOnline: '对方已在线', peerOffline: '对方暂时离开',
      stateIdle: '未连接', stateConnecting: '连接中', stateLive: '通话中', stateClosed: '已断开', stateEnded: '已结束',
      loading: '正在获取会话信息…', invalid: '会话不存在或二维码已失效，请联系工作人员重新扫码',
      full: '当前会话数已达上限，请稍后再试', ended: '会话已结束，感谢使用',
      micDenied: '麦克风权限被拒绝：请在浏览器设置中允许后重试',
      webrtcUnsupported: '当前浏览器不支持实时对讲（需 HTTPS 或新版本浏览器）',
      reconnecting: '连接中断，正在重连…', holdToTalk: '按住下方印章说话，翻译字幕实时滚动',
    },
    en: {
      title: 'Live Translation', badge: { visitor: 'Visitor', staff: 'Staff' },
      mine: 'Me', peer: 'Peer', start: 'Join Session', startHint: 'Microphone required · please allow the browser permission prompt',
      ptt: 'Talk', pttHint: 'Hold the seal button to speak, release to end a sentence<br>Peer speech appears above as captions',
      peerWaiting: 'Peer not joined yet', peerOnline: 'Peer online', peerOffline: 'Peer temporarily away',
      stateIdle: 'Offline', stateConnecting: 'Connecting', stateLive: 'Live', stateClosed: 'Disconnected', stateEnded: 'Ended',
      loading: 'Loading session…', invalid: 'Session not found or QR expired. Please scan again.',
      full: 'Session limit reached, please try again later', ended: 'Session ended, thanks for using',
      micDenied: 'Microphone permission denied: allow it in browser settings and retry',
      webrtcUnsupported: 'This browser does not support live talk (HTTPS or an up-to-date browser required)',
      reconnecting: 'Connection lost, reconnecting…', holdToTalk: 'Hold the seal below to talk; translations roll in real time',
    },
  };

  /* ── 运行时状态 ─────────────────────────────── */
  const state = {
    token: null,
    info: null,          // token-info 返回 {code,role,title,lang,session_status,peer_online}
    ended: false,        // 会话终结（session_end / 已结束），阻止重连
    joined: false,       // 已点「进入会话」
    ws: null,
    pc: null,
    localStream: null,
    pingTimer: null,
    pendingIce: [],      // answer 到达前缓存的本端候选
    peerJoined: false,
    captions: [],        // {seq,direction,text,translated,ts}
    lastSeq: 0,
    wakeLock: null,
  };

  /* ── DOM 快捷引用 ───────────────────────────── */
  const $ = (id) => document.getElementById(id);
  const els = {
    title: $('rt-title'), dot: $('rt-dot'), state: $('rt-state'), msg: $('rt-msg'),
    infoLoading: $('rt-info-loading'), infoBody: $('rt-info-body'),
    roleBadge: $('rt-role-badge'), code: $('rt-code'),
    langMine: $('rt-lang-mine'), langPeer: $('rt-lang-peer'), peerState: $('rt-peer-state'),
    streamCard: $('rt-stream-card'), stream: $('rt-stream'),
    pttCard: $('rt-ptt-card'), entry: $('rt-entry'), btnStart: $('rt-btn-start'),
    pttZone: $('rt-ptt-zone'), btnPtt: $('rt-btn-ptt'), pttHint: $('rt-ptt-hint'),
    remoteAudio: $('rt-remote-audio'),
  };

  /* ── 工具 ───────────────────────────────────── */
  function t(key) {
    // zh/en 双语字典：非中文语言统一回退英文；语言口径与全局一致（localStorage app_lang）
    const lang = (localStorage.getItem('app_lang') || 'zh') !== 'zh' ? 'en' : 'zh';
    return (DICT[lang] && DICT[lang][key]) || DICT.zh[key] || key;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function msg(text, kind) {
    els.msg.innerHTML = text ? `<div class="status-msg ${kind || ''}">${text}</div>` : '';
  }
  const LANG_NAMES = {
    'zh-CN': '中文', en: 'English', ja: '日本語', ko: '한국어', es: 'Español', fr: 'Français',
    de: 'Deutsch', ru: 'Русский', hi: 'हिन्दी', th: 'ไทย', vi: 'Tiếng Việt', id: 'Indonesia',
  };
  const langName = (code) => LANG_NAMES[code] || String(code || '').toUpperCase();
  function wsUrl(token) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${location.host}${API}/rtc/ws/${token}`;
  }
  function setState(text, dotClass) {
    els.state.textContent = text;
    els.dot.className = `dot ${dotClass || ''}`;
  }
  function amVisitor() { return state.info && state.info.role === 'visitor'; }

  /* ── 会话信息 ───────────────────────────────── */
  async function loadTokenInfo() {
    try {
      const resp = await fetch(`${API}/rtc/token-info?token=${encodeURIComponent(state.token)}`);
      if (resp.status === 404) { renderFatal(t('invalid')); return false; }
      const body = await resp.json();
      state.info = body.data;
      renderInfo();
      if (state.info.session_status === 'ended') { renderFatal(t('ended')); return false; }
      return true;
    } catch {
      msg(t('invalid'), 'err');
      return false;
    }
  }

  function renderInfo() {
    const info = state.info;
    els.title.textContent = info.title || t('title');
    els.infoLoading.classList.add('hidden');
    els.infoBody.classList.remove('hidden');
    els.roleBadge.textContent = t('badge')[info.role] || info.role;
    els.roleBadge.className = `rt-badge ${info.role}`;
    els.code.textContent = `#${info.code}`;
    els.langMine.textContent = langName(info.lang);
    els.langPeer.textContent = amVisitor() ? langName(info.staff_lang) : langName(info.visitor_lang);
    renderPeer();
  }

  function renderPeer() {
    if (!state.info) return;
    els.peerState.innerHTML = state.peerJoined
      ? `<b>${escapeHtml(t('peerOnline'))}</b>`
      : escapeHtml(t('peerWaiting'));
  }

  function renderFatal(text) {
    setState(t('stateEnded'), 'err');
    msg(text, 'err');
    els.entry.classList.add('hidden');
    els.pttZone.classList.add('hidden');
  }

  /* ── 进入会话（用户手势内申请麦克风并建连） ── */
  async function join() {
    if (state.joined || state.ended) return;
    if (!navigator.mediaDevices || !window.RTCPeerConnection) {
      msg(t('webrtcUnsupported'), 'err');
      return;
    }
    els.btnStart.disabled = true;
    try {
      state.localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      els.btnStart.disabled = false;
      msg(err && err.name === 'NotAllowedError' ? t('micDenied') : t('webrtcUnsupported'), 'err');
      return;
    }
    state.joined = true;
    els.entry.classList.add('hidden');
    els.pttZone.classList.remove('hidden');
    els.streamCard.style.display = '';
    els.pttHint.innerHTML = t('pttHint');
    requestWakeLock();
    connectWs();
  }

  /* ── 信令 WebSocket 与 WebRTC 协商 ──────────── */
  function connectWs() {
    closeWs();
    const ws = new WebSocket(wsUrl(state.token));
    state.ws = ws;
    setState(t('stateConnecting'), '');
    ws.onopen = () => {
      if (state.ended) return;
      setState(t('stateConnecting'), '');
      state.pingTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}');
      }, HEARTBEAT_MS);
      createPeer();           // 每次连接重新协商（服务端按同 token 顶替旧 peer）
      catchUpCaptions();
    };
    ws.onclose = () => {
      clearInterval(state.pingTimer);
      if (state.ended) return;
      setState(t('stateClosed'), 'err');
      teardownPeer();
      msg(t('reconnecting'), 'warn');
      setTimeout(() => { if (!state.ended && state.joined) connectWs(); }, RECONNECT_MS);
    };
    ws.onerror = () => { setState(t('stateClosed'), 'err'); };
    ws.onmessage = (ev) => handleSignal(JSON.parse(ev.data));
  }

  function closeWs() {
    clearInterval(state.pingTimer);
    if (state.ws) { try { state.ws.close(); } catch { /* ignore */ } state.ws = null; }
  }

  function createPeer() {
    teardownPeer();
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    state.pc = pc;
    state.localStream.getTracks().forEach((track) => pc.addTrack(track, state.localStream));

    pc.onicecandidate = (ev) => {
      if (ev.candidate && state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'ice', candidate: ev.candidate.toJSON() }));
      }
    };
    pc.ontrack = (ev) => {
      // 仅工作人员端有下行轨（游客语音的译文 TTS 播报）；自动经 <audio> 播放
      if (ev.streams && ev.streams[0]) els.remoteAudio.srcObject = ev.streams[0];
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'connected') {
        setState(t('stateLive'), 'live');
        els.btnPtt.disabled = false;   // 连接就绪，允许按住说话
        msg('', '');
      } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
        setState(t('stateClosed'), 'err');
        els.btnPtt.disabled = true;
        msg(t('reconnecting'), 'warn');
      }
    };

    // 客户端发起 offer（aiortc 应答后服务器候选随 answer 一次性下发）
    pc.createOffer({ offerToReceiveAudio: true }).then(async (offer) => {
      await pc.setLocalDescription(offer);
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'offer', sdp: pc.localDescription.sdp }));
      }
    });
  }

  function teardownPeer() {
    if (state.pc) { try { state.pc.close(); } catch { /* ignore */ } state.pc = null; }
    state.pendingIce = [];
    els.btnPtt.disabled = true;
  }

  function handleSignal(data) {
    if (data.type === 'answer' && state.pc) {
      state.pc.setRemoteDescription({ type: 'answer', sdp: data.sdp })
        .then(flushPendingIce)
        .catch(() => { /* 协商失败走 onclose 重连 */ });
    } else if (data.type === 'ice' && data.candidate) {
      if (state.pc && state.pc.remoteDescription) {
        state.pc.addIceCandidate(data.candidate).catch(() => { /* 单条候选失败可忽略 */ });
      } else {
        state.pendingIce.push(data.candidate); // answer 未到先缓存
      }
    } else if (data.type === 'caption') {
      appendCaption(data);
    } else if (data.type === 'peer_state') {
      state.peerJoined = data.state === 'joined';
      renderPeer();
    } else if (data.type === 'session_end') {
      state.ended = true;
      shutdown();
      setState(t('stateEnded'), 'err');
      const card = document.createElement('div');
      card.className = 'end-card';
      card.innerHTML = `<div class="end-title">🎭 ${escapeHtml(t('ended'))}</div>`;
      els.stream.appendChild(card);
    }
  }

  function flushPendingIce() {
    const list = state.pendingIce.splice(0);
    list.forEach((c) => { if (state.pc) state.pc.addIceCandidate(c).catch(() => {}); });
  }

  /* ── 按住说话（PTT）────────────────────────── */
  function ptt(on) {
    els.btnPtt.classList.toggle('holding', on);
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ type: 'ptt', on }));
    }
  }
  function bindPtt() {
    const btn = els.btnPtt;
    const down = (ev) => {
      ev.preventDefault();
      if (btn.disabled || state.pc === null) return;
      ptt(true);
    };
    const up = (ev) => {
      ev.preventDefault();
      ptt(false);
    };
    btn.addEventListener('pointerdown', down);
    btn.addEventListener('pointerup', up);
    btn.addEventListener('pointercancel', up);
    btn.addEventListener('pointerleave', up);
    // 阻止长按弹菜单 / 双击缩放
    btn.addEventListener('contextmenu', (ev) => ev.preventDefault());
  }

  /* ── 字幕：断线补拉 + 实时渲染 ──────────────── */
  async function catchUpCaptions() {
    try {
      const resp = await fetch(`${API}/rtc/captions/${encodeURIComponent(state.token)}?after=0`);
      const body = await resp.json();
      (body.data || []).forEach((cap) => {
        if (cap.seq > state.lastSeq) { state.lastSeq = cap.seq; state.captions.push(cap); appendCapNode(cap, false); }
      });
      scrollToLatest();
    } catch { /* 补拉失败不影响实时流 */ }
  }

  function appendCaption(cap) {
    if (cap.seq <= state.lastSeq) return; // 去重（补拉与实时可能重叠）
    state.lastSeq = cap.seq;
    state.captions.push(cap);
    appendCapNode(cap, true);
    scrollToLatest();
  }

  function appendCapNode(cap, latest) {
    const empty = els.stream.querySelector('.rt-empty');
    if (empty) empty.remove();
    const prev = els.stream.querySelector('.cap-item.latest');
    if (prev) prev.classList.remove('latest');
    const mine = amVisitor()
      ? cap.direction === 'visitor->staff'
      : cap.direction === 'staff->visitor';
    const item = document.createElement('div');
    item.className = `cap-item ${mine ? 'mine' : 'theirs'}${latest ? ' latest' : ''}`;
    const time = new Date((cap.ts || 0) * 1000).toLocaleTimeString('zh-CN', { hour12: false });
    item.innerHTML = `
      <div class="meta"><span class="who">${mine ? escapeHtml(t('mine')) : escapeHtml(t('peer'))}</span><span>#${cap.seq} · ${time}</span></div>
      <div class="src">${escapeHtml(cap.text)}</div>
      <div class="tr">${escapeHtml(cap.translated || '')}</div>`;
    els.stream.appendChild(item);
    while (els.stream.children.length > 200) els.stream.removeChild(els.stream.firstChild);
  }

  function scrollToLatest() {
    requestAnimationFrame(() => { els.stream.scrollTop = els.stream.scrollHeight; });
  }

  /* ── 屏幕常亮：对讲场景保持屏幕不熄灭 ───────── */
  async function requestWakeLock() {
    if (!('wakeLock' in navigator) || state.wakeLock) return;
    try {
      state.wakeLock = await navigator.wakeLock.request('screen');
      state.wakeLock.addEventListener('release', () => { state.wakeLock = null; });
    } catch { /* 拒绝/不支持：静默降级 */ }
  }
  function releaseWakeLock() {
    if (state.wakeLock) { try { state.wakeLock.release(); } catch { /* ignore */ } state.wakeLock = null; }
  }

  /* ── 退出与清理 ─────────────────────────────── */
  function shutdown() {
    closeWs();
    teardownPeer();
    releaseWakeLock();
    if (state.localStream) {
      state.localStream.getTracks().forEach((track) => track.stop());
      state.localStream = null;
    }
    els.remoteAudio.srcObject = null;
  }

  /* ── 语言切换联动 ───────────────────────────── */
  window.addEventListener('app:langchange', () => {
    if (!state.info) return;
    renderInfo();
    if (state.joined) {
      els.pttHint.innerHTML = t('pttHint');
      els.btnPtt.textContent = t('ptt');
    } else if (!state.ended) {
      els.btnStart.textContent = t('start');
    }
  });

  /* ── 初始化：?view=rtc&token=X（&role=staff 仅用于服务端角色，token 即身份） ── */
  (async function init() {
    state.token = new URLSearchParams(location.search).get('token');
    if (!state.token) { renderFatal(t('invalid')); return; }
    bindPtt();
    els.btnStart.onclick = join;
    await loadTokenInfo();
  })();
})();
