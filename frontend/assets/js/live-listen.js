/* 场次直播收听席逻辑：选场次 → WS 订阅 → 原声播放 + 双语字幕 + 可选译文播报。
 *
 * 高内聚：观众端全部交互（场次发现、订阅、音频播放、字幕渲染、播报）收敛于此文件。
 * 低耦合：与后端仅通过 REST 契约与 WS 消息协议（schemas/live.py 定义）通信。
 *
 * 数据流：
 *   文本帧 caption/listeners/session_end → 字幕流渲染 / 人数 / 收播提示
 *   二进制帧 PCM16/16k/mono             → AudioContext 排队播放（现场原声）
 *   可选：新字幕译文 → /api/tts/synthesize 合成播报（复用导览 TTS）
 */
(function () {
  'use strict';

  const API = '/api';
  const SAMPLE_RATE = 16000;    // 后端原声转发采样率
  const HEARTBEAT_MS = 25000;   // WS 保活心跳间隔

  /* ── 运行时状态 ─────────────────────────────── */
  const state = {
    show: null,            // 当前收听的场次 {id,title,host_name,target_langs,session_code}
    ws: null,
    pingTimer: null,
    displayLang: null,     // 'zh'=仅原文；其余为语言码（原文+译文对照）
    captions: [],
    ended: false,
    stick: true,           // 字幕粘底跟随（用户上滑回看时置 false，显示"最新字幕"按钮）
    applaudLast: 0,        // 本端叫好发送节流
    applaudTotal: 0,       // 本场全场叫好累计（收播写入记忆卡/收播卡）
    seenTerms: [],         // 本场看过的绝技/关键词（散场推相关文创）
    lastSeq: 0,            // 字幕最大 seq（去重用）
    // 原声播放
    audioCtx: null,
    playHeadAt: 0,         // 已排队音频的结束时间（AudioContext 时基）
    audioOn: true,
    // 译文播报
    ttsOn: false,
    ttsLang: 'en',
    ttsPlaying: false,
    // 屏幕常亮
    wakeLock: null,
    // 关屏降级播放：页面隐藏（关屏/切后台）后 AudioContext 必停，
    // 降级为 <audio> 排队播放预合成 TTS 译文（Android 后台可续播）
    bgMode: false,
    bgAudio: null,     // 复用同一个 <audio>，保持后台播放连续性
    bgQueue: [],       // 待播字幕 [{seq, text, lang}]
    bgBusy: false,
    // 候场节目（无直播时的随便听听）
    fillerAudio: null, // 复用一个 <audio>，避免多路播放叠加
    fillerId: '',      // 正在播放的节目 id
  };

  /* ── DOM 快捷引用 ───────────────────────────── */
  const $ = (id) => document.getElementById(id);
  const els = {
    dotWs: $('dot-ws'), wsState: $('ws-state'),
    viewLobby: $('view-lobby'), viewListen: $('view-listen'),
    liveList: $('live-list'), lobbyRefresh: $('lobby-refresh'),
    lsTitle: $('ls-title'), lsSub: $('ls-sub'), lsCount: $('ls-count'),
    langChips: $('lang-chips'),
    stream: $('stream'), capCount: $('cap-count'), listenMsg: $('listen-msg'),
    applaud: $('btn-applaud'), applaudCount: $('applaud-count'), latestBtn: $('btn-latest'),
    btnAudio: $('btn-audio'), btnTts: $('btn-tts'), btnExit: $('btn-exit'),
  };

  /* ── 工具 ───────────────────────────────────── */
  function msg(box, text, kind) {
    box.innerHTML = text ? `<div class="status-msg ${kind || ''}">${text}</div>` : '';
  }
  function wsUrl(code, audio) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${location.host}${API}/live/ws/${code}?audio=${audio ? 1 : 0}`;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  const LANG_LABELS = {
    en: 'English', ja: '日本語', ko: '한국어', es: 'Español', fr: 'Français',
    de: 'Deutsch', ru: 'Русский', hi: 'हिन्दी', ar: 'العربية', pt: 'Português',
    it: 'Italiano', th: 'ไทย', vi: 'Tiếng Việt', id: 'Indonesia', ms: 'Melayu',
    tr: 'Türkçe', pl: 'Polski', nl: 'Nederlands', uk: 'Українська',
    ur: 'اردو', bn: 'বাংলা', fa: 'فارسی', sw: 'Kiswahili',
  };
  const langLabel = (code) => LANG_LABELS[code] || code.toUpperCase();

  function ttsUrl(text, lang) {
    // 中文内容用 zh-CN 音色，其余语言码与 TTS 注册表一致
    const ttsLang = lang === 'zh' ? 'zh-CN' : lang;
    const qs = new URLSearchParams({ text, lang: ttsLang });
    return `${API}/tts/synthesize?${qs}`;
  }

  /* ── 收听席双语（zh/en；其余语言回退英文） ── */
  const LL = {
    zh: {
      ws_init: '未连接', ws_listening: '收听中', ws_ended: '已结束',
      ws_disconnected: '已断开', ws_conn_fail: '连接失败', ws_conn_err: '连接错误',
      count_suffix: ' 条', code_suffix: ' · 会场码 ',
      lobby_conn_fail: '无法连接服务，请稍后刷新',
      no_live1: '当前没有正在直播的场次', no_live2: '请按场次排期稍后再来',
      recv1: '正在接收现场收音…', recv2: '字幕将在此实时滚动',
      audio_on: '原声：开', audio_off: '原声：关', tts_off: '译文播报：关', tts_broadcast: '播报：',
      msg_ended_short: '本场直播已结束',
      msg_disc_refresh: '连接已断开，请刷新页面重试',
      msg_reconnect: '连接中断，正在重连…（{n}）',
      msg_bt_off: '耳机已断开，播放已暂停；重连后自动恢复',
      msg_ended: '本场「{t}」直播已结束，感谢收听',
      end_title: '今晚的戏已散场，精彩可以带走',
      end_stats: '📣 全场叫好 {a} 次 · 字幕陪你听懂 {c} 句',
      end_memory: '🖼 生成今晚的观剧记忆卡 →',
      end_photo: '留住今晚 · AI 川剧旅拍与一键换装 →',
    },
    ja: {
      ws_init: '未接続', ws_listening: '視聴中', ws_ended: '終了',
      ws_disconnected: '切断', ws_conn_fail: '接続失敗', ws_conn_err: '接続エラー',
      count_suffix: '件', code_suffix: ' · 会場コード ',
      lobby_conn_fail: 'サーバーに接続できません。後ほど更新してください。',
      no_live1: 'ただいま配信中のセッションはありません', no_live2: '公演スケジュールをご確認のうえ、またお越しください',
      recv1: '現場音声を受信中…', recv2: '字幕がここにリアルタイム表示されます',
      audio_on: '原音：オン', audio_off: '原音：オフ', tts_off: '訳読み上げ：オフ', tts_broadcast: '読み上げ：',
      msg_ended_short: 'このライブは終了しました',
      msg_disc_refresh: '接続が切断されました。ページを更新してください。',
      msg_reconnect: '接続が中断しました。再接続中…（{n}）',
      msg_bt_off: 'ヘッドセットが切断されました。再生を一時停止中。再接続で自動復帰します。',
      msg_ended: '「{t}」のライブは終了しました。ご視聴ありがとうございました。',
      end_title: '今夜の公演は幕を閉じました。感動をそのままに',
      end_stats: '📣 全場の喝彩 {a} 回 · 字幕で聴き取った {c} 言',
      end_memory: '🖼 今夜の観劇メモリーカードを作成 →',
      end_photo: '今夜を残す · AI川劇フォト & 衣装チェンジ →',
    },
    ko: {
      ws_init: '연결 안 됨', ws_listening: '청취 중', ws_ended: '종료',
      ws_disconnected: '연결 끊김', ws_conn_fail: '연결 실패', ws_conn_err: '연결 오류',
      count_suffix: '건', code_suffix: ' · 세션 코드 ',
      lobby_conn_fail: '서버에 연결할 수 없습니다. 잠시 후 새로고침해 주세요.',
      no_live1: '현재 진행 중인 라이브 세션이 없습니다', no_live2: '공연 일정을 확인하고 다시 방문해 주세요',
      recv1: '현장 음성을 수신 중…', recv2: '자막이 여기에 실시간 표시됩니다',
      audio_on: '원음: 켬', audio_off: '원음: 끔', tts_off: '번역 음성: 끔', tts_broadcast: '읽어주기:',
      msg_ended_short: '이 라이브 공연이 종료되었습니다',
      msg_disc_refresh: '연결이 끊겼습니다. 페이지를 새로고침해 주세요.',
      msg_reconnect: '연결이 끊겨 재연결 중… ({n})',
      msg_bt_off: '헤드셋 연결이 끊겨 재생이 일시 중지되었습니다. 재연결 시 자동으로 복구됩니다.',
      msg_ended: '"{t}" 라이브가 종료되었습니다. 청취해 주셔서 감사합니다.',
      end_title: '오늘 밤 공연이 막을 내렸습니다. 감동을 가져가세요',
      end_stats: '📣 전체 환호 {a}회 · 자막으로 이해한 {c}마디',
      end_memory: '🖼 오늘 밤의 관극 메모리 카드 만들기 →',
      end_photo: '오늘 밤을 간직 · AI川극 포토 & 원클릭 의상 →',
    },
    fr: {
      ws_init: 'Non connecté', ws_listening: 'Écoute', ws_ended: 'Terminé',
      ws_disconnected: 'Déconnecté', ws_conn_fail: 'Échec de connexion', ws_conn_err: 'Erreur de connexion',
      count_suffix: ' ', code_suffix: " · Code d'accès ",
      lobby_conn_fail: 'Serveur injoignable. Actualisez plus tard.',
      no_live1: 'Aucune session en direct pour le moment', no_live2: 'Consultez le programme et revenez plus tard',
      recv1: 'Réception du son en direct…', recv2: 'Les sous-titres défilent ici en temps réel',
      audio_on: 'Original : activé', audio_off: 'Original : désactivé', tts_off: 'Voix de traduction : désactivée', tts_broadcast: 'Lecture :',
      msg_ended_short: 'Ce direct est terminé',
      msg_disc_refresh: 'Déconnecté. Actualisez la page.',
      msg_reconnect: 'Connexion perdue, reconnexion… ({n})',
      msg_bt_off: 'Casque déconnecté. Lecture en pause ; reprise automatique à la reconnexion.',
      msg_ended: 'Le direct « {t} » est terminé. Merci de votre écoute.',
      end_title: 'Le spectacle de ce soir est terminé — emportez la magie',
      end_stats: '📣 {a} acclamations du public · {c} répliques éclaircies par les sous-titres',
      end_memory: '🖼 Créer la carte souvenir de ce soir →',
      end_photo: 'Gardez ce soir · Photoshoot opéra IA & costumes en un clic →',
    },
    de: {
      ws_init: 'Nicht verbunden', ws_listening: 'Hören', ws_ended: 'Beendet',
      ws_disconnected: 'Getrennt', ws_conn_fail: 'Verbindung fehlgeschlagen', ws_conn_err: 'Verbindungsfehler',
      count_suffix: ' ', code_suffix: ' · Zugangscode ',
      lobby_conn_fail: 'Server nicht erreichbar. Bitte später aktualisieren.',
      no_live1: 'Derzeit keine Live-Sitzungen', no_live2: 'Bitte Spielplan ansehen und später wiederkommen',
      recv1: 'Live-Audio wird empfangen…', recv2: 'Untertitel laufen hier in Echtzeit',
      audio_on: 'Original: an', audio_off: 'Original: aus', tts_off: 'Übersetzungsstimme: aus', tts_broadcast: 'Vorlesen:',
      msg_ended_short: 'Diese Live-Show ist beendet',
      msg_disc_refresh: 'Getrennt. Bitte Seite aktualisieren.',
      msg_reconnect: 'Verbindung verloren, Wiederherstellung… ({n})',
      msg_bt_off: 'Headset getrennt. Wiedergabe pausiert; automatische Fortsetzung nach Wiederverbindung.',
      msg_ended: 'Die Live-Show „{t}" ist beendet. Danke fürs Zuhören.',
      end_title: 'Die Show von heute Abend ist vorbei — nehmen Sie die Magie mit',
      end_stats: '📣 {a} gemeinsame Rufe · {c} Zeilen verständlich gemacht',
      end_memory: '🖼 Erinnerungskarte für heute Abend erstellen →',
      end_photo: 'Den Abend behalten · AI-Oper-Fotoshooting & Kostümwechsel →',
    },
    es: {
      ws_init: 'Sin conexión', ws_listening: 'Escuchando', ws_ended: 'Finalizado',
      ws_disconnected: 'Desconectado', ws_conn_fail: 'Fallo de conexión', ws_conn_err: 'Error de conexión',
      count_suffix: ' ', code_suffix: ' · Código de acceso ',
      lobby_conn_fail: 'No se puede conectar al servidor. Actualice más tarde.',
      no_live1: 'No hay sesiones en directo ahora mismo', no_live2: 'Consulte el programa y vuelva más tarde',
      recv1: 'Recibiendo audio en vivo…', recv2: 'Los subtítulos se muestran aquí en tiempo real',
      audio_on: 'Original: sí', audio_off: 'Original: no', tts_off: 'Voz de traducción: no', tts_broadcast: 'Lectura:',
      msg_ended_short: 'Este directo ha terminado',
      msg_disc_refresh: 'Desconectado. Actualice la página.',
      msg_reconnect: 'Conexión perdida, reconectando… ({n})',
      msg_bt_off: 'Auriculares desconectados. Reproducción en pausa; se reanuda al reconectar.',
      msg_ended: 'El directo «{t}» ha terminado. Gracias por escucharnos.',
      end_title: 'El show de esta noche terminó — llévate la magia',
      end_stats: '📣 {a} vítores del público · {c} líneas aclaradas por los subtítulos',
      end_memory: '🖼 Crear la tarjeta recuerdo de esta noche →',
      end_photo: 'Conserva la noche · Sesión de fotos de ópera IA y cambio de traje →',
    },
    en: {
      ws_init: 'Not connected', ws_listening: 'Listening', ws_ended: 'Ended',
      ws_disconnected: 'Disconnected', ws_conn_fail: 'Connection failed', ws_conn_err: 'Connection error',
      count_suffix: ' ', code_suffix: ' · Access code ',
      lobby_conn_fail: "Can't reach the server. Please refresh later.",
      no_live1: 'No live sessions right now', no_live2: 'Please check the schedule and come back later',
      recv1: 'Receiving live audio…', recv2: 'Captions roll here in real time',
      audio_on: 'Original: On', audio_off: 'Original: Off', tts_off: 'Translation voice: Off', tts_broadcast: 'Read-out:',
      msg_ended_short: 'This live show has ended',
      msg_disc_refresh: 'Disconnected. Please refresh the page.',
      msg_reconnect: 'Connection lost, reconnecting… ({n})',
      msg_bt_off: 'Headset disconnected. Playback paused; resumes on reconnect.',
      msg_ended: 'The live show "{t}" has ended. Thanks for listening.',
      end_title: "Tonight's show is over — take the magic with you",
      end_stats: '📣 {a} group cheers · {c} lines made clear by captions',
      end_memory: "🖼 Make tonight's memory card →",
      end_photo: 'Keep the night · AI opera photoshoot & costume →',
    },
  };
  const llLang = () => {
    const code = localStorage.getItem('app_lang') || 'zh';
    if (LL[code]) return code;
    return code.startsWith('zh') ? 'zh' : 'en';
  };
  const ll = (k) => (LL[llLang()] || LL.en)[k] || LL.en[k] || LL.zh[k] || '';

  function setWsState(status) {
    state.wsStatus = status;
    const map = { init: 'ws_init', listening: 'ws_listening', ended: 'ws_ended',
                  disconnected: 'ws_disconnected', conn_fail: 'ws_conn_fail', conn_err: 'ws_conn_err' };
    els.wsState.textContent = ll(map[status] || 'ws_init');
  }
  function setCapCount() { els.capCount.textContent = state.captions.length + ll('count_suffix'); }
  function renderControlBtns() {
    els.btnAudio.innerHTML = `<i data-lucide="volume-${state.audioOn ? '2' : 'x'}" class="w-4 h-4 inline-block"></i> `
      + ll(state.audioOn ? 'audio_on' : 'audio_off');
    els.btnTts.innerHTML = state.ttsOn
      ? `<i data-lucide="speech" class="w-4 h-4 inline-block"></i> ` + ll('tts_broadcast') + langLabel(state.ttsLang)
      : `<i data-lucide="languages" class="w-4 h-4 inline-block"></i> ` + ll('tts_off');
    if (window.lucide) lucide.createIcons();
  }
  function renderDynamicTexts() {
    setWsState(state.wsStatus || 'init');
    setCapCount();
    renderControlBtns();
    if (state.show) els.lsSub.textContent = state.show.host_name + ll('code_suffix') + state.show.session_code;
  }

  /* ── 候场节目（无直播时的「随便听听」） ──
   * 预烘焙川味节目音频（assets/audio/programs/，CosyVoice 离线产出），
   * 每段独立情感基调；每次进大厅随机排序，凑个茶余饭后的热闹。 */
  const FILLER = [
    { id: 'bianlian', icon: '🎭',
      title: { zh: '变脸 · 袖里乾坤', en: 'Face-Changing · Magic in the Sleeves' },
      sub: { zh: '绝活讲古 · 约22秒', en: 'Opera lore · ~22s' },
      src: './assets/audio/programs/bianlian.mp3' },
    { id: 'tuhuo', icon: '🔥',
      title: { zh: '吐火 · 一口烈焰', en: 'Fire-Spit · A Breath of Flame' },
      sub: { zh: '绝技欣赏 · 约18秒', en: 'Stage skill · ~18s' },
      src: './assets/audio/programs/tuhuo.mp3' },
    { id: 'gundeng', icon: '🏮',
      title: { zh: '滚灯 · 灯不灭人不歇', en: 'Lantern Roll · The Fun One' },
      sub: { zh: '丑角功夫 · 约17秒', en: 'Clown art · ~17s' },
      src: './assets/audio/programs/gundeng.mp3' },
    { id: 'shengqiang', icon: '🎼',
      title: { zh: '五腔共和 · 川剧声腔', en: 'Five Voices of Chuan Opera' },
      sub: { zh: '声腔导赏 · 约22秒', en: 'Vocal tour · ~22s' },
      src: './assets/audio/programs/shengqiang.mp3' },
  ];

  function fillerLang() {
    return (localStorage.getItem('app_lang') || 'zh') !== 'zh' ? 'en' : 'zh';
  }

  const FILLER_HEAD = {
    zh: ['📻 随便听听', '候场茶点 · 川味小段'],
    en: ['📻 Casual Listening', 'While waiting · bite-sized opera bits'],
  };

  function stopFiller() {
    if (state.fillerAudio) {
      state.fillerAudio.pause();
      if (window.MediaHelper) window.MediaHelper.clear(state.fillerAudio);
      state.fillerAudio = null;
    }
    state.fillerId = '';
    const row = els.liveList.querySelector('.live-item.playing');
    if (row) {
      row.classList.remove('playing');
      row.querySelector('.go').textContent = '▶';
    }
  }

  function playFiller(item, row, go) {
    if (state.fillerId === item.id) { stopFiller(); return; } // 再点一次即暂停
    stopFiller();
    const audio = new Audio(item.src);
    state.fillerAudio = audio;
    state.fillerId = item.id;
    row.classList.add('playing');
    go.textContent = '⏸';
    if (window.MediaHelper) {
      // MediaSession：蓝牙耳机线控/锁屏卡片可控（浏览器后台播报约定）
      window.MediaHelper.bind(audio, {
        title: item.title[fillerLang()], artist: '川剧场 · CHUAN',
        onStop: stopFiller,
      });
    }
    audio.onended = stopFiller;
    audio.onerror = stopFiller;
    audio.play().catch(stopFiller);
  }

  function renderFiller() {
    const lang = fillerLang();
    const head = FILLER_HEAD[lang] || FILLER_HEAD.zh;
    const picks = FILLER.slice().sort(() => Math.random() - 0.5); // 随机排序
    const card = document.createElement('div');
    card.className = 'll-card';
    card.innerHTML = `<div class="ll-filler-head"><b>${head[0]}</b><span>${head[1]}</span></div>`;
    picks.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'live-item';
      row.innerHTML = `
        <div class="ico">${item.icon}</div>
        <div class="info"><b>${escapeHtml(item.title[lang])}</b><small>${escapeHtml(item.sub[lang])}</small></div>
        <div class="go play">▶</div>`;
      row.onclick = () => playFiller(item, row, row.querySelector('.go'));
      card.appendChild(row);
    });
    els.liveList.appendChild(card);
  }

  /* ── 场次大厅 ───────────────────────────────── */
  /* 会场码深链失败提示（zh/en，其余回退英文） */
  function lobbyNotice(code) {
    const zh = ((localStorage.getItem('app_lang') || 'zh').indexOf('zh') === 0);
    const host = document.getElementById('listen-msg') || document.querySelector('#view-livelisten .ll-card');
    if (!host) return;
    const div = document.createElement('div');
    div.className = 'lobby-notice';
    div.textContent = zh
      ? `会场码 ${code} 无效或场次已结束，已为您返回场次列表`
      : `Venue code ${code} is invalid or the show has ended. Back to the session list.`;
    (document.getElementById('listen-msg') || host).prepend(div);
  }

  async function loadLiveShows() {
    stopFiller(); // 刷新列表时停止候场节目（旧播放行会被销毁）
    document.querySelectorAll('.lobby-notice').forEach((e) => e.remove());
    try {
      const resp = await fetch(`${API}/live/shows/now`);
      const body = await resp.json();
      renderLobby(body.data || []);
    } catch {
      els.liveList.innerHTML = '<div class="stream-empty">' + ll('lobby_conn_fail') + '</div>';
    }
  }

  function renderLobby(items) {
    els.liveList.innerHTML = '';
    if (!items.length) {
      els.liveList.innerHTML = '<div class="stream-empty"><span class="big" id="ll-empty-ico"></span>' + ll('no_live1') + '<br>' + ll('no_live2') + '</div>';
    renderEmptyIcons();
      renderFiller(); // 空场不冷场：候场节目随便听听
      return;
    }
    items.forEach((s) => {
      const item = document.createElement('div');
      item.className = 'live-item';
      const start = new Date(s.start_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      item.innerHTML = `
        <div class="ico">🏮</div>
        <div class="info">
          <b>${escapeHtml(s.title)}</b>
          <small>${escapeHtml(s.host_name)} · ${start} 开演 · ${s.listeners} 人正在收听</small>
        </div>
        <div class="go">›</div>`;
      item.onclick = () => enterListen(s);
      els.liveList.appendChild(item);
    });
  }

  /* ── 屏幕常亮（Wake Lock）：收听席保持屏幕不熄灭 ─
   * 收听席走 AudioContext 播 PCM 流，关屏即停，因此用「保屏」而非后台播放：
   * 进入收听页申请、退出/收播释放；系统自动释放（切后台/充电策略）后在
   * visibilitychange 回前台时自动重新申请。不支持该 API 的浏览器静默跳过。 */
  async function requestWakeLock() {
    if (!('wakeLock' in navigator) || state.wakeLock) return;
    try {
      state.wakeLock = await navigator.wakeLock.request('screen');
      state.wakeLock.addEventListener('release', () => { state.wakeLock = null; });
    } catch { /* 拒绝/不支持：静默降级 */ }
  }
  function releaseWakeLock() {
    if (state.wakeLock) {
      try { state.wakeLock.release(); } catch { /* ignore */ }
      state.wakeLock = null;
    }
  }
  document.addEventListener('visibilitychange', () => {
    // Wake Lock 在页面隐藏时被系统强制释放，回前台且仍在收听中则补申请
    if (document.visibilityState === 'visible') {
      if (!state.ended && state.show) requestWakeLock();
      exitBackgroundMode(); // 回前台：停降级音频，实时原声随后续 PCM 帧恢复
    } else {
      enterBackgroundMode(); // 关屏/切后台：AudioContext 必停，降级预录制译文音频
    }
  });

  /* ── 关屏降级播放：预合成 TTS 译文经 <audio> 排队 ─
   * 页面隐藏时 AudioContext 被系统挂起，实时原声静音；
   * 此时切换为「收到一句 → 预合成 TTS 译文 → <audio> 排队播」，
   * <audio> 在 Android 上后台可继续播放（iOS 锁屏卡片可续播）。
   * 回前台自动退出降级，实时原声恢复（PCM 积压>1.5s 自动追齐）。 */
  function enterBackgroundMode() {
    if (state.ended || !state.show || state.bgMode) return;
    state.bgMode = true;
    if (state.audioCtx) { try { state.audioCtx.suspend(); } catch { /* ignore */ } }
  }

  function exitBackgroundMode() {
    if (!state.bgMode) return;
    state.bgMode = false;
    state.bgQueue = [];
    state.bgBusy = false;
    if (state.bgAudio) {
      if (window.MediaHelper) MediaHelper.clear(state.bgAudio);
      state.bgAudio.pause();
      state.bgAudio.src = '';
    }
    if (state.audioCtx) { try { state.audioCtx.resume(); } catch { /* ignore */ } }
  }

  function enqueueBackground(cap) {
    const lang = state.displayLang !== 'zh' ? state.displayLang : 'zh';
    const text = (cap.translations || {})[lang] || cap.text; // 无译文降级播原文
    if (!text) return;
    state.bgQueue.push({ seq: cap.seq, text, lang });
    while (state.bgQueue.length > 6) state.bgQueue.shift(); // 防积压：只播最近 6 句
    pumpBackground();
  }

  async function pumpBackground() {
    if (state.bgBusy || state.bgMode === false || !state.bgQueue.length) return;
    state.bgBusy = true;
    const item = state.bgQueue.shift();
    try {
      const resp = await fetch(ttsUrl(item.text, item.lang));
      if (!resp.ok) throw new Error('tts ' + resp.status);
      const blob = await resp.blob();
      if (!state.bgMode) return; // 期间已回前台
      if (!state.bgAudio) state.bgAudio = new Audio();
      state.bgAudio.src = URL.createObjectURL(blob);
      if (window.MediaHelper) {
        MediaHelper.bind(state.bgAudio, {
          title: state.show.title + ' · 译文收听',
          album: '四川省川剧院',
        });
      }
      await new Promise((resolve) => {
        state.bgAudio.onended = resolve;
        state.bgAudio.onerror = resolve;
        state.bgAudio.play().catch(resolve); // iOS 后台禁止新起播放：跳过本句
      });
    } catch { /* 单句失败跳过，不中断队列 */ }
    finally {
      state.bgBusy = false;
      pumpBackground(); // 播完接续下一句
    }
  }

  /* ── 进入播放页 ─────────────────────────────── */
  function enterListen(show) {
    stopFiller(); // 进直播间停候场节目，避免与现场原声叠加
    state.show = show;
    state.captions = [];
    state.ended = false;
    state.displayLang = show.target_langs[0] || 'zh';
    state.ttsLang = state.displayLang !== 'zh' ? state.displayLang : 'en';
    els.viewLobby.classList.add('hidden');
    els.viewListen.classList.remove('hidden');
    els.lsTitle.textContent = show.title;
    els.lsSub.textContent = show.host_name + ll('code_suffix') + show.session_code;
    renderLangChips();
    els.stream.innerHTML = '<div class="stream-empty"><span class="big" id="st-empty-ico"></span>' + ll('recv1') + '<br>' + ll('recv2') + '</div>';
    renderEmptyIcons();
    state.stick = true;
    state.lastSeq = 0;
    state.reconnectCount = 0;
    els.latestBtn.classList.add('hidden');
    els.applaudCount.textContent = '';
    setCapCount();
    msg(els.listenMsg, '', '');
    // 通知其它模块（川剧护照）：已进入收听席
    window.dispatchEvent(new CustomEvent('app:live:joined', { detail: { showId: show && show.id, show: show } }));
    connectWs(show.session_code);
    requestWakeLock(); // 收听中保持屏幕常亮（AudioContext 关屏即停）
    // 整合进首页后 URL 需带 view=livelisten，刷新不丢视图
    history.replaceState(null, '', `?view=livelisten&code=${show.session_code}`);
  }

  /* 本场数据落盘：观剧记忆卡读取（收播 / 手动退出 / 关页三时机） */
  function persistShowStats() {
    if (!state.show) return;
    try {
      localStorage.setItem('chuan_applaud_last', String(state.applaudTotal || 0));
      localStorage.setItem('chuan_caps_last', String(state.captions.length));
      localStorage.setItem('chuan_seen_terms', JSON.stringify(state.seenTerms));
    } catch (e) { /* ignore */ }
  }

  function exitListen() {
    persistShowStats();
    window.dispatchEvent(new CustomEvent('app:live:ended'));
    state.ended = true; // 阻止自动重连
    closeWs();
    stopAudio();
    exitBackgroundMode(); // 停降级译文音频与媒体卡片
    releaseWakeLock();
    els.viewListen.classList.add('hidden');
    els.viewLobby.classList.remove('hidden');
    loadLiveShows();
    history.replaceState(null, '', location.pathname);
  }

  /* ── 语言选择 ───────────────────────────────── */
  function renderLangChips() {
    els.langChips.innerHTML = '';
    const options = [{ code: 'zh', label: '中文原文' }]
      .concat((state.show.target_langs || []).map((c) => ({ code: c, label: langLabel(c) })));
    options.forEach((opt) => {
      const chip = document.createElement('span');
      chip.className = 'chip' + (state.displayLang === opt.code ? ' active' : '');
      chip.textContent = opt.label;
      chip.onclick = () => {
        state.displayLang = opt.code;
        if (opt.code !== 'zh') state.ttsLang = opt.code;
        renderLangChips();
        renderCaptions();
      };
      els.langChips.appendChild(chip);
    });
  }

  /* ── 观众 WebSocket ─────────────────────────── */
  function connectWs(code) {
    closeWs();
    const ws = new WebSocket(wsUrl(code, state.audioOn));
    ws.binaryType = 'arraybuffer';
    state.ws = ws;
    ws.onopen = () => {
      state.reconnectCount = 0; // 连接成功重置计数
      els.dotWs.className = 'dot live';
      setWsState('listening');
      msg(els.listenMsg, '', '');
      state.pingTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}');
      }, HEARTBEAT_MS);
    };
    ws.onclose = (ev) => {
      clearInterval(state.pingTimer);
      if (ws !== state.ws) return; // 已被新连接替换，旧连接的 onclose 忽略
      if (state.ended) return;
      if (ev && ev.code === 4404) {
        // 4404 = 会场不存在或已结束（服务端主动关闭）
        state.ended = true;
        msg(els.listenMsg, ll('msg_ended_short'), 'ok');
        els.dotWs.className = 'dot err';
        setWsState('ended');
        if (window.ContextShop) setTimeout(() => window.ContextShop.fillEndShop(), 100);
        return;
      }
      els.dotWs.className = 'dot err';
      setWsState('disconnected');
      if (state.show) {
        state.reconnectCount = (state.reconnectCount || 0) + 1;
        if (state.reconnectCount > 20) {
          state.ended = true;
          msg(els.listenMsg, ll('msg_disc_refresh'), 'err');
          setWsState('conn_fail');
          return;
        }
        msg(els.listenMsg, ll('msg_reconnect').replace('{n}', state.reconnectCount), 'warn');
        setTimeout(() => { if (!state.ended) connectWs(state.show.session_code); }, Math.min(3000 * state.reconnectCount, 15000));
      }
    };
    ws.onerror = () => { els.dotWs.className = 'dot err'; setWsState('conn_err'); };
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        handleTextFrame(JSON.parse(ev.data));
      } else {
        playPcm(ev.data); // 二进制帧 = 现场原声 PCM
      }
    };
  }

  function renderEmptyIcons() {
    if (!window.lucide) return;
    const put = (id, name) => {
      const span = document.getElementById(id);
      if (span && !span.firstChild) { span.innerHTML = `<i data-lucide="${name}" class="w-10 h-10 mx-auto opacity-50"></i>`; lucide.createIcons(); }
    };
    put('ll-empty-ico', 'radio'); put('st-empty-ico', 'mic'); put('ld-empty-ico', 'radio');
  }
  /* ── 叫好互动与字幕粘底 ─────────────────── */
  function scrollToLatest() {
    els.latestBtn.classList.add('hidden');
    // html 已有 scroll-smooth，scrollTop 赋值即平滑滚动（兼容嵌入式浏览器的 window.scrollTo 失效）
    var el = document.scrollingElement || document.documentElement;
    el.scrollTop = el.scrollHeight;
  }

  function flyApplaud(selfSend) {
    // 同屏最多 6 个飞字，位置/大小/角度随机，1.3s 后自净
    const existing = document.querySelectorAll('.applaud-fly');
    if (existing.length >= 6) existing[0].remove();
    const el = document.createElement('div');
    el.className = 'applaud-fly' + (selfSend ? '' : ' small');
    el.textContent = selfSend ? '好！' : (['好！','好！！','Bravo!','妙呀！'][Math.floor(Math.random() * 4)]);
    el.style.left = (12 + Math.random() * 70) + 'vw';
    el.style.bottom = (12 + Math.random() * 22) + 'vh';
    el.style.setProperty('--rot', (Math.random() * 16 - 8).toFixed(1) + 'deg');
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1350);
  }

  els.applaud.addEventListener('click', () => {
    if (!state.ws || state.ws.readyState !== 1) return;
    const now = Date.now();
    if (now - state.applaudLast < 500) return; // 本端 0.5s 节流
    state.applaudLast = now;
    flyApplaud(true); // 本端即时反馈，广播帧到达时其他端同步飞屏
    try { state.ws.send(JSON.stringify({ type: 'applaud' })); } catch { /* 断线时忽略 */ }
  });

  els.latestBtn.addEventListener('click', scrollToLatest);

  window.addEventListener('scroll', () => {
    if (!state.show || state.ended) return;
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
    state.stick = nearBottom;
    if (nearBottom) els.latestBtn.classList.add('hidden');
    else if (state.captions.length) els.latestBtn.classList.remove('hidden');
  }, { passive: true });

  function closeWs() {
    clearInterval(state.pingTimer);
    if (state.ws) {
      state.ws.onclose = null; // 主动关闭不触发重连
      try { state.ws.close(); } catch { /* ignore */ }
      state.ws = null;
    }
  }

  function handleTextFrame(data) {
    if (data.type === 'caption') {
      if (state.lastSeq && data.seq <= state.lastSeq) return; // 重连补发去重
      state.lastSeq = data.seq;
      state.captions.push(data);
      window.dispatchEvent(new CustomEvent('app:live:caption'));
      appendCaption(data);
      if (state.bgMode) enqueueBackground(data);   // 关屏降级：预合成译文排队播
      else if (state.ttsOn) speakTranslation(data); // 前台：可选译文播报
    } else if (data.type === 'highlight') {
      renderHighlight(data); // 绝技看点卡片：强调样式、自动收起
      if (data.term && !state.seenTerms.includes(data.term)) state.seenTerms.push(data.term);
      window.dispatchEvent(new CustomEvent('app:live:highlight', { detail: { term: data.term } }));
    } else if (data.type === 'listeners') {
      els.lsCount.textContent = data.count;
    } else if (data.type === 'applaud') {
      state.applaudTotal = data.total || state.applaudTotal;
      els.applaudCount.textContent = data.total > 0 ? data.total : '';
      flyApplaud(false); // 全场共感：任何人叫好，所有人看到飞屏
    } else if (data.type === 'session_end') {
      window.dispatchEvent(new CustomEvent('app:live:ended'));
      state.ended = true;
      clearInterval(state.pingTimer);
      closeWs();
      stopAudio();
      exitBackgroundMode(); // 收播：停降级译文音频
      releaseWakeLock(); // 收播后不再保屏
      els.dotWs.className = 'dot err';
      setWsState('ended');
      msg(els.listenMsg, ll('msg_ended').replace('{t}', data.title), 'ok');
      persistShowStats();
      // 收播转化：静态渲染（WS 已关，不依赖网络）——今晚的数据 + 记忆卡 + 旅拍
      const card = document.createElement('div');
      card.className = 'end-card';
      card.innerHTML = `
        <div class="end-title"><i data-lucide="sparkles" class="w-4 h-4 inline-block"></i> ${ll('end_title')}</div>
        <div class="end-stats">${ll('end_stats').replace('{a}', state.applaudTotal || 0).replace('{c}', state.captions.length)}</div>
        <div id="end-shop"></div>
        <a class="end-link" href="#" id="end-memory">${ll('end_memory')}</a>
        <a class="end-link" href="./index.html?view=wenchuang&sub=ai-photoshoot">${ll('end_photo')}</a>`;
      card.querySelector('#end-memory').addEventListener('click', (e) => {
        e.preventDefault();
        if (window.MemoryCard) window.MemoryCard.open();
      });
      els.stream.appendChild(card);
      if (window.ContextShop) setTimeout(() => window.ContextShop.fillEndShop(), 100);
      if (window.lucide) lucide.createIcons();
      requestAnimationFrame(() => { if (state.stick) scrollToLatest(); else els.latestBtn.classList.remove('hidden'); });
    }
  }

  /* ── 原声播放（WS 二进制 PCM → Web Audio 排队） ─ */
  function playPcm(arrayBuffer) {
    if (!state.audioOn) return;
    if (!state.audioCtx) {
      state.audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
      state.playHeadAt = state.audioCtx.currentTime;
    }
    if (state.audioCtx.state === 'suspended') state.audioCtx.resume();
    const samples = new Int16Array(arrayBuffer);
    if (!samples.length) return;
    const buffer = state.audioCtx.createBuffer(1, samples.length, SAMPLE_RATE);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;

    const source = state.audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(state.audioCtx.destination);
    // 按时间轴排队：网络抖动时保持连续，落后过多则追齐（丢弃积压）
    const now = state.audioCtx.currentTime;
    state.playHeadAt = Math.max(state.playHeadAt, now);
    if (state.playHeadAt - now > 1.5) state.playHeadAt = now; // 积压超 1.5s 直接追齐
    source.start(state.playHeadAt);
    state.playHeadAt += buffer.duration;
  }

  function stopAudio() {
    if (state.audioCtx) { try { state.audioCtx.close(); } catch { /* ignore */ } state.audioCtx = null; }
  }

  /* ── 译文语音播报（复用后端 TTS） ───────────── */
  async function speakTranslation(cap) {
    const text = (cap.translations || {})[state.ttsLang];
    if (!text || state.ttsPlaying) return;
    state.ttsPlaying = true;
    try {
      const resp = await fetch(ttsUrl(text, state.ttsLang));
      if (!resp.ok) return;
      const blob = await resp.blob();
      await new Promise((resolve) => {
        const audio = new Audio(URL.createObjectURL(blob));
        audio.onended = resolve;
        audio.onerror = resolve;
        audio.play().catch(resolve);
      });
    } catch { /* 播报失败不影响字幕 */ }
    finally { state.ttsPlaying = false; }
  }

  /* ── 字幕渲染 ───────────────────────────────── */
  function appendCaption(cap) {
    const empty = els.stream.querySelector('.stream-empty');
    if (empty) empty.remove();
    const prev = els.stream.querySelector('.cap-item.latest');
    if (prev) prev.classList.remove('latest');
    els.stream.appendChild(buildCapItem(cap, true));
    setCapCount();
    requestAnimationFrame(() => { if (state.stick) scrollToLatest(); else els.latestBtn.classList.remove('hidden'); });
    while (els.stream.children.length > 200) els.stream.removeChild(els.stream.firstChild);
  }

  function renderCaptions() {
    els.stream.innerHTML = '';
    state.captions.forEach((cap, i) => {
      els.stream.appendChild(buildCapItem(cap, i === state.captions.length - 1));
    });
    setCapCount();
  }

  function buildCapItem(cap, latest) {
    const item = document.createElement('div');
    item.className = 'cap-item' + (latest ? ' latest' : '');
    const time = new Date((cap.ts || 0) * 1000).toLocaleTimeString('zh-CN', { hour12: false });
    let trHtml = '';
    if (state.displayLang && state.displayLang !== 'zh') {
      const text = (cap.translations || {})[state.displayLang];
      trHtml = text
        ? `<div class="tr">${escapeHtml(text)}</div>`
        : '<div class="tr" style="opacity:.5">（该句译文未生成）</div>';
    }
    item.innerHTML = `
      <div class="meta">#${cap.seq} · ${time}</div>
      <div class="zh">${escapeHtml(cap.text)}</div>${trHtml}`;
    return item;
  }

  /* ── 绝技看点卡片 ───────────────────────────── */
  function renderHighlight(hl) {
    // 同屏最多 1 条：新看点到来先移除旧卡片
    const old = els.stream.querySelector('.hl-card');
    if (old) old.remove();
    const empty = els.stream.querySelector('.stream-empty');
    if (empty) empty.remove();
    const card = document.createElement('div');
    card.className = 'hl-card';
    const body = (hl.translations || {})[state.displayLang] || hl.text;
    card.innerHTML = `
      <div class="hl-term"><i data-lucide="sparkles" class="w-3.5 h-3.5 inline-block"></i> ${escapeHtml(hl.term || '')}</div>
      <div class="hl-body">${escapeHtml(body || '')}</div>` +
      (window.ContextShop ? window.ContextShop.shopLinkFor(hl.term) : '');
    els.stream.appendChild(card);
    if (window.lucide) lucide.createIcons();
    requestAnimationFrame(() => { if (state.stick) scrollToLatest(); else els.latestBtn.classList.remove('hidden'); });
    setTimeout(() => card.remove(), 8000); // 8 秒自动收起，不占字幕流
  }

  /* ── 控制按钮 ───────────────────────────────── */
  els.btnAudio.onclick = () => {
    state.audioOn = !state.audioOn;
    renderControlBtns();
    els.btnAudio.classList.toggle('on', state.audioOn);
    if (!state.audioOn) { stopAudio(); }
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      // 切换原声订阅需要重连（audio 是连接级参数）
      state.ws.onclose = null; // 主动关闭不触发重连
      state.ws.close();
      state.ws = null;
      connectWs(state.show.session_code);
    }
  };

  // 专用耳机断连：立即停原声（AudioContext 不在 ble-guard 兜底范围，须自行关闭）
  window.addEventListener('ble:disconnected', () => {
    stopAudio();
    stopFiller(); // 候场节目同样随耳机断连停止
    msg(els.listenMsg, ll('msg_bt_off'), 'warn');
  });
  // 耳机重连成功：清提示，原声随后续 PCM 帧自动恢复
  window.addEventListener('ble:connected', () => {
    if (!state.ended) msg(els.listenMsg, '', '');
  });
  els.btnTts.onclick = () => {
    state.ttsOn = !state.ttsOn;
    renderControlBtns();
    els.btnTts.classList.toggle('on', state.ttsOn);
  };
  els.btnExit.onclick = exitListen;
  window.addEventListener('app:live:refresh', () => { if (!state.ended) loadLiveShows(); });
  window.addEventListener('pagehide', () => { if (state.show && !state.ended) persistShowStats(); });
  els.lobbyRefresh.onclick = loadLiveShows;
  renderDynamicTexts(); // 初始渲染：按当前语言设置状态/计数/开关按钮
  // 语言切换：大厅在场时重拉（候场节目标题/副题随语言刷新）
  window.addEventListener('app:langchange', () => {
    renderDynamicTexts();
    if (!els.viewLobby.classList.contains('hidden')) loadLiveShows();
  });

  /* ── 初始化：支持 ?code= 直达 ────────────────── */
  (async function init() {
    const code = new URLSearchParams(location.search).get('code');
    if (code) {
      try {
        const resp = await fetch(`${API}/live/shows/now`);
        const body = await resp.json();
        const show = (body.data || []).find((s) => s.session_code === code.toUpperCase());
        if (show) { enterListen(show); return; }
      } catch { /* 查询失败回退到大厅 */ }
    }
    // 先渲染列表（会清旧提示），再补会场码失败提示
    loadLiveShows().then(() => { if (code) lobbyNotice(code.toUpperCase()); });
  })();

  /* ── 调试钩子：仅 ?debug 时暴露内部（供自动化测试关屏降级逻辑） ── */
  if (new URLSearchParams(location.search).has('debug')) {
    window.__ListenDebug = { state, enterBackgroundMode, exitBackgroundMode, enqueueBackground };
  }
})();
