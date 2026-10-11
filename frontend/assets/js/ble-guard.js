/* 专用耳机蓝牙准入模块（ble-guard）
 *
 * 业务流程：游客在剧院门口租用专用蓝牙耳机 → 扫码进入本服务页面 →
 *   停留在准入页（仅可选语言 + 连接专用耳机）→ 连接成功才解锁正式服务。
 *   耳机断连 → 自动回退准入页并停止全部音频；断连前低电量则提示充电后使用。
 *
 * 高内聚：准入页 UI（样式/DOM/文案 i18n）、BLE 连接、电量检测、断连回退、
 *        自动重连，全部收敛于此文件，任意页面引入即启用。
 * 低耦合：对外仅派发 window 事件 'ble:connected' / 'ble:disconnected'
 *        （detail: { name, battery, lowBattery }），各音频模块自行监听停止；
 *        另兜底暂停页面全部 <audio>（AudioContext 由各模块监听事件自行关闭）。
 *        语言选择复用页面全局 setLanguage（存在时）与 app:langchange 事件。
 *
 * 环境要求：Web Bluetooth 需 HTTPS（或 localhost）+ Chrome/Edge/Android。
 * 开发旁路：URL 带 ?demo=1 跳过准入（仅限本地调试，生产请勿传播该参数）。
 * 耳机识别：按蓝牙名称前缀过滤（租赁定制耳机统一命名，如 CHUAN-001）。
 */
(function () {
  'use strict';

  /* localStorage 安全封装（隐私模式/禁用时降级为内存对象） */
  var _memStore = {};
  function safeGet(k) { try { return localStorage.getItem(k); } catch (e) { return _memStore[k] || null; } }
  function safeSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { _memStore[k] = v; } }

  /* ── 配置（可通过 window.BLE_GATE_CONFIG 覆盖） ── */
  const CFG = Object.assign({
    namePrefix: 'CHUAN',    // 专用耳机蓝牙广播名前缀
    lowBattery: 20,         // 低电量阈值（%）
    svcBattery: 0x180F,     // BLE 标准电量服务
    chrBattery: 0x2A19,     // 电量特征值
    pollMs: 60000,          // 在连电量轮询间隔
    retryMs: 3000,          // 断连后自动重连间隔
    skipEnabled: true,      // 允许「跳过」进入（耳机未到位的检查阶段用；上线置 false）
  }, window.BLE_GATE_CONFIG || {});

  // 旁路标志在脚本求值时立刻快照：live-listen 深链的 replaceState 会改写 URL
  // （剥掉 demo/view 参数），若延迟到 DOMContentLoaded 再读就会丢失旁路。
  var DEMO_BYPASS = new URLSearchParams(location.search).get('demo') === '1';

  /* ── 准入页多语言文案（8 语种，与界面语言一致） ── */
  const I18N = {
    zh: { title: '川剧智能同传服务', subtitle: '请先选择语言，再连接您租用的专用耳机以开启服务',
      stepLang: '① 选择语言', stepConnect: '② 连接专用耳机',
      connectBtn: '连接专用耳机', connecting: '正在连接耳机…', connected: '耳机已连接，祝您观演愉快',
      disconnected: '耳机连接已断开，请重新连接', lowBattery: '耳机电量偏低（{b}%），请充电后继续使用',
      lowBattNow: '当前耳机电量 {b}%，建议尽快充电', unsupported: '当前浏览器不支持蓝牙连接，请使用 Chrome 浏览器或至服务台寻求帮助', helpTitle: '蓝牙在此浏览器不可用', helpL1: 'iPhone / 微信内置浏览器不支持网页连接蓝牙', helpL2: '换用安卓 Chrome，或到一楼服务台，工作人员协助您佩戴耳机',
      footer: '未租用耳机的游客，请至剧院门口服务台办理租用', skipBtn: '暂不连接，先浏览页面' },
    en: { title: 'Sichuan Opera Live Interpretation', subtitle: 'Select your language, then connect your rental headset to start',
      stepLang: '① Select language', stepConnect: '② Connect rental headset',
      connectBtn: 'Connect Headset', connecting: 'Connecting…', connected: 'Headset connected. Enjoy the show!',
      disconnected: 'Headset disconnected. Please reconnect.', lowBattery: 'Headset battery is low ({b}%). Please charge it before continuing.',
      lowBattNow: 'Headset battery: {b}%. Charging is recommended soon.', unsupported: 'Bluetooth is not supported by this browser. Please use Chrome or ask the service desk for help.', helpTitle: 'Bluetooth unavailable in this browser', helpL1: 'iPhone and in-app browsers cannot connect to web Bluetooth', helpL2: 'Switch to Chrome on Android, or visit the lobby service desk for help',
      footer: 'Haven\'t rented a headset yet? Please visit the service desk at the theatre entrance.', skipBtn: 'Skip and browse without a headset' },
    ja: { title: '四川オペラ同時通訳サービス', subtitle: '言語を選択し、レンタル専用イヤホンを接続してください',
      stepLang: '① 言語を選択', stepConnect: '② 専用イヤホンを接続',
      connectBtn: 'イヤホンを接続', connecting: '接続中…', connected: '接続完了。ご鑑賞をお楽しみください',
      disconnected: 'イヤホンが切断されました。再接続してください', lowBattery: 'イヤホンのバッテリーが少ないです（{b}%）。充電してからご使用ください。',
      lowBattNow: '現在のバッテリー：{b}%。早めの充電をおすすめします。', unsupported: 'このブラウザはBluetoothに対応していません。Chromeをご利用いただくか、サービスカウンターまで。', helpTitle: 'このブラウザはBluetooth非対応', helpL1: 'iPhoneやアプリ内ブラウザでは接続できません', helpL2: 'AndroidのChromeに切り替えるか、ロビーのサービスカウンターへ',
      footer: 'イヤホン未レンタルの方は劇場入口のサービスカウンターへ', skipBtn: 'スキップして閲覧のみ' },
    ko: { title: '쓰촨 오페라 동시통역 서비스', subtitle: '언어를 선택한 후 대여 전용 이어폰을 연결하세요',
      stepLang: '① 언어 선택', stepConnect: '② 전용 이어폰 연결',
      connectBtn: '이어폰 연결', connecting: '연결 중…', connected: '연결되었습니다. 공연을 즐기세요!',
      disconnected: '이어폰 연결이 끊겼습니다. 다시 연결하세요', lowBattery: '이어폰 배터리가 부족합니다({b}%). 충전 후 사용해 주세요.',
      lowBattNow: '현재 배터리: {b}%. 빠른 충전을 권장합니다.', unsupported: '이 브라우저는 블루투스를 지원하지 않습니다. Chrome을 사용하거나 서비스 데스크에 문의하세요.', helpTitle: '이 브라우저는 블루투스 미지원', helpL1: 'iPhone·앱 내장 브라우저는 웹 블루투스 연결이 불가합니다', helpL2: '안드로이드 Chrome으로 열거나 로비 서비스 데스크로 와 주세요',
      footer: '이어폰 미대여 관객은 극장 입구 서비스 데스크로', skipBtn: '건너뛰고 둘러보기' },
    es: { title: 'Interpretación de la Ópera de Sichuan', subtitle: 'Elija su idioma y conecte los auriculares de alquiler para comenzar',
      stepLang: '① Elija idioma', stepConnect: '② Conecte los auriculares',
      connectBtn: 'Conectar auriculares', connecting: 'Conectando…', connected: 'Auriculares conectados. ¡Disfrute de la función!',
      disconnected: 'Auriculares desconectados. Vuelva a conectarlos.', lowBattery: 'Batería baja ({b}%). Cargue los auriculares antes de continuar.',
      lowBattNow: 'Batería actual: {b}%. Se recomienda cargar pronto.', unsupported: 'Este navegador no admite Bluetooth. Use Chrome o acuda al mostrador de servicio.', helpTitle: 'Bluetooth no disponible aquí', helpL1: 'iPhone y los navegadores integrados no admiten Web Bluetooth', helpL2: 'Use Chrome en Android o acuda al mostrador del vestíbulo',
      footer: '¿Sin auriculares alquilados? Acuda al mostrador a la entrada del teatro.',
      skipBtn: 'Entrar sin auriculares' },
    fr: { title: 'Interprétation de l\'Opéra du Sichuan', subtitle: 'Choisissez votre langue, puis connectez votre casque loué pour commencer',
      stepLang: '① Choisissez la langue', stepConnect: '② Connectez le casque',
      connectBtn: 'Connecter le casque', connecting: 'Connexion…', connected: 'Casque connecté. Bon spectacle !',
      disconnected: 'Casque déconnecté. Veuillez le re connecter.', lowBattery: 'Batterie faible ({b}%). Veuillez recharger avant de continuer.',
      lowBattNow: 'Batterie actuelle : {b}%. Recharge recommandée.', unsupported: 'Bluetooth non pris en charge. Utilisez Chrome ou demandez au comptoir de service.', helpTitle: 'Bluetooth indisponible ici', helpL1: 'iPhone et les navigateurs intégrés ne gèrent pas le Web Bluetooth', helpL2: 'Passez à Chrome sur Android ou au comptoir du hall',
      footer: 'Pas encore de casque ? Rendez-vous au comptoir à l\'entrée du théâtre.', skipBtn: 'Continuer sans casque' },
    de: { title: 'Live-Dolmetschen der Sichuan-Oper', subtitle: 'Wählen Sie Ihre Sprache und verbinden Sie den Miet-Kopfhörer',
      stepLang: '① Sprache wählen', stepConnect: '② Miet-Kopfhörer verbinden',
      connectBtn: 'Kopfhörer verbinden', connecting: 'Verbinde…', connected: 'Kopfhörer verbunden. Viel Spaß!',
      disconnected: 'Kopfhörer getrennt. Bitte neu verbinden.', lowBattery: 'Akku schwach ({b}%). Bitte vor Nutzung aufladen.',
      lowBattNow: 'Aktueller Akku: {b}%. Baldiges Aufladen empfohlen.', unsupported: 'Bluetooth wird nicht unterstützt. Nutzen Sie Chrome oder fragen Sie am Servicepunkt.', helpTitle: 'Bluetooth hier nicht verfügbar', helpL1: 'iPhone und In-App-Browser unterstützen kein Web-Bluetooth', helpL2: 'Nutzen Sie Chrome auf Android oder den Servicedesk in der Lobby',
      footer: 'Kein Kopfhörer gemietet? Servicepunkt am Theatereingang.', skipBtn: 'Ohne Kopfhörer fortfahren' },
    ru: { title: 'Синхронный перевод оперы Сычуани', subtitle: 'Выберите язык и подключите арендованную гарнитуру',
      stepLang: '① Выберите язык', stepConnect: '② Подключите гарнитуру',
      connectBtn: 'Подключить гарнитуру', connecting: 'Подключение…', connected: 'Гарнитура подключена. Приятного просмотра!',
      disconnected: 'Гарнитура отключена. Подключите снова.', lowBattery: 'Низкий заряд гарнитуры ({b}%). Зарядите перед использованием.',
      lowBattNow: 'Текущий заряд: {b}%. Рекомендуется зарядить.', unsupported: 'Браузер не поддерживает Bluetooth. Используйте Chrome или обратитесь на стойку.', helpTitle: 'Bluetooth недоступен здесь', helpL1: 'iPhone и встроенные браузеры не поддерживают Web Bluetooth', helpL2: 'Откройте Chrome на Android или подойдите к стойке в холле',
      footer: 'Без гарнитуры? Обратитесь на стойку у входа в театр.',
      skipBtn: 'Войти без гарнитуры' },
  };

  const LANG_LABELS = {
    zh: '中文', en: 'English', ja: '日本語', ko: '한국어',
    es: 'Español', fr: 'Français', de: 'Deutsch', ru: 'Русский',
  };

  /* ── 运行时状态 ─────────────────────────────── */
  const state = {
    lang: (safeGet('app_lang') || 'zh').slice(0, 2),
    device: null,
    battery: null,
    lowBatt: false,
    unlocked: false,
    pollTimer: null,
    retryTimer: null,
    els: {},
  };
  const t = (key, extra) => {
    const dict = I18N[state.lang] || I18N.en;
    let s = dict[key] || I18N.en[key] || key;
    if (extra) s = s.replace('{b}', String(extra));
    return s;
  };

  /* ── 准入页 UI（样式 + DOM 动态注入，随引随用） ── */
  const GATE_CSS = `
.ble-gate{position:fixed;inset:0;z-index:9999;overflow-y:auto;
  background:linear-gradient(160deg,#0F0A07 0%,#241610 55%,#0E0805 100%);
  display:flex;align-items:center;justify-content:center;padding:24px}
.ble-gate.hidden{display:none}
.ble-gate-card{max-width:420px;width:100%;text-align:center;color:#F5EDE0;
  animation:gateIn .45s cubic-bezier(.2,.7,.3,1)}
@keyframes gateIn{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
.ble-gate-seal{width:64px;height:64px;margin:0 auto 16px;background:linear-gradient(135deg,#C73E3A,#8B1A1A);
  color:#F5EDE0;border-radius:14px;display:flex;align-items:center;justify-content:center;
  font-family:'Noto Serif SC',serif;font-size:32px;font-weight:700;transform:rotate(-3deg);
  box-shadow:0 8px 24px rgba(199,62,58,.35)}
.ble-gate-title{font-family:'Noto Serif SC',serif;font-size:22px;font-weight:700;letter-spacing:2px;margin-bottom:8px;
  text-shadow:0 2px 12px rgba(0,0,0,.5)}
.ble-gate-sub{font-size:13px;color:rgba(245,237,224,.6);line-height:1.7;margin-bottom:20px}
.ble-gate-step{font-size:12px;color:#E0A83E;letter-spacing:1px;margin:18px 0 10px;text-align:left;font-weight:600}
.ble-gate-langs{display:flex;flex-wrap:wrap;gap:8px}
.ble-gate-lang{padding:8px 14px;border-radius:999px;font-size:12px;cursor:pointer;white-space:nowrap;
  border:1px solid rgba(245,237,224,.15);background:rgba(255,249,242,.06);color:rgba(245,237,224,.65);transition:all .15s}
.ble-gate-lang:hover{background:rgba(255,249,242,.12);color:#F5EDE0}
.ble-gate-lang.active{background:#E0A83E;color:#0F0A07;border-color:#E0A83E;font-weight:700}
.ble-gate-btn{display:block;width:100%;padding:15px;margin-top:6px;border:none;border-radius:12px;
  font-size:15px;font-weight:700;cursor:pointer;background:#C73E3A;color:#F5EDE0;transition:all .15s}
.ble-gate-btn:hover:not(:disabled){background:#8B1A1A;box-shadow:0 4px 20px rgba(199,62,58,.35)}
.ble-gate-btn:active:not(:disabled){transform:scale(.98)}
.ble-gate-btn:disabled{opacity:.5;cursor:not-allowed}
.ble-gate-alert{font-size:13px;padding:11px 13px;border-radius:10px;margin-bottom:14px;line-height:1.6;text-align:left}
.ble-gate-alert.warn{background:rgba(224,168,62,.12);color:#F5C557;border:1px solid rgba(224,168,62,.35)}
.ble-gate-alert.err{background:rgba(199,62,58,.15);color:#F5A5A0;border:1px solid rgba(199,62,58,.35)}
.ble-gate-status{font-size:12px;color:rgba(245,237,224,.5);margin-top:12px;line-height:1.7;min-height:18px}
.ble-gate-footer{font-size:11px;color:rgba(245,237,224,.35);margin-top:22px;line-height:1.7}
.ble-gate-batt{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:rgba(245,237,224,.5);
  margin-top:10px;padding:4px 10px;border-radius:999px;border:1px solid rgba(245,237,224,.12)}
.ble-gate-batt.low{color:#F5A5A0;border-color:rgba(199,62,58,.4)}
.ble-gate-batt.hidden,.ble-gate-alert.hidden{display:none}
.ble-gate-help{margin-top:14px;padding:14px;border-radius:12px;text-align:left;
  background:rgba(224,168,62,.08);border:1px solid rgba(224,168,62,.3)}
.ble-gate-help-title{font-size:14px;font-weight:700;color:#F5C557;margin-bottom:8px;
  display:flex;align-items:center;gap:7px}
.ble-gate-help-line{font-size:12px;color:rgba(245,237,224,.75);line-height:1.8;padding-left:20px;position:relative}
.ble-gate-help-line::before{content:'•';position:absolute;left:6px;color:#E0A83E}
.ble-gate-help-cta{margin-top:10px;padding:10px;border-radius:10px;text-align:center;
  background:rgba(224,168,62,.14);color:#FFE9C8;font-size:13px;font-weight:700;
  display:flex;align-items:center;justify-content:center;gap:8px}
.ble-gate-skip{margin-top:12px;background:none;border:none;cursor:pointer;
  font-size:12px;color:rgba(245,237,224,.45);text-decoration:underline;text-underline-offset:3px;
  transition:color .15s}
.ble-gate-skip:hover{color:rgba(245,237,224,.8)}
`;

  function buildGate() {
    const style = document.createElement('style');
    style.textContent = GATE_CSS;
    document.head.appendChild(style);

    const gate = document.createElement('div');
    gate.id = 'ble-gate';
    gate.className = 'ble-gate';
    gate.innerHTML = `
      <div class="ble-gate-card">
        <div class="ble-gate-seal">川</div>
        <div class="ble-gate-title" data-gt="title"></div>
        <div class="ble-gate-sub" data-gt="subtitle"></div>
        <div id="ble-gate-alert" class="ble-gate-alert hidden"></div>
        <div class="ble-gate-step" data-gt="stepLang"></div>
        <div class="ble-gate-langs" id="ble-gate-langs"></div>
        <div class="ble-gate-step" data-gt="stepConnect"></div>
        <button id="ble-gate-connect" class="ble-gate-btn"></button>
        <button id="ble-gate-skip" class="ble-gate-skip" data-gt="skipBtn"></button>
        <div id="ble-gate-batt" class="ble-gate-batt hidden"></div>
        <div id="ble-gate-status" class="ble-gate-status"></div>
        <div id="ble-gate-help" class="ble-gate-help hidden">
          <div class="ble-gate-help-title"></div>
          <div class="ble-gate-help-line"></div>
          <div class="ble-gate-help-line"></div>
          <div class="ble-gate-help-cta"></div>
        </div>
        <div class="ble-gate-footer" data-gt="footer"></div>
      </div>`;
    document.body.appendChild(gate);

    state.els = {
      gate, alert: gate.querySelector('#ble-gate-alert'),
      langs: gate.querySelector('#ble-gate-langs'),
      btn: gate.querySelector('#ble-gate-connect'),
      skip: gate.querySelector('#ble-gate-skip'),
      batt: gate.querySelector('#ble-gate-batt'),
      status: gate.querySelector('#ble-gate-status'),
      help: gate.querySelector('#ble-gate-help'),
    };
    state.els.btn.addEventListener('click', manualConnect);
    // 检查阶段旁路：未到位耳机也能进入页面检查功能（上线由 CFG.skipEnabled=false 关闭）
    if (CFG.skipEnabled) state.els.skip.addEventListener('click', skipGate);
    else state.els.skip.classList.add('hidden');

    // 语言 chips
    Object.keys(LANG_LABELS).forEach((code) => {
      const chip = document.createElement('span');
      chip.className = 'ble-gate-lang';
      chip.dataset.lang = code;
      chip.textContent = LANG_LABELS[code];
      chip.addEventListener('click', () => selectLang(code));
      state.els.langs.appendChild(chip);
    });
    renderGateText();
  }

  function renderGateText() {
    document.querySelectorAll('#ble-gate [data-gt]').forEach((el) => {
      el.textContent = t(el.dataset.gt);
    });
    state.els.btn.textContent = t('connectBtn');
    state.els.langs.querySelectorAll('.ble-gate-lang').forEach((chip) => {
      chip.classList.toggle('active', chip.dataset.lang === state.lang);
    });
  }

  function selectLang(code) {
    state.lang = code;
    safeSet('app_lang', code);
    // 复用页面全局语言切换（index.html 的 setLanguage 会派发 app:langchange）
    if (typeof window.setLanguage === 'function') {
      window.setLanguage(code, LANG_LABELS[code] || code, null, true);
    } else {
      window.dispatchEvent(new CustomEvent('app:langchange', { detail: { lang: code } }));
    }
    renderGateText();
  }

  /* 蓝牙不可用引导卡：换浏览器 / 服务台求助（现场无外网，不引导下载 Chrome） */
  function showHelpCard() {
    const card = state.els.help;
    if (!card) return;
    card.classList.remove('hidden');
    card.querySelector('.ble-gate-help-title').textContent = '🎧 ' + t('helpTitle');
    const lines = card.querySelectorAll('.ble-gate-help-line');
    lines[0].textContent = t('helpL1');
    lines[1].textContent = t('helpL2');
    card.querySelector('.ble-gate-help-cta').textContent = '🏛 ' + t('footer');
  }

  function showAlert(kind, text) {
    state.els.alert.className = 'ble-gate-alert ' + kind;
    state.els.alert.textContent = text;
  }
  function clearAlert() { state.els.alert.className = 'ble-gate-alert hidden'; }
  function setStatus(text) { state.els.status.textContent = text || ''; }

  function renderBattery() {
    const el = state.els.batt;
    if (state.battery == null) { el.classList.add('hidden'); return; }
    el.classList.remove('hidden');
    el.classList.toggle('low', state.lowBatt);
    el.textContent = `🔋 ${state.battery}%`;
  }

  /* ── 锁定 / 解锁 ───────────────────────────── */
  function lock(reason, battery) {
    state.unlocked = false;
    state.els.gate.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    if (reason === 'lowBattery') showAlert('warn', t('lowBattery', battery));
    else if (reason === 'disconnected') showAlert('err', t('disconnected'));
    else clearAlert();
    renderGateText();
  }

  function unlock() {
    state.unlocked = true;
    state.els.gate.classList.add('hidden');
    document.body.style.overflow = '';
    clearAlert(); setStatus(t('connected'));
    renderBattery();
    window.dispatchEvent(new CustomEvent('ble:connected', {
      detail: { name: state.device ? state.device.name : '', battery: state.battery, lowBattery: state.lowBatt },
    }));
  }

  /* 检查阶段旁路：不派发 ble:connected（未连真实设备，各模块按未连接态自行处理） */
  function skipGate() {
    state.unlocked = false;
    state.skipped = true;
    sessionStorage.setItem('ble_gate_skipped', '1'); // 仅本标签页会话记忆：新开页面仍出准入页
    state.els.gate.classList.add('hidden');
    document.body.style.overflow = '';
  }

  /* ── BLE 连接 ──────────────────────────────── */
  async function manualConnect() {
    if (!navigator.bluetooth) { showAlert('err', t('unsupported')); showHelpCard(); return; }
    state.els.btn.disabled = true;
    setStatus(t('connecting'));
    try {
      const device = await navigator.bluetooth.requestDevice({
        filters: [{ namePrefix: CFG.namePrefix }],
        optionalServices: [CFG.svcBattery],
      });
      await setupDevice(device);
    } catch (err) {
      if (err.name !== 'NotFoundError') { // 用户取消选择器不算错误
        console.error('[ble-guard] connect failed:', err);
        setStatus(t('disconnected'));
      } else {
        setStatus('');
      }
    } finally {
      state.els.btn.disabled = false;
    }
  }

  async function setupDevice(device) {
    stopRetry();
    device.addEventListener('gattserverdisconnected', onDisconnected);
    const server = await device.gatt.connect();
    state.device = device;
    await readBattery(server);   // 尽力而为：不支持电量服务不阻塞解锁
    startPoll();
    if (state.lowBatt) showAlert('warn', t('lowBattNow', state.battery));
    else clearAlert();
    unlock();
  }

  async function readBattery(server) {
    try {
      const svc = await server.getPrimaryService(CFG.svcBattery);
      const chr = await svc.getCharacteristic(CFG.chrBattery);
      const val = await chr.readValue();
      state.battery = val.getUint8(0);
      state.lowBatt = state.battery < CFG.lowBattery;
    } catch {
      state.battery = null; state.lowBatt = false;
    }
  }

  function startPoll() {
    stopPoll();
    state.pollTimer = setInterval(async () => {
      if (!state.device || !state.device.gatt.connected) return;
      try { await readBattery(state.device.gatt); renderBattery(); } catch { /* ignore */ }
    }, CFG.pollMs);
  }
  function stopPoll() { clearInterval(state.pollTimer); state.pollTimer = null; }

  function onDisconnected() {
    stopPoll();
    // 兜底暂停页面所有 <audio>；AudioContext 由各模块监听事件自行关闭
    document.querySelectorAll('audio').forEach((a) => { try { a.pause(); } catch (e) { /* ignore */ } });
    window.dispatchEvent(new CustomEvent('ble:disconnected', {
      detail: { lowBattery: state.lowBatt, battery: state.battery },
    }));
    lock(state.lowBatt ? 'lowBattery' : 'disconnected', state.battery);
    scheduleRetry(); // 耳机回到范围内自动恢复
  }

  function scheduleRetry() {
    stopRetry();
    state.retryTimer = setInterval(async () => {
      if (!state.device || state.device.gatt.connected) return;
      try {
        const server = await state.device.gatt.connect();
        await readBattery(server);
        startPoll();
        unlock();
        stopRetry();
      } catch (e) { /* 未回到范围：继续等 */ }
    }, CFG.retryMs);
  }
  function stopRetry() { clearInterval(state.retryTimer); state.retryTimer = null; }

  /* ── 初始化 ────────────────────────────────── */
  async function init() {
    // 开发旁路：?demo=1（生产环境请勿传播）
    if (DEMO_BYPASS) return;

    buildGate();
    // 检查阶段：本标签页内已跳过则不再重复出准入页（新开页面仍会出）
    if (sessionStorage.getItem('ble_gate_skipped') === '1') {
      state.skipped = true;
      state.els.gate.classList.add('hidden');
      return;
    }
    lock('initial');

    // 语言跟随全局切换（index 顶部下拉 → gate 文案同步）
    window.addEventListener('app:langchange', (ev) => {
      const lang = (ev.detail && ev.detail.lang || 'zh').slice(0, 2);
      if (I18N[lang]) { state.lang = lang; renderGateText(); }
    });

    // 曾连接过的设备：静默自动重连（Chrome getDevices），失败则等待手动连接
    if (navigator.bluetooth && navigator.bluetooth.getDevices) {
      try {
        const devices = await navigator.bluetooth.getDevices();
        const mine = devices.find((d) => (d.name || '').startsWith(CFG.namePrefix));
        if (mine) {
          try { await setupDevice(mine); } catch (e) { /* 静默：留在准入页 */ }
        }
      } catch (e) { /* 浏览器不支持：忽略 */ }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.BleGuard = { lock, unlock, get connected() { return state.unlocked; } };
})();
