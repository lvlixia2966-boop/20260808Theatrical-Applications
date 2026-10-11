/* ============================================================
 * creator-hub.js — 众创平台 9 大次级页面交互模块
 *
 * 模块划分（高内聚低耦合，每个页面前缀独立）：
 *   1. 川剧剧本杀   jbs_*  可玩一局：选剧本 → 搜证 → 指认 → 结算
 *   2. 数字化修复   rst_*  前后对比滑块 + 任务认领
 *   3. 川剧智库     zk_*   搜索 + 分类筛选 + 词条详情
 *   4. Skills 库    sk_*   技艺课程库：分类 / 课时 / 学习进度
 *   5. 数字资产库   ca_*   共创素材：筛选 / 预览 / 收藏
 *   6. 3DGS 预览    gs_*   Canvas 点云查看器：旋转 / 缩放 / 密度
 *   7. 虚实轻剧     qj_*   互动剧情：打字机 / 分支 / 多结局收集
 *   8. 创意工坊     ws_*   多 Agent 流水线运行演示
 *   9. 智能体矩阵   am_*   Agent 配置面板 + 能力矩阵
 *
 * 依赖（来自 index.html 全局）：showToast / lucide.createIcons
 * 入口钩子：index.html 的 openCreatorSub() 会回调 window.onCreatorSubEnter(id)
 * ============================================================ */

'use strict';

/* ---------- 公共小工具 ---------- */
function chIcons() {
  if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
}

/* ============================================================
 * 1. 川剧剧本杀 jbs_*
 * ============================================================ */
const JBS_DATA = {
  playable: {
    id: 'golden-mask',
    title: '戏台迷云 · 失踪的金脸谱',
    desc: '金脸谱在开演前夜离奇失踪，戏班四人人人可疑。搜证推理，指认真凶！',
    players: '1 人 · 15 分钟 · 简单',
    story: '1947 年，成都三庆会戏班。明日就是班主寿辰大戏《白蛇传》，压箱底的祖传金脸谱却在开演前夜不翼而飞。你是刚入班三天的新学徒，班主命你彻查此事。后台四人都说自己是清白的……',
    suspects: [
      { id: 'wusheng', name: '武生 · 赵擎天', note: '当日压轴主演，自称一早去城隍庙还愿' },
      { id: 'huadan', name: '花旦 · 苏月影', note: '失眠多日，茶杯里常年泡着安神药' },
      { id: 'jing', name: '净角 · 常胜', note: '自称整晚在练功房练嗓，无人可证' },
      { id: 'chou', name: '丑角 · 孙小豆', note: '班里的开心果，人缘极好，负责后台杂务' }
    ],
    clues: [
      { id: 1, title: '被撬开的窗户', text: '后台窗户有人从外撬开的痕迹——但窗台积灰上只有班内人的鞋印。', tag: '现场' },
      { id: 2, title: '鞋底的金粉', text: '孙小豆的靴底沾着新鲜金粉，与金脸谱上的敷金工艺一致。', tag: '物证' },
      { id: 3, title: '安神药渣', text: '苏月影的茶杯里泡着安神药渣——她确实常年失眠，此事人尽皆知。', tag: '干扰' },
      { id: 4, title: '没亮过的练功房', text: '看门老人说练功房当晚根本没开灯，常胜的"练嗓"是谎言。', tag: '证词' },
      { id: 5, title: '检修灯的生人', text: '有人以"检修灯光"名义进过后台——可灯光师说并无此事，是内应放行。', tag: '现场' },
      { id: 6, title: '戏箱夹层的拓片', text: '孙小豆戏箱夹层里藏着一张金脸谱拓片，墨迹还是新的。', tag: '实锤' }
    ],
    truth: 'chou',
    truthText: '丑角孙小豆被古玩商收买，借"检修灯光"之名支开旁人，用拓片调包了金脸谱，原物藏在戏箱夹层准备连夜带出。常胜说谎只是因为私下去见嗓医怕被班主责罚，苏月影的安神药纯属无辜。'
  },
  comingSoon: [
    { title: '白蛇外传 · 断桥疑云', desc: '水漫金山之后，断桥之上另起迷云（多人本，敬请期待）' },
    { title: '变脸师的最后一张脸', desc: '绝技传人离奇失忆，硬核推理（烧脑本，敬请期待）' }
  ]
};
let jbsRevealed = new Set();
let jbsState = 'lobby'; // lobby | game | result

function jbsInit() {
  jbsRenderLobby();
}
function jbsRenderLobby() {
  jbsState = 'lobby';
  jbsRevealed = new Set();
  const lobby = document.getElementById('jbs-lobby');
  const game = document.getElementById('jbs-game');
  const result = document.getElementById('jbs-result');
  if (!lobby) return;
  lobby.classList.remove('hidden');
  game.classList.add('hidden');
  result.classList.add('hidden');
  lobby.innerHTML = `
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div class="bg-white rounded-2xl border border-[#8B0000]/20 shadow-sm overflow-hidden hover:shadow-md transition-all">
        <div class="h-28 bg-gradient-to-r from-[#8B0000] to-[#C19A6B] flex items-center justify-center text-5xl">🎭</div>
        <div class="p-4 space-y-2">
          <div class="flex items-center justify-between">
            <h5 class="font-bold text-foreground">${JBS_DATA.playable.title}</h5>
            <span class="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 text-[11px] font-bold rounded-full">可玩</span>
          </div>
          <p class="text-xs text-muted-foreground">${JBS_DATA.playable.desc}</p>
          <p class="text-[11px] text-[#C19A6B] font-bold">${JBS_DATA.playable.players}</p>
          <button onclick="jbsStartGame()" class="w-full py-2.5 bg-[#8B0000] text-white font-bold text-xs rounded-xl hover:bg-[#a00000] transition-all">开始游戏</button>
        </div>
      </div>
      <div class="space-y-3">
        ${JBS_DATA.comingSoon.map(s => `
          <div class="bg-secondary/30 rounded-2xl border border-border/60 p-4 flex items-center gap-3">
            <div class="w-11 h-11 rounded-2xl bg-[#C19A6B]/20 flex items-center justify-center text-xl flex-shrink-0">📜</div>
            <div class="flex-1 min-w-0">
              <h5 class="font-bold text-sm text-foreground">${s.title}</h5>
              <p class="text-[11px] text-muted-foreground truncate">${s.desc}</p>
            </div>
            <span class="px-2 py-1 bg-gray-200 text-gray-500 text-[11px] font-bold rounded-full flex-shrink-0">即将上线</span>
          </div>
        `).join('')}
        <div class="bg-[#8B0000]/5 border border-[#8B0000]/10 rounded-2xl p-4">
          <h5 class="font-bold text-xs text-[#8B0000] mb-1.5">玩法说明</h5>
          <p class="text-[11px] text-muted-foreground leading-relaxed">阅读案情 → 点击线索卡搜证（至少解锁 4 条）→ 指认嫌疑人 → 查看真相结算。注意：有干扰线索！</p>
        </div>
      </div>
    </div>
  `;
  chIcons();
}
function jbsStartGame() {
  jbsState = 'game';
  jbsRevealed = new Set();
  document.getElementById('jbs-lobby').classList.add('hidden');
  document.getElementById('jbs-result').classList.add('hidden');
  const game = document.getElementById('jbs-game');
  game.classList.remove('hidden');
  document.getElementById('jbs-story').innerHTML = `
    <div class="flex items-start gap-3">
      <span class="w-9 h-9 rounded-xl bg-[#8B0000] text-white flex items-center justify-center flex-shrink-0"><i data-lucide="scroll-text" class="w-5 h-5"></i></span>
      <div>
        <h4 class="font-bold text-foreground mb-1">案情背景</h4>
        <p class="text-sm text-muted-foreground leading-relaxed">${JBS_DATA.playable.story}</p>
      </div>
    </div>
  `;
  jbsRenderClues();
  jbsRenderVote();
  chIcons();
}
function jbsRenderClues() {
  const box = document.getElementById('jbs-clues');
  box.innerHTML = `
    <div class="flex items-center justify-between mb-2">
      <h4 class="font-bold text-foreground flex items-center gap-2 text-sm">
        <i data-lucide="search" class="w-4 h-4 text-[#8B0000]"></i> 现场搜证
        <span id="jbs-count" class="text-[11px] text-muted-foreground font-normal">已解锁 ${jbsRevealed.size} / 6</span>
      </h4>
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
      ${JBS_DATA.playable.clues.map(c => {
        const open = jbsRevealed.has(c.id);
        return `
        <div onclick="jbsReveal(${c.id})" class="rounded-2xl border p-3.5 cursor-pointer transition-all ${open ? 'bg-[#8B0000]/5 border-[#8B0000]/30' : 'bg-white border-border/60 hover:border-[#8B0000]/40 hover:shadow-sm'}">
          ${open ? `
            <div class="text-[11px] font-bold text-[#8B0000] mb-1">${c.tag} · 线索 ${c.id}</div>
            <div class="font-bold text-xs text-foreground mb-1">${c.title}</div>
            <p class="text-[11px] text-muted-foreground leading-relaxed">${c.text}</p>
          ` : `
            <div class="h-full flex flex-col items-center justify-center gap-1.5 py-2 text-muted-foreground">
              <i data-lucide="lock" class="w-5 h-5"></i>
              <span class="text-[11px] font-bold">线索 ${c.id} · 点击解锁</span>
            </div>
          `}
        </div>`;
      }).join('')}
    </div>
  `;
  chIcons();
}
function jbsReveal(id) {
  if (jbsState !== 'game') return;
  jbsRevealed.add(id);
  showToast('🔓 解锁线索');
  jbsRenderClues();
  jbsRenderVote();
}
function jbsRenderVote() {
  const box = document.getElementById('jbs-vote');
  const enough = jbsRevealed.size >= 4;
  box.innerHTML = `
    <div class="bg-white rounded-2xl border border-border/60 p-4 space-y-3">
      <h4 class="font-bold text-foreground flex items-center gap-2 text-sm">
        <i data-lucide="user-search" class="w-4 h-4 text-[#8B0000]"></i> 指认真凶
        ${enough ? '' : '<span class="text-[11px] text-red-500 font-normal">（还需解锁 ' + (4 - jbsRevealed.size) + ' 条线索）</span>'}
      </h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        ${JBS_DATA.playable.suspects.map(s => `
          <button ${enough ? '' : 'disabled'} onclick="jbsAccuse('${s.id}')" class="text-left p-3 rounded-xl border transition-all ${enough ? 'border-border/60 hover:border-[#8B0000] hover:bg-[#8B0000]/5 active:scale-[0.98]' : 'border-border/40 opacity-50 cursor-not-allowed'}">
            <div class="font-bold text-xs text-foreground">${s.name}</div>
            <div class="text-[11px] text-muted-foreground mt-0.5">${s.note}</div>
          </button>
        `).join('')}
      </div>
    </div>
  `;
  chIcons();
}
function jbsAccuse(id) {
  if (jbsState !== 'game') return;
  jbsState = 'result';
  const correct = id === JBS_DATA.playable.truth;
  const suspect = JBS_DATA.playable.suspects.find(s => s.id === id);
  const rate = correct ? (jbsRevealed.size >= 6 ? 'S 级 · 神探学徒' : 'A 级 · 明察秋毫') : 'B 级 · 再接再厉';
  const result = document.getElementById('jbs-result');
  document.getElementById('jbs-game').classList.add('hidden');
  result.classList.remove('hidden');
  result.innerHTML = `
    <div class="text-center space-y-4 py-6">
      <div class="w-20 h-20 mx-auto rounded-full flex items-center justify-center text-4xl shadow-md ${correct ? 'bg-emerald-500/10' : 'bg-red-500/10'}">
        ${correct ? '🎯' : '❌'}
      </div>
      <div>
        <h4 class="font-display text-2xl font-bold ${correct ? 'text-emerald-600' : 'text-red-500'}">${correct ? '指认正确！' : '指认失误…'}</h4>
        <p class="text-sm text-muted-foreground mt-1">你指认的是 ${suspect.name}，真凶是 <span class="font-bold text-[#8B0000]">丑角 · 孙小豆</span></p>
      </div>
      <div class="max-w-lg mx-auto bg-[#8B0000]/5 border border-[#8B0000]/10 rounded-2xl p-4 text-left">
        <h5 class="font-bold text-xs text-[#8B0000] mb-1.5">真相还原</h5>
        <p class="text-xs text-muted-foreground leading-relaxed">${JBS_DATA.playable.truthText}</p>
      </div>
      <div class="flex items-center justify-center gap-3 text-xs text-muted-foreground">
        <span>线索利用 ${jbsRevealed.size} / 6</span><span>·</span>
        <span class="font-bold text-[#8B0000]">${rate}</span>
      </div>
      <div class="flex justify-center gap-2 pt-1">
        <button onclick="jbsStartGame()" class="px-6 py-2.5 bg-[#8B0000] text-white font-bold rounded-xl hover:bg-[#a00000] transition-all">再玩一次</button>
        <button onclick="jbsRenderLobby()" class="px-6 py-2.5 bg-secondary/60 text-[#8B0000] font-bold rounded-xl hover:bg-secondary transition-all">返回剧本大厅</button>
      </div>
    </div>
  `;
  showToast(correct ? '🎉 指认正确，获得神探徽章' : '😂 真凶另有其人');
}

/* ============================================================
 * 2. 数字化修复 rst_*
 * ============================================================ */
const RST_COMPARES = [
  { name: '红脸关羽', before: './assets/mask-red-orig.png', after: './assets/mask-red-ai.jpg' },
  { name: '金脸龙王', before: './assets/mask-gold-orig.png', after: './assets/mask-gold-ai.jpg' },
  { name: '蓝脸豪杰', before: './assets/mask-blue-orig.png', after: './assets/mask-blue-ai.jpg' }
];
let rstCompareIdx = 0;
let rstStats = { pending: 47, done: 312, contributors: 892 };
const RST_TASKS = [
  { id: 1, type: '老照片', color: 'bg-amber-500/10 text-amber-600', title: '1958 年《秋江》剧照 · 褪色与折痕修复', diff: '中等', points: 20, status: 'open' },
  { id: 2, type: '老唱片', color: 'bg-teal-500/10 text-teal-600', title: '1962 年高腔《拷红》蜡盘唱片 · 噪声剥离', diff: '困难', points: 40, status: 'open' },
  { id: 3, type: '戏服纹样', color: 'bg-primary/10 text-primary', title: '蜀绣蟒袍纹样扫描件 · 破损补全', diff: '中等', points: 25, status: 'open' },
  { id: 4, type: '手抄剧本', color: 'bg-blue-500/10 text-blue-600', title: '清末手抄工尺谱 · 字迹增强与转录', diff: '简单', points: 10, status: 'open' }
];

function rstInit() {
  rstRenderStats();
  rstRenderTabs();
  rstBindSlider();
  rstRenderTasks();
  chIcons();
}
function rstRenderStats() {
  document.getElementById('rst-stats').innerHTML = `
    <div class="bg-secondary/40 rounded-xl p-4"><div class="text-xl font-bold text-[#8B0000]">${rstStats.pending}</div><div class="text-[11px] text-muted-foreground tracking-widest mt-1">待修复任务</div></div>
    <div class="bg-secondary/40 rounded-xl p-4"><div class="text-xl font-bold text-emerald-600">${rstStats.done}</div><div class="text-[11px] text-muted-foreground tracking-widest mt-1">已完成</div></div>
    <div class="bg-secondary/40 rounded-xl p-4"><div class="text-xl font-bold text-[#C19A6B]">${rstStats.contributors}</div><div class="text-[11px] text-muted-foreground tracking-widest mt-1">贡献者</div></div>
  `;
}
function rstRenderTabs() {
  document.getElementById('rst-compare-tabs').innerHTML = RST_COMPARES.map((c, i) => `
    <button onclick="rstSwitchCompare(${i})" class="px-3 py-1.5 text-xs font-bold rounded-full transition-all ${i === rstCompareIdx ? 'bg-[#8B0000] text-white shadow-sm' : 'bg-secondary/50 border border-border text-foreground hover:bg-secondary'}">${caT(c.id)}</button>
  `).join('');
}
function rstSwitchCompare(i) {
  rstCompareIdx = i;
  const c = RST_COMPARES[i];
  document.getElementById('rst-img-before').src = c.before;
  document.getElementById('rst-img-after').src = c.after;
  rstRenderTabs();
  rstSyncBeforeWidth();
  showToast('已切换对比资产：' + c.name);
}
function rstSyncBeforeWidth() {
  const box = document.getElementById('rst-compare-box');
  const img = document.getElementById('rst-img-before');
  if (box && img) img.style.width = box.clientWidth + 'px';
}
function rstBindSlider() {
  const box = document.getElementById('rst-compare-box');
  const divider = document.getElementById('rst-divider');
  const wrap = document.getElementById('rst-before-wrap');
  if (!box || !divider || divider.dataset.bound) return;
  divider.dataset.bound = '1';
  let dragging = false;
  const setPos = (clientX) => {
    const rect = box.getBoundingClientRect();
    let pct = ((clientX - rect.left) / rect.width) * 100;
    pct = Math.max(2, Math.min(98, pct));
    divider.style.left = pct + '%';
    wrap.style.width = pct + '%';
  };
  // 点击任意位置跳转 + 按住拖动
  box.addEventListener('mousedown', e => { dragging = true; setPos(e.clientX); });
  document.addEventListener('mousemove', e => { if (dragging) setPos(e.clientX); });
  document.addEventListener('mouseup', () => { dragging = false; });
  box.addEventListener('touchstart', e => { dragging = true; setPos(e.touches[0].clientX); }, { passive: true });
  document.addEventListener('touchmove', e => { if (dragging) setPos(e.touches[0].clientX); }, { passive: true });
  document.addEventListener('touchend', () => { dragging = false; });
  window.addEventListener('resize', rstSyncBeforeWidth);
  rstSyncBeforeWidth();
}
function rstRenderTasks() {
  document.getElementById('rst-tasks').innerHTML = RST_TASKS.map(t => `
    <div class="bg-white rounded-2xl border border-border/60 p-4 flex flex-col sm:flex-row sm:items-center gap-3">
      <span class="px-2 py-1 ${t.color} text-[11px] font-bold rounded-full flex-shrink-0 w-fit">${t.type}</span>
      <div class="flex-1 min-w-0">
        <div class="font-bold text-xs text-foreground">${t.title}</div>
        <div class="text-[11px] text-muted-foreground mt-0.5">难度 ${t.diff} · 贡献点 +${t.points}</div>
        ${t.status === 'progress' ? '<div class="h-1.5 bg-secondary/60 rounded-full overflow-hidden mt-2"><div class="h-full bg-[#8B0000] rounded-full transition-all duration-300 rst-progress" style="width:8%"></div></div>' : ''}
      </div>
      ${t.status === 'open' ? `
        <button onclick="rstClaim(${t.id})" class="px-4 py-2 bg-[#8B0000] text-white font-bold text-xs rounded-xl hover:bg-[#a00000] transition-all flex-shrink-0">认领修复</button>
      ` : t.status === 'progress' ? `
        <span class="px-4 py-2 bg-[#8B0000]/10 text-[#8B0000] font-bold text-xs rounded-xl flex-shrink-0">AI 预修复中…</span>
      ` : `
        <span class="px-4 py-2 bg-emerald-500/10 text-emerald-600 font-bold text-xs rounded-xl flex items-center gap-1 flex-shrink-0"><i data-lucide="check" class="w-3.5 h-3.5"></i> 已完成</span>
      `}
    </div>
  `).join('');
  chIcons();
}
function rstClaim(id) {
  const task = RST_TASKS.find(t => t.id === id);
  if (!task || task.status !== 'open') return;
  task.status = 'progress';
  rstRenderTasks();
  showToast('🛠️ 已认领「' + task.type + '」任务，AI 预修复启动');
  // 模拟 AI 预修复进度
  const card = document.querySelector('.rst-progress');
  let p = 8;
  const timer = setInterval(() => {
    p += 22 + Math.random() * 18;
    const bar = document.querySelector('.rst-progress');
    if (bar) bar.style.width = Math.min(p, 100) + '%';
    if (p >= 100) {
      clearInterval(timer);
      task.status = 'done';
      rstStats.pending = Math.max(0, rstStats.pending - 1);
      rstStats.done += 1;
      rstStats.contributors += 1;
      rstRenderStats();
      rstRenderTasks();
      showToast('✅ 修复完成，贡献点 +' + task.points);
    }
  }, 420);
}

/* ============================================================
 * 3. 川剧智库 zk_*
 * ============================================================ */
const ZK_CATS = [
  { id: 'all', name: '全部' }, { id: 'repertoire', name: '剧目' }, { id: 'master', name: '名家' },
  { id: 'role', name: '行当' }, { id: 'voice', name: '声腔' }, { id: 'history', name: '史话' }
];
const ZK_ENTRIES = [
  { id: 1, cat: 'repertoire', title: '《白蛇传》', summary: '川剧看家大戏，水漫金山气势磅礴，青儿"变脸"别开一格。', reads: '2.3w',
    detail: ['《白蛇传》是川剧最具代表性的传统大戏之一，"水漫金山"一场以群战、武打与紫金饶钹等特技著称，场面恢弘。', '川剧版的独特之处在于青儿这一角色：从初期的温柔侍女到后期的刚烈战斗，演员通过"变脸"绝活完成情绪与身份的转换，成为全剧最亮眼的一笔。', '断桥一折则细腻婉转，白素贞与许仙的对手戏唱做并重，是青衣行当的试金石。'] },
  { id: 2, cat: 'repertoire', title: '《秋江》', summary: '折子戏经典：陈妙常江上追赶潘必正，艄翁插科打诨妙趣横生。', reads: '1.8w',
    detail: ['《秋江》出自《玉簪记》，讲陈妙常雇舟追赶情人潘必正的故事。全戏无水无船，全凭演员的身段与桨法在空台上"划"出一条大江。', '艄翁是川剧丑行的教科书级角色，风趣诙谐又不失善良，与陈妙常一急一缓，构成绝妙的喜剧节奏。', '此戏久演不衰，被誉为"以虚拟实、以简驭繁"的戏曲美学典范。'] },
  { id: 3, cat: 'repertoire', title: '《滚灯》', summary: '丑角绝活戏：皮金头顶油灯，钻板凳、翻跟头，灯不灭人不歇。', reads: '1.5w',
    detail: ['《滚灯》是川剧丑角功夫戏的代表，讲赌徒皮金被妻子惩罚，头顶点燃的油灯做各种高难度动作。', '顶灯、钻凳、倒立行走等技巧一气呵成，油灯始终不灭，考验演员的脖颈功、腰功与平衡能力。', '该戏与变脸、吐火并称川剧三大绝活，常作为压轴节目亮相。'] },
  { id: 4, cat: 'repertoire', title: '《拷红》', summary: '红娘机智应对老夫人的经典折子，唱念并重，机趣盎然。', reads: '9.6k',
    detail: ['《拷红》出自《西厢记》，聚焦红娘被崔老夫人拷问一场，以连珠炮式的念白与俏皮的唱段塑造了一个侠肝义胆的丫鬟形象。', '川剧处理此戏节奏明快，红娘的"辩"层层递进，最终反将老夫人一军，喜剧效果极佳。'] },
  { id: 5, cat: 'master', title: '陈智林', summary: '川剧表演艺术家，工文武小生，领衔《巴山秀才》等新编名剧。', reads: '1.2w',
    detail: ['陈智林是当代川剧领军人物之一，工文武小生，唱腔高亢醇厚，身段潇洒大方。', '他领衔主演的《巴山秀才》《易胆大》等剧目广受好评，多次斩获国家级奖项，并长期致力于川剧的传承与推广。'] },
  { id: 6, cat: 'master', title: '沈铁梅', summary: '川剧表演艺术家，三度摘梅，代表作《金子》享誉海内外。', reads: '1.6w',
    detail: ['沈铁梅被誉为"川剧声腔女状元"，嗓音甜美圆润，将川剧旦角声腔艺术推向新高度。', '其代表作《金子》改编自《原野》，曾赴多国巡演，让世界听见川剧高腔的魅力。'] },
  { id: 7, cat: 'master', title: '阳友鹤', summary: '川剧旦角一代宗师，人称"阳倒槽"，桃李满天下。', reads: '8.8k',
    detail: ['阳友鹤是二十世纪川剧旦角艺术的集大成者，唱念做打无一不精，尤擅刻画不同年龄、身份的女性形象。', '他晚年致力于教学与整理传统表演程式，为川剧留下了系统的旦角功法体系。'] },
  { id: 8, cat: 'master', title: '魏明伦', summary: '"巴山鬼才"，剧作家，《潘金莲》《变脸》等剧震动剧坛。', reads: '1.1w',
    detail: ['魏明伦以荒诞川剧《潘金莲》名动全国，其剧作思辨锋利、结构奇巧，被称为"巴山鬼才"。', '《变脸》《中国公主杜兰朵》等作品在全国范围产生深远影响，为传统戏曲的现代转型提供了样本。'] },
  { id: 9, cat: 'role', title: '生旦净丑 · 四大行当', summary: '小生儒雅、旦角婉媚、净角雄浑、丑角机趣，行当分明各展其长。', reads: '1.4w',
    detail: ['川剧行当划分细密：生行分小生、须生、正生等；旦行分闺门旦、花旦、刀马旦、老旦等；净行俗称"花脸"，以脸谱区分人物品性；丑行则"无丑不成戏"，机趣灵活。', '各行业有独门功法，如小生的褶子功、旦角的水袖与指法、净角的架子与脸谱勾画、丑角的矮子功等，共同构成川剧表演的庞大体系。'] },
  { id: 10, cat: 'voice', title: '五种声腔 · 昆高胡弹灯', summary: '昆腔、高腔、胡琴、弹戏、灯调五腔共和，成就川剧海纳百川。', reads: '1.9w',
    detail: ['川剧并非单一声腔，而是清代以来昆腔、高腔、胡琴、弹戏与四川本土灯调五大声腔在川地融合的结晶。', '高腔是川剧之魂：帮、打、唱三者结合，一人启齿、众人帮腔，不加管弦、徒歌干唱，激越苍凉。', '灯调源于民间歌舞，活泼明快，多用于小戏；胡琴、弹戏分别从皮黄、梆子演化而来，各有经典剧目。'] },
  { id: 11, cat: 'history', title: '川剧的形成', summary: '明清移民入川，诸腔竞奏，最终"五腔合一"自成一派。', reads: '1.3w',
    detail: ['明末清初"湖广填四川"的移民浪潮，把昆腔、梆子、皮黄等声腔带进巴蜀，与本地灯戏俗曲长期共存、彼此吸收。', '至清代中后期，以成都、重庆为中心逐渐形成统一的艺术风格，川剧之名得以确立，成为西南地区影响最大的剧种。'] },
  { id: 12, cat: 'history', title: '三庆会 · 戏班传奇', summary: '1912 年成都成立的著名戏班，名家荟萃，被誉为"戏圣"摇篮。', reads: '7.9k',
    detail: ['三庆会由康子林、杨素兰等人于 1912 年在成都创建，集结当时川剧界精英，实行班主任制与艺人共议，开风气之先。', '康子林与"戏圣"康广隶等名家在此传艺授徒，三庆会数十年间成为川剧人才与剧目的高地，深刻影响了二十世纪川剧的走向。'] }
];
let zkCat = 'all';
let zkKeyword = '';

function zkInit() {
  zkRenderCats();
  zkRenderGrid();
}
function zkRenderCats() {
  document.getElementById('zk-cats').innerHTML = ZK_CATS.map(c => `
    <button onclick="zkSetCat('${c.id}')" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex-shrink-0 ${c.id === zkCat ? 'bg-teal-600 text-white shadow-sm' : 'bg-secondary/50 border border-border text-foreground hover:bg-secondary'}">${caT(c.id)}</button>
  `).join('');
}
function zkSetCat(cat) {
  zkCat = cat;
  document.getElementById('zk-detail').classList.add('hidden');
  document.getElementById('zk-grid').classList.remove('hidden');
  zkRenderCats();
  zkRenderGrid();
}
function zkSearch() {
  zkKeyword = (document.getElementById('zk-search').value || '').trim().toLowerCase();
  document.getElementById('zk-detail').classList.add('hidden');
  document.getElementById('zk-grid').classList.remove('hidden');
  zkRenderGrid();
}
function zkFiltered() {
  return ZK_ENTRIES.filter(e => {
    const okCat = zkCat === 'all' || e.cat === zkCat;
    const okKw = !zkKeyword || (e.title + e.summary + e.detail.join('')).toLowerCase().includes(zkKeyword);
    return okCat && okKw;
  });
}
function zkRenderGrid() {
  const list = zkFiltered();
  const catName = id => (ZK_CATS.find(c => c.id === id) || {}).name || id;
  const grid = document.getElementById('zk-grid');
  if (!list.length) {
    grid.innerHTML = '<div class="col-span-full text-center py-10 text-sm text-muted-foreground">没有找到相关词条，换个关键词试试</div>';
    return;
  }
  grid.innerHTML = list.map(e => `
    <div onclick="zkOpen(${e.id})" class="bg-white rounded-2xl border border-border/60 p-4 cursor-pointer hover:border-teal-500/50 hover:shadow-md transition-all active:scale-[0.98] space-y-2">
      <div class="flex items-center justify-between">
        <span class="px-2 py-0.5 bg-teal-500/10 text-teal-700 text-[11px] font-bold rounded-full">${catName(e.cat)}</span>
        <span class="text-[11px] text-muted-foreground">📖 ${e.reads}</span>
      </div>
      <h5 class="font-bold text-sm text-foreground">${e.title}</h5>
      <p class="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">${e.summary}</p>
    </div>
  `).join('');
}
function zkOpen(id) {
  const e = ZK_ENTRIES.find(x => x.id === id);
  if (!e) return;
  const catName = (ZK_CATS.find(c => c.id === e.cat) || {}).name;
  const related = ZK_ENTRIES.filter(x => x.cat === e.cat && x.id !== e.id).slice(0, 2);
  const grid = document.getElementById('zk-grid');
  const detail = document.getElementById('zk-detail');
  grid.classList.add('hidden');
  detail.classList.remove('hidden');
  detail.innerHTML = `
    <div class="bg-white rounded-2xl border border-border/60 p-5 sm:p-6 space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <span class="px-2 py-0.5 bg-teal-500/10 text-teal-700 text-[11px] font-bold rounded-full">${catName}</span>
          <h4 class="font-display text-lg font-bold text-foreground">${e.title}</h4>
        </div>
        <button onclick="zkBack()" class="px-3 py-1.5 bg-secondary/50 border border-border rounded-xl text-xs font-bold text-foreground hover:bg-secondary transition-all">返回列表</button>
      </div>
      <p class="text-sm font-bold text-[#C19A6B]">${e.summary}</p>
      ${e.detail.map(p => `<p class="text-sm text-muted-foreground leading-relaxed">${p}</p>`).join('')}
      ${related.length ? `
      <div class="pt-2 border-t border-border/60">
        <div class="text-[11px] text-muted-foreground mb-1.5">相关词条</div>
        <div class="flex flex-wrap gap-2">
          ${related.map(r => `<button onclick="zkOpen(${r.id})" class="px-3 py-1.5 bg-teal-500/5 border border-teal-500/20 text-teal-700 text-xs font-bold rounded-full hover:bg-teal-500/10">${r.title}</button>`).join('')}
        </div>
      </div>` : ''}
      <div class="flex gap-2 pt-1">
        <button onclick="showToast('✍️ 已提交词条补充申请，感谢共创')" class="px-4 py-2 bg-[#8B0000] text-white text-xs font-bold rounded-xl hover:bg-[#a00000] transition-all">补充词条</button>
        <button onclick="showToast('🔗 链接已复制')" class="px-4 py-2 bg-secondary/50 border border-border text-foreground text-xs font-bold rounded-xl hover:bg-secondary transition-all">分享</button>
      </div>
    </div>
  `;
  window.scrollTo({ top: document.getElementById('subview-zhiku').offsetTop - 120, behavior: 'smooth' });
}
function zkBack() {
  document.getElementById('zk-detail').classList.add('hidden');
  document.getElementById('zk-grid').classList.remove('hidden');
}

/* ============================================================
 * 4. Skills 库 sk_*
 * ============================================================ */
const SK_CATS = [
  { id: 'all', name: '全部' }, { id: 'sing', name: '唱腔' }, { id: 'speech', name: '念白' },
  { id: 'move', name: '身段' }, { id: 'combat', name: '武打' }, { id: 'stunt', name: '绝活' }
];
const SK_COURSES = [
  { id: 1, cat: 'sing', title: '高腔"帮打唱"入门', teacher: '高腔名家 · 周老师', diff: '入门', lessons: 8, done: 3, cover: '🎤' },
  { id: 2, cat: 'sing', title: '胡琴腔韵味技法', teacher: '琴师 · 何老师', diff: '进阶', lessons: 10, done: 0, cover: '🎻' },
  { id: 3, cat: 'speech', title: '川剧念白与韵律', teacher: '名丑传人 · 刘老师', diff: '入门', lessons: 6, done: 0, cover: '🗣️' },
  { id: 4, cat: 'move', title: '旦角水袖十式', teacher: '青衣名家 · 苏老师', diff: '进阶', lessons: 12, done: 5, cover: '🌸' },
  { id: 5, cat: 'move', title: '生角台步与圆场', teacher: '武生 · 赵老师', diff: '入门', lessons: 8, done: 0, cover: '👣' },
  { id: 6, cat: 'move', title: '折扇功 · 开合翻转', teacher: '小生 · 李老师', diff: '进阶', lessons: 9, done: 0, cover: '🪭' },
  { id: 7, cat: 'combat', title: '短打把子功', teacher: '武行教师 · 郑老师', diff: '进阶', lessons: 14, done: 0, cover: '⚔️' },
  { id: 8, cat: 'stunt', title: '变脸基础 · 回脸三法', teacher: '变脸传人 · 佚名', diff: '大师', lessons: 18, done: 0, cover: '🎭' },
  { id: 9, cat: 'stunt', title: '顶灯平衡训练', teacher: '丑角名家 · 孙老师', diff: '大师', lessons: 12, done: 0, cover: '💡' }
];
let skCat = 'all';

function skInit() {
  skRenderCats();
  skRenderGrid();
}
function skRenderCats() {
  document.getElementById('sk-cats').innerHTML = SK_CATS.map(c => `
    <button onclick="skSetCat('${c.id}')" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex-shrink-0 ${c.id === skCat ? 'bg-blue-600 text-white shadow-sm' : 'bg-secondary/50 border border-border text-foreground hover:bg-secondary'}">${caT(c.id)}</button>
  `).join('');
}
function skSetCat(cat) {
  skCat = cat;
  document.getElementById('sk-detail').classList.add('hidden');
  skRenderCats();
  skRenderGrid();
}
const skDiffColor = d => d === '入门' ? 'bg-emerald-500/10 text-emerald-600' : d === '进阶' ? 'bg-amber-500/10 text-amber-600' : 'bg-red-500/10 text-red-600';
function skRenderGrid() {
  const list = SK_COURSES.filter(c => skCat === 'all' || c.cat === skCat);
  document.getElementById('sk-grid').innerHTML = list.map(c => {
    const pct = Math.round(c.done / c.lessons * 100);
    return `
    <div onclick="skOpen(${c.id})" class="bg-white rounded-2xl border border-border/60 p-4 cursor-pointer hover:border-blue-500/50 hover:shadow-md transition-all active:scale-[0.98] space-y-3">
      <div class="flex items-start justify-between">
        <div class="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center text-2xl">${c.cover}</div>
        <span class="px-2 py-0.5 ${skDiffColor(c.diff)} text-[11px] font-bold rounded-full">${c.diff}</span>
      </div>
      <div>
        <h5 class="font-bold text-sm text-foreground">${c.title}</h5>
        <p class="text-[11px] text-muted-foreground mt-0.5">${c.teacher} · ${c.lessons} 课时</p>
      </div>
      <div>
        <div class="flex justify-between text-[11px] text-muted-foreground mb-1">
          <span>${c.done > 0 ? '已学 ' + c.done + ' 课时' : '未开始'}</span><span>${pct}%</span>
        </div>
        <div class="h-1.5 bg-secondary/60 rounded-full overflow-hidden">
          <div class="h-full bg-blue-600 rounded-full transition-all duration-500" style="width:${pct}%"></div>
        </div>
      </div>
    </div>
  `;}).join('');
}
function skOpen(id) {
  const c = SK_COURSES.find(x => x.id === id);
  if (!c) return;
  const lessons = Array.from({ length: c.lessons }, (_, i) => i < c.done);
  const detail = document.getElementById('sk-detail');
  detail.classList.remove('hidden');
  detail.innerHTML = `
    <div class="bg-white rounded-2xl border border-border/60 p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center text-2xl">${c.cover}</div>
          <div>
            <h4 class="font-bold text-foreground">${c.title}</h4>
            <p class="text-[11px] text-muted-foreground">${c.teacher} · ${c.diff}</p>
          </div>
        </div>
        <button onclick="skClose()" class="px-3 py-1.5 bg-secondary/50 border border-border rounded-xl text-xs font-bold text-foreground hover:bg-secondary transition-all">收起</button>
      </div>
      <div class="space-y-1.5 max-h-60 overflow-y-auto pr-1">
        ${lessons.map((done, i) => `
          <div class="flex items-center gap-3 p-2.5 rounded-xl ${done ? 'bg-emerald-500/5' : 'bg-secondary/30'}">
            <span class="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0 ${done ? 'bg-emerald-500 text-white' : 'bg-white border border-border text-muted-foreground'}">${done ? '✓' : i + 1}</span>
            <span class="flex-1 text-xs ${done ? 'text-muted-foreground line-through' : 'text-foreground font-bold'}">第 ${i + 1} 课 · ${['基础讲解', '示范跟练', '分解动作', '连贯演练', '名师点评', '阶段考核'][i % 6]}</span>
            <button onclick="skLearn(${id}, ${i})" class="px-2.5 py-1 text-[11px] font-bold rounded-lg ${done ? 'text-muted-foreground' : 'bg-blue-600 text-white'} transition-all">${done ? '复习' : '学习'}</button>
          </div>
        `).join('')}
      </div>
      <div class="flex flex-wrap gap-2">
        <button onclick="showToast('⬇️ 动作素材包已加入下载队列')" class="px-4 py-2 bg-[#8B0000] text-white text-xs font-bold rounded-xl hover:bg-[#a00000] transition-all">下载动作素材包</button>
        <button onclick="showToast('📅 已预约名师 1v1 指导')" class="px-4 py-2 bg-secondary/50 border border-border text-foreground text-xs font-bold rounded-xl hover:bg-secondary transition-all">预约指导</button>
      </div>
    </div>
  `;
}
function skLearn(cid, lessonIdx) {
  const c = SK_COURSES.find(x => x.id === cid);
  if (lessonIdx >= c.done) {
    c.done = Math.min(c.lessons, lessonIdx + 1);
    showToast('🎉 完成第 ' + (lessonIdx + 1) + ' 课，进度已更新');
  } else {
    showToast('▶️ 正在复习第 ' + (lessonIdx + 1) + ' 课');
  }
  skOpen(cid);
  skRenderGrid();
}
function skClose() {
  document.getElementById('sk-detail').classList.add('hidden');
}

/* ============================================================
 * 5. 数字资产库 ca_*
 * ============================================================ */
/* 素材库界面多语言（zh/en，其余语言回退英文；跟随 app:langchange） */
const CA_I18N = {
  zh: { all:'全部', mask:'脸谱纹样', model:'3D 模型', texture:'贴图材质', audio:'音频音效', preview:'预览', audioTag:'音频素材' },
  en: { all:'All', mask:'Mask Patterns', model:'3D Models', texture:'Textures', audio:'Sound FX', preview:'Preview', audioTag:'Audio' }
};
function caLang() {
  const l = (localStorage.getItem('app_lang') || 'zh');
  return l.indexOf('zh') === 0 ? 'zh' : (CA_I18N[l] ? l : 'en');
}
function caT(k) {
  const d = CA_I18N[caLang()] || CA_I18N.en;
  return d[k] || CA_I18N.en[k] || k;
}
const CA_CATS = [
  { id: 'all', name: '全部' }, { id: 'mask', name: '脸谱纹样' }, { id: 'model', name: '3D 模型' },
  { id: 'texture', name: '贴图材质' }, { id: 'audio', name: '音频音效' }
];
const CA_ASSETS = [
  { id: 1, cat: 'mask', name: '红脸关羽数字脸谱', img: './assets/mask-red.png', format: 'PNG · 4K', size: '12.4 MB', dl: 3612, fav: true },
  { id: 2, cat: 'mask', name: '金脸龙王数字脸谱', img: './assets/mask-gold.png', format: 'PNG · 4K', size: '13.1 MB', dl: 2987, fav: false },
  { id: 3, cat: 'mask', name: '蓝脸豪杰数字脸谱', img: './assets/mask-blue.png', format: 'PNG · 4K', size: '11.8 MB', dl: 2455, fav: false },
  { id: 4, cat: 'mask', name: '绿脸侠客单色稿', img: './assets/mask_green_hero.jpg', format: 'JPG · 2K', size: '3.2 MB', dl: 1877, fav: false },
  { id: 5, cat: 'mask', name: '蓝虎纹样参考', img: './assets/mask_blue_tiger.jpg', format: 'JPG · 2K', size: '2.9 MB', dl: 1620, fav: false },
  { id: 6, cat: 'mask', name: '金龙纹样参考', img: './assets/mask_gold_dragon.jpg', format: 'JPG · 2K', size: '3.4 MB', dl: 2103, fav: true },
  { id: 7, cat: 'model', name: '芙蓉靠旗战袍 · 高斯泼溅', img: './assets/products/furong_wusheng_sword.jpg', format: '.PLY', size: '268 MB', dl: 892, fav: false },
  { id: 8, cat: 'model', name: '芙蓉盖碗茶具 · OBJ', img: './assets/products/furong_gaiwan_teaset.jpg', format: '.OBJ', size: '45 MB', dl: 1204, fav: false },
  { id: 9, cat: 'model', name: '蜀绣绷架 · OBJ', img: './assets/products/furong_embroidery_frame.jpg', format: '.OBJ', size: '38 MB', dl: 764, fav: false },
  { id: 10, cat: 'texture', name: '芙蓉蜀锦纹理', img: './assets/products/furong_shushi_tapestry.jpg', format: 'TIFF · 8K', size: '96 MB', dl: 1568, fav: false },
  { id: 11, cat: 'texture', name: '藏红花礼盒衬底纹样', img: './assets/products/furong_saffron_box.jpg', format: 'PNG · 4K', size: '18 MB', dl: 977, fav: false },
  { id: 12, cat: 'texture', name: '陶俑釉面材质球', img: './assets/products/furong_opera_pottery.jpg', format: '.MTL', size: '22 MB', dl: 689, fav: false },
  { id: 13, cat: 'audio', name: '《贵妃》高腔选段', img: './assets/audio/pijin.mp3', format: 'MP3 · 48kHz', size: '2.1 MB', dl: 5230, fav: true, isAudio: true },
  { id: 14, cat: 'audio', name: '《贵妃》高腔选段 · 英文讲解版', img: './assets/audio/pijin_en.mp3', format: 'MP3 · 48kHz', size: '1.8 MB', dl: 1342, fav: false, isAudio: true }
];
let caCat = 'all';

function caInit() {
  caRenderCats();
  caRenderGrid();
}
function caRenderCats() {
  document.getElementById('ca-cats').innerHTML = CA_CATS.map(c => `
    <button onclick="caSetCat('${c.id}')" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex-shrink-0 ${c.id === caCat ? 'bg-primary text-white shadow-sm' : 'bg-secondary/50 border border-border text-foreground hover:bg-secondary'}">${caT(c.id)}</button>
  `).join('');
}
function caSetCat(cat) {
  caCat = cat;
  caRenderCats();
  caRenderGrid();
}
function caRenderGrid() {
  const list = CA_ASSETS.filter(a => caCat === 'all' || a.cat === caCat);
  document.getElementById('ca-grid').innerHTML = list.map(a => `
    <div class="bg-white rounded-2xl border border-border/60 overflow-hidden hover:shadow-md transition-all group">
      <div class="relative aspect-square bg-secondary/40 cursor-pointer" onclick="caPreview(${a.id})">
        ${a.isAudio
          ? `<div class="w-full h-full flex items-center justify-center bg-primary/10 text-primary"><div class="text-center space-y-2"><i data-lucide="file-audio" class="w-10 h-10 mx-auto"></i><div class="text-[11px] font-bold">音频素材</div></div></div>`
          : `<img src="${a.img}" alt="${a.name}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">`}
        <span class="absolute top-2 left-2 px-1.5 py-0.5 bg-black/70 text-white text-[11px] rounded font-mono">${a.format}</span>
        <button onclick="event.stopPropagation(); caToggleFav(${a.id})" class="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/50 text-white flex items-center justify-center backdrop-blur-sm hover:scale-110 transition-transform">
          <i data-lucide="heart" class="w-3.5 h-3.5 ${a.fav ? 'fill-red-500 text-red-500' : ''}"></i>
        </button>
      </div>
      <div class="p-3">
        <div class="font-bold text-xs text-foreground truncate">${a.name}</div>
        <div class="flex items-center justify-between mt-1.5">
          <span class="text-[11px] text-muted-foreground">${a.size} · ⬇ ${a.dl > 1000 ? (a.dl / 1000).toFixed(1) + 'k' : a.dl}</span>
          <button onclick="caPreview(${a.id})" class="px-2.5 py-1 bg-primary/10 text-primary text-[11px] font-bold rounded-lg hover:bg-primary/10 transition-all">预览</button>
        </div>
      </div>
    </div>
  `).join('');
  chIcons();
}
function caToggleFav(id) {
  const a = CA_ASSETS.find(x => x.id === id);
  if (!a) return;
  a.fav = !a.fav;
  caRenderGrid();
  showToast(a.fav ? '❤️ 已加入收藏' : '已取消收藏');
}
function caPreview(id) {
  const a = CA_ASSETS.find(x => x.id === id);
  if (!a) return;
  const overlay = document.getElementById('ca-preview');
  overlay.innerHTML = `
    <div class="bg-card border border-border rounded-3xl max-w-lg w-full overflow-hidden shadow-2xl" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between p-4 border-b border-border/60">
        <div>
          <h4 class="font-bold text-sm text-foreground">${a.name}</h4>
          <p class="text-[11px] text-muted-foreground mt-0.5">${a.format} · ${a.size} · ⬇ ${a.dl} 次下载</p>
        </div>
        <button onclick="caHidePreview()" class="w-8 h-8 rounded-full bg-secondary/60 flex items-center justify-center hover:bg-secondary transition-all"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <div class="p-4">
        ${a.isAudio
          ? `<div class="rounded-2xl bg-primary/10 p-5 text-center space-y-3"><i data-lucide="file-audio" class="w-12 h-12 mx-auto text-primary"></i><audio controls src="${a.img}" class="w-full"></audio></div>`
          : `<img src="${a.img}" alt="${a.name}" class="w-full rounded-2xl border border-border/60">`}
        <p class="text-[11px] text-muted-foreground mt-3">授权说明：素材可用于众创平台内二创，商用需申请 IP 授权。</p>
      </div>
      <div class="flex gap-2 p-4 pt-0">
        <button onclick="showToast('⬇️ ${a.name} 开始下载（demo）')" class="flex-1 py-2.5 bg-primary text-white font-bold text-xs rounded-xl hover:bg-primary/85 transition-all">下载素材</button>
        <button onclick="caToggleFav(${a.id}); caHidePreview()" class="px-4 py-2.5 bg-secondary/50 border border-border text-foreground font-bold text-xs rounded-xl hover:bg-secondary transition-all">收藏</button>
      </div>
    </div>
  `;
  overlay.classList.remove('hidden');
  chIcons();
}
function caHidePreview() {
  document.getElementById('ca-preview').classList.add('hidden');
}
function caClosePreview(e) {
  if (e.target === e.currentTarget) caHidePreview();
}

/* ============================================================
 * 6. 3DGS 预览 gs_*
 * ============================================================ */
const GS_SCENES = [
  { id: 'red', name: '红脸关羽 · 脸谱点云', img: './assets/mask-red.png', tag: 'FACE-01 · 8.2w 泼溅点' },
  { id: 'gold', name: '金脸龙王 · 脸谱点云', img: './assets/mask-gold.png', tag: 'FACE-02 · 7.6w 泼溅点' },
  { id: 'blue', name: '蓝脸豪杰 · 脸谱点云', img: './assets/mask-blue.png', tag: 'FACE-03 · 7.9w 泼溅点' },
  { id: 'green', name: '古戏台 · 场景点云', img: './assets/mask-green.png', tag: 'STAGE-01 · 21w 泼溅点' }
];
const GS_DENSITY = [
  { name: '低', step: 7 }, { name: '中', step: 5 }, { name: '高', step: 3 }
];
let gsSceneIdx = 0;
let gsDensityIdx = 1;
let gsPoints = [];
let gsAngleY = 0, gsAngleX = -0.25;
let gsZoom = 1;
let gsAutoRotate = true;
let gsRafId = null;
let gsBound = false;
let gsFps = 60, gsFpsTime = performance.now(), gsFpsCount = 0;

function gsInit() {
  if (!gsBound) {
    gsBindControls();
    gsBound = true;
  }
  gsRenderScenes();
  gsBuildPoints();
  if (!gsRafId) gsLoop();
}
function gsRenderScenes() {
  document.getElementById('gs-scenes').innerHTML = GS_SCENES.map((s, i) => `
    <button onclick="gsSwitch(${i})" class="w-full text-left p-3 rounded-2xl border transition-all flex items-center gap-2.5 ${i === gsSceneIdx ? 'border-[#8B0000] bg-[#8B0000]/5 shadow-sm' : 'border-border/60 bg-white hover:border-[#8B0000]/40'}">
      <img src="${s.img}" class="w-10 h-10 rounded-xl object-cover flex-shrink-0" alt="${s.name}">
      <div class="min-w-0">
        <div class="text-xs font-bold text-foreground truncate">${s.name}</div>
        <div class="text-[11px] text-muted-foreground font-mono truncate">${s.tag}</div>
      </div>
    </button>
  `).join('');
  document.getElementById('gs-badge').textContent = GS_SCENES[gsSceneIdx].tag;
}
function gsSwitch(i) {
  gsSceneIdx = i;
  gsRenderScenes();
  gsBuildPoints();
  showToast('🔄 已加载场景：' + GS_SCENES[i].name);
}
function gsBuildPoints() {
  gsPoints = [];
  const scene = GS_SCENES[gsSceneIdx];
  const img = new Image();
  img.onload = () => {
    const step = GS_DENSITY[gsDensityIdx].step;
    const w = 96, h = Math.max(80, Math.round(96 * img.height / img.width));
    const off = document.createElement('canvas');
    off.width = w; off.height = h;
    const ctx = off.getContext('2d');
    ctx.drawImage(img, 0, 0, w, h);
    let pts = [];
    try {
      const data = ctx.getImageData(0, 0, w, h).data;
      for (let y = 0; y < h; y += 1) {
        for (let x = 0; x < w; x += 1) {
          const i = (y * w + x) * 4;
          const r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3];
          if (a < 40) continue;
          // 跳过接近纯白的背景像素
          if (r > 235 && g > 235 && b > 235) continue;
          const lum = (r + g + b) / 765;
          pts.push({
            x: (x / w - 0.5) * 2.2,
            y: (0.5 - y / h) * 2.2,
            z: (lum - 0.5) * 0.9,
            r, g, b
          });
        }
      }
    } catch (e) { /* 画布跨域污染等异常 → 使用程序化点云兜底 */ }
    if (pts.length < 200) pts = gsProceduralPoints();
    // 按密度抽稀
    const keep = Math.max(1, Math.round(step / 3));
    gsPoints = pts.filter((_, i) => i % keep === 0);
    gsUpdateHud();
  };
  img.onerror = () => { gsPoints = gsProceduralPoints(); gsUpdateHud(); };
  img.src = scene.img;
  gsPoints = gsProceduralPoints(); // 图片加载前先显示兜底点云
  gsUpdateHud();
}
function gsProceduralPoints() {
  const pts = [];
  const palette = [[139, 0, 0], [193, 154, 107], [192, 57, 43], [44, 62, 80], [241, 196, 15]];
  for (let i = 0; i < 1800; i++) {
    const a = Math.random() * Math.PI * 2;
    const b = Math.acos(Math.random() * 2 - 1);
    const rr = 0.9 + Math.random() * 0.15;
    const c = palette[Math.floor(Math.random() * palette.length)];
    pts.push({
      x: rr * Math.sin(b) * Math.cos(a),
      y: rr * Math.cos(b),
      z: rr * Math.sin(b) * Math.sin(a),
      r: c[0], g: c[1], b: c[2]
    });
  }
  return pts;
}
function gsUpdateHud() {
  document.getElementById('gs-hud').innerHTML = `
    <div>POINTS: ${gsPoints.length.toLocaleString()}</div>
    <div>FPS: ${gsFps}</div>
    <div>DENSITY: ${GS_DENSITY[gsDensityIdx].name}</div>
  `;
}
function gsProject(p) {
  const cy = Math.cos(gsAngleY), sy = Math.sin(gsAngleY);
  const cx = Math.cos(gsAngleX), sx = Math.sin(gsAngleX);
  let x = p.x * cy + p.z * sy;
  let z = -p.x * sy + p.z * cy;
  let y = p.y * cx - z * sx;
  z = p.y * sx + z * cx;
  const fov = 3.2;
  const s = fov / (fov + z) * gsZoom;
  return { sx: x * s, sy: y * s, z, s };
}
function gsLoop() {
  gsRafId = requestAnimationFrame(gsLoop);
  const canvas = document.getElementById('gs-canvas');
  if (!canvas || document.getElementById('subview-3dgs').classList.contains('hidden')) return;
  // FPS 统计
  gsFpsCount++;
  const now = performance.now();
  if (now - gsFpsTime > 800) {
    gsFps = Math.round(gsFpsCount * 1000 / (now - gsFpsTime));
    gsFpsTime = now; gsFpsCount = 0;
    gsUpdateHud();
  }
  if (gsAutoRotate) gsAngleY += 0.006;
  const dpr = window.devicePixelRatio || 1;
  const cw = canvas.clientWidth, chh = canvas.clientHeight;
  if (canvas.width !== cw * dpr || canvas.height !== chh * dpr) {
    canvas.width = cw * dpr; canvas.height = chh * dpr;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cw, chh);
  // 地面网格
  ctx.strokeStyle = 'rgba(193,154,107,0.10)';
  ctx.lineWidth = 1;
  for (let gx = -4; gx <= 4; gx++) {
    ctx.beginPath();
    ctx.moveTo(cw / 2 + gx * 40 * gsZoom, chh / 2 + 130 * gsZoom);
    ctx.lineTo(cw / 2 + gx * 40 * gsZoom, chh / 2 + 260 * gsZoom);
    ctx.stroke();
  }
  // 点云（按 z 排序远小近大）
  const sorted = gsPoints.map(p => ({ p, pr: gsProject(p) })).sort((a, b) => b.pr.z - a.pr.z);
  for (const it of sorted) {
    const { p, pr } = it;
    const x = cw / 2 + pr.sx * cw * 0.32;
    const y = chh / 2 + pr.sy * chh * 0.32;
    if (x < -10 || x > cw + 10 || y < -10 || y > chh + 10) continue;
    const size = Math.max(0.8, 2.6 * pr.s);
    ctx.fillStyle = 'rgba(' + p.r + ',' + p.g + ',' + p.b + ',0.85)';
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
  }
}
function gsBindControls() {
  const canvas = document.getElementById('gs-canvas');
  let dragging = false, lastX = 0, lastY = 0;
  canvas.addEventListener('mousedown', e => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    gsAngleY += (e.clientX - lastX) * 0.008;
    gsAngleX = Math.max(-1.2, Math.min(1.2, gsAngleX + (e.clientY - lastY) * 0.006));
    lastX = e.clientX; lastY = e.clientY;
  });
  document.addEventListener('mouseup', () => { dragging = false; });
  canvas.addEventListener('touchstart', e => { dragging = true; lastX = e.touches[0].clientX; lastY = e.touches[0].clientY; }, { passive: true });
  document.addEventListener('touchmove', e => {
    if (!dragging) return;
    gsAngleY += (e.touches[0].clientX - lastX) * 0.008;
    gsAngleX = Math.max(-1.2, Math.min(1.2, gsAngleX + (e.touches[0].clientY - lastY) * 0.006));
    lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
  }, { passive: true });
  document.addEventListener('touchend', () => { dragging = false; });
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    gsZoom = Math.max(0.4, Math.min(2.8, gsZoom * (e.deltaY > 0 ? 0.92 : 1.08)));
  }, { passive: false });
}
function gsToggleRotate() {
  gsAutoRotate = !gsAutoRotate;
  const btn = document.getElementById('gs-btn-rotate');
  btn.className = 'px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all ' + (gsAutoRotate ? 'bg-[#8B0000] text-white' : 'bg-secondary/50 border border-border text-foreground');
  showToast(gsAutoRotate ? '🔄 自动旋转已开启' : '⏸️ 自动旋转已暂停');
}
function gsChangePoint() {
  gsDensityIdx = (gsDensityIdx + 1) % GS_DENSITY.length;
  gsBuildPoints();
  showToast('🎨 泼溅密度：' + GS_DENSITY[gsDensityIdx].name);
}
function gsReset() {
  gsAngleY = 0; gsAngleX = -0.25; gsZoom = 1;
  showToast('↩️ 视角已重置');
}

/* ============================================================
 * 7. 虚实轻剧 qj_*
 * ============================================================ */
const QJ_NODES = {
  n0: { scene: '🌙', bg: 'from-[#2D3436] to-[#8B0000]', title: '后台 · 开演前',
    text: '你溜进后台想近距离看戏，却被班主一把抓住："新来的学徒？正好，今晚缺人手！"锣鼓声已近，走，还是留？',
    choices: [
      { label: '将错就错，留下来', next: 'n1' },
      { label: '说明误会，赶紧溜走', next: 'end_a' }
    ] },
  n1: { scene: '💄', bg: 'from-[#8B0000] to-[#C19A6B]', title: '化妆间 · 一张脸谱',
    text: '师姐递来一张脸谱："《白蛇传》缺个虾兵，你顶上！"你盯着手中色彩斑斓的脸谱，手心冒汗……',
    choices: [
      { label: '戴上脸谱，硬着头皮上台', next: 'n2' },
      { label: '坦白：我一点也不会唱戏', next: 'n3' }
    ] },
  n2: { scene: '🎭', bg: 'from-[#C19A6B] to-[#8B0000]', title: '台上 · 变脸惊魂',
    text: '台上变脸绝活到你这环节出了岔子，台下哗然。千钧一发，丑角师父一句现挂救了场，满堂喝彩化作掌声雷动。',
    choices: [
      { label: '散场后拜师学艺', next: 'n4' },
      { label: '惊魂未定，悄悄离开', next: 'end_b' }
    ] },
  n3: { scene: '🪷', bg: 'from-[#6C5CE7] to-[#2D3436]', title: '侧台 · 水袖三式',
    text: '师姐笑了："谁天生就会？来，我教你水袖三式。"云手、兰花指、甩袖……一招一式，竟有说不出的熨帖。',
    choices: [
      { label: '留下来，正式学戏', next: 'end_c' },
      { label: '其实我只是想要个签名', next: 'end_d' }
    ] },
  n4: { scene: '🏮', bg: 'from-[#8B0000] to-[#2D3436]', title: '空荡的戏台 · 一问',
    text: '师父收徒前只问一句："变脸，靠的是手上快，还是心里定？"',
    choices: [
      { label: '手上快，快到无人看清', next: 'end_e1' },
      { label: '心里定，定到面不改色', next: 'end_e' }
    ] }
};
const QJ_ENDINGS = {
  end_a: { name: '匆匆过客', emoji: '🚪', desc: '你溜出戏班，锣鼓声渐远。川剧与你，只是今晚路过的一段热闹。' },
  end_b: { name: '一日戏梦', emoji: '🌾', desc: '你悄悄离开，那晚的台步与喝彩成了偶尔想起的一场梦。' },
  end_c: { name: '梨园新蕊', emoji: '🌱', desc: '你正式拜师学戏。数年后，侧台的水袖换成台前的身影。' },
  end_d: { name: '追星之旅', emoji: '📸', desc: '师姐笑着签了名，还送你一张脸谱书签。快乐，有时就这么简单。' },
  end_e1: { name: '薪火相传', emoji: '🔥', desc: '师父摇头又笑了："手快是形，心定是魂——记住你今晚说的话。"你入了门。' },
  end_e: { name: '薪火相传', emoji: '🔥', desc: '师父点头："说到了根上。"那晚，你成了变脸绝技的下一代传人。' }
};
const QJ_KEY = 'qj_endings_v1';
let qjCurrent = 'n0';
let qjStep = 0;
let qjTypeTimer = null;

function qjInit() {
  qjRenderStart();
  qjRenderEndingDots();
}
function qjCollected() {
  try { return JSON.parse(localStorage.getItem(QJ_KEY) || '[]'); } catch (e) { return []; }
}
function qjRenderEndingDots() {
  const collected = qjCollected();
  const allIds = ['end_a', 'end_b', 'end_c', 'end_d', 'end_e'];
  document.getElementById('qj-endings').innerHTML = allIds.map(id => {
    const got = collected.includes(id) || (id === 'end_e' && collected.includes('end_e1'));
    return `<span class="w-3 h-3 rounded-full flex items-center justify-center text-[7px] ${got ? 'bg-[#8B0000] text-white' : 'bg-secondary/70 text-muted-foreground'}" title="${QJ_ENDINGS[id].name}">${got ? '★' : ''}</span>`;
  }).join('');
}
function qjRenderStart() {
  const collected = qjCollected().length;
  const start = document.getElementById('qj-start');
  document.getElementById('qj-scene').classList.add('hidden');
  start.classList.remove('hidden');
  document.getElementById('qj-progress').style.width = '0%';
  start.innerHTML = `
    <div class="w-20 h-20 mx-auto rounded-full bg-[#8B0000]/10 flex items-center justify-center text-4xl">🏮</div>
    <h4 class="font-display text-xl font-bold text-foreground">入班第一天</h4>
    <p class="text-sm text-muted-foreground max-w-md mx-auto">一个误入后台的夜晚，一场将至的大戏。你的每个选择，都通向不同的结局——已收集 <span class="font-bold text-[#8B0000]">${collected}</span> / 5 个结局。</p>
    <button onclick="qjBegin()" class="px-8 py-3 bg-[#8B0000] text-white font-bold rounded-xl hover:bg-[#a00000] transition-all shadow-md">开始剧情</button>
  `;
}
function qjBegin() {
  qjCurrent = 'n0';
  qjStep = 0;
  document.getElementById('qj-start').classList.add('hidden');
  document.getElementById('qj-scene').classList.remove('hidden');
  qjShowNode();
}
function qjShowNode() {
  const node = QJ_NODES[qjCurrent];
  if (!node) return;
  document.getElementById('qj-progress').style.width = (qjStep / 4 * 100) + '%';
  const box = document.getElementById('qj-scene');
  box.innerHTML = `
    <div class="rounded-2xl overflow-hidden border border-border/60">
      <div class="h-28 bg-gradient-to-r ${node.bg} flex items-center justify-center text-4xl">${node.scene}</div>
      <div class="bg-white p-5">
        <div class="text-[11px] font-bold text-[#C19A6B] tracking-widest mb-1.5">${node.title}</div>
        <p id="qj-text" class="text-sm text-foreground leading-relaxed min-h-[3.5rem] cursor-pointer"></p>
        <div id="qj-choices" class="hidden grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-4"></div>
      </div>
    </div>
  `;
  const textEl = document.getElementById('qj-text');
  const choicesEl = document.getElementById('qj-choices');
  qjType(textEl, node.text, () => qjShowChoices(node.choices));
  textEl.onclick = () => qjSkipType(textEl, node.text, () => qjShowChoices(node.choices));
}
function qjType(el, text, done) {
  clearInterval(qjTypeTimer);
  el.textContent = '';
  let i = 0;
  qjTypeTimer = setInterval(() => {
    el.textContent += text[i++];
    if (i >= text.length) { clearInterval(qjTypeTimer); done(); }
  }, 26);
}
function qjSkipType(el, text, done) {
  if (el.textContent.length < text.length) {
    clearInterval(qjTypeTimer);
    el.textContent = text;
    done();
  }
}
function qjShowChoices(choices) {
  const box = document.getElementById('qj-choices');
  box.classList.remove('hidden');
  box.innerHTML = choices.map(c => `
    <button onclick="qjPick('${c.next}')" class="p-3.5 rounded-2xl bg-secondary/40 border border-border/60 hover:border-[#8B0000] hover:bg-[#8B0000]/5 transition-all text-left font-bold text-sm text-foreground active:scale-[0.98]">${c.label}</button>
  `).join('');
  chIcons();
}
function qjPick(next) {
  if (QJ_NODES[next]) {
    qjCurrent = next;
    qjStep++;
    qjShowNode();
    return;
  }
  // 结局
  const ending = QJ_ENDINGS[next];
  qjStep = 4;
  document.getElementById('qj-progress').style.width = '100%';
  const collected = qjCollected();
  const saveId = collected.includes('end_e') && next === 'end_e1' ? 'end_e1' : next;
  if (!collected.includes(saveId)) {
    collected.push(saveId);
    try { localStorage.setItem(QJ_KEY, JSON.stringify(collected)); } catch (e) {}
  }
  qjRenderEndingDots();
  const box = document.getElementById('qj-scene');
  box.innerHTML = `
    <div class="text-center space-y-4 py-8">
      <div class="w-20 h-20 mx-auto rounded-full bg-[#8B0000]/10 flex items-center justify-center text-4xl">${ending.emoji}</div>
      <div>
        <div class="text-[11px] text-muted-foreground tracking-widest">解锁结局</div>
        <h4 class="font-display text-2xl font-bold text-[#8B0000] mt-1">${ending.name}</h4>
      </div>
      <p class="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">${ending.desc}</p>
      <div class="flex justify-center gap-2 pt-1">
        <button onclick="qjBegin()" class="px-6 py-2.5 bg-[#8B0000] text-white font-bold rounded-xl hover:bg-[#a00000] transition-all">再来一次</button>
        <button onclick="showToast('📤 结局卡已分享给好友')" class="px-6 py-2.5 bg-secondary/60 text-[#8B0000] font-bold rounded-xl hover:bg-secondary transition-all">分享结局卡</button>
      </div>
    </div>
  `;
  showToast('🏆 解锁结局「' + ending.name + '」');
}

/* ============================================================
 * 8. 创意工坊 ws_*
 * ============================================================ */
const WS_TEMPLATES = [
  {
    id: 'video', name: '川剧科普短视频', icon: '🎬', desc: '5 个 Agent 协作产出 60 秒短视频脚本与首帧',
    nodes: [
      { name: '选题策划官', icon: 'lightbulb', model: 'GLM-4.6' },
      { name: '编剧作家', icon: 'pen-line', model: 'GLM-4.6' },
      { name: '分镜画师', icon: 'palette', model: 'CogView-4' },
      { name: '配音演员', icon: 'mic', model: 'GPT-SoVITS' },
      { name: '审校官', icon: 'shield-check', model: 'GLM-4.6' }
    ],
    logs: [
      '选题策划官：检索本周热榜，锁定话题「00 后为什么看不懂变脸」',
      '编剧作家：生成 60 秒脚本《60 秒看懂川剧变脸》，埋 2 个反转点',
      '分镜画师：产出 8 张分镜，首帧已渲染（红脸→金脸切换构图）',
      '配音演员：川普口播音轨合成完毕，语速 4.2 字/秒',
      '审校官：术语 3 处已校正（帮腔/扯脸/揉脸），审核通过 ✅'
    ],
    output: {
      title: '《60 秒看懂川剧变脸》',
      img: './assets/mask-gold-ai.jpg',
      text: '开场 3 秒红脸特写 → "变脸变的不是脸，是人心" → 三种扯脸技法快剪 → 结尾金脸定格 + 话题引导。'
    }
  },
  {
    id: 'mask', name: '脸谱设计方案', icon: '🎭', desc: '从文化考据到配色的脸谱共创流水线',
    nodes: [
      { name: '文化考据官', icon: 'book-open', model: 'GLM-4.6' },
      { name: '纹样画师', icon: 'palette', model: 'CogView-4' },
      { name: '配色师', icon: 'droplets', model: 'CogView-4' },
      { name: '审校官', icon: 'shield-check', model: 'GLM-4.6' }
    ],
    logs: [
      '文化考据官：确定主题「少年包公」，梳理额间月牙纹样考据 3 条',
      '纹样画师：生成黑白花脸底稿 2 版，眉纹采用"卧蚕眉"变体',
      '配色师：主色定黑金撞色，辅色朱砂红点缀，饱和度校准完成',
      '审校官：纹样与史料一致性核对通过，进入素材库 ✅'
    ],
    output: {
      title: '少年包公 · 新脸谱设计',
      img: './assets/mask-black-ai.jpg',
      text: '黑金主调 + 朱砂点睛，额间月牙改为新月钩纹，兼顾传统规制与年轻审美。'
    }
  },
  {
    id: 'script', name: '互动剧本工坊', icon: '📜', desc: '为虚实轻剧自动生成多分支剧本',
    nodes: [
      { name: '剧情架构师', icon: 'network', model: 'GLM-4.6' },
      { name: '对话打磨师', icon: 'message-circle', model: 'GLM-4.6' },
      { name: '分支设计师', icon: 'git-branch', model: 'GLM-4.6' },
      { name: '质检官', icon: 'shield-check', model: 'GLM-4.6' }
    ],
    logs: [
      '剧情架构师：生成《入班第二天》三幕结构，主线 +2 支线',
      '对话打磨师：川味口语化改写 14 处，人物声线区分度提升',
      '分支设计师：布置 5 个选择点，收敛至 3 个结局，情感曲线校验通过',
      '质检官：死链检查 0 错误，剧本已推送至虚实轻剧编辑器 ✅'
    ],
    output: {
      title: '《入班第二天》互动剧本',
      img: './assets/mask-green-ai.jpg',
      text: '三幕五选择三结局：一条线学变脸、一条线探后台、一条线帮师姐救场，覆盖"传承/悬念/温情"三种体验。'
    }
  }
];
let wsTemplateIdx = 0;
let wsRunning = false;

function wsInit() {
  wsRenderTemplates();
  wsRenderPipeline();
  wsLogClear();
}
function wsRenderTemplates() {
  document.getElementById('ws-templates').innerHTML = WS_TEMPLATES.map((t, i) => `
    <button onclick="wsSelect(${i})" class="text-left p-4 rounded-2xl border transition-all ${i === wsTemplateIdx ? 'border-[#8B0000] bg-[#8B0000]/5 shadow-sm' : 'border-border/60 bg-white hover:border-[#8B0000]/40'}">
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-xl">${t.icon}</span>
        <span class="font-bold text-sm text-foreground">${t.name}</span>
      </div>
      <p class="text-[11px] text-muted-foreground">${t.desc}</p>
    </button>
  `).join('');
}
function wsSelect(i) {
  if (wsRunning) { showToast('⏳ 工作流运行中，请稍候'); return; }
  wsTemplateIdx = i;
  wsRenderTemplates();
  wsRenderPipeline();
  wsLogClear();
  document.getElementById('ws-output').classList.add('hidden');
}
function wsRenderPipeline(statuses) {
  const t = WS_TEMPLATES[wsTemplateIdx];
  const st = statuses || t.nodes.map(() => 'pending');
  document.getElementById('ws-pipeline').innerHTML = t.nodes.map((n, i) => `
    <div class="flex items-stretch flex-shrink-0">
      <div class="w-36 rounded-2xl border p-3 space-y-2 ${st[i] === 'running' ? 'border-[#8B0000] bg-[#8B0000]/5 animate-pulse' : st[i] === 'done' ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-border/60 bg-white'}">
        <div class="flex items-center justify-between">
          <i data-lucide="${n.icon}" class="w-4.5 h-4.5 ${st[i] === 'done' ? 'text-emerald-600' : 'text-[#8B0000]'}" style="width:18px;height:18px"></i>
          ${st[i] === 'done' ? '<i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-600"></i>' : st[i] === 'running' ? '<i data-lucide="loader-2" class="w-4 h-4 text-[#8B0000] animate-spin"></i>' : '<i data-lucide="clock" class="w-4 h-4 text-muted-foreground"></i>'}
        </div>
        <div>
          <div class="font-bold text-xs text-foreground leading-tight">${n.name}</div>
          <div class="text-[11px] text-muted-foreground font-mono mt-0.5">${n.model}</div>
        </div>
      </div>
      ${i < t.nodes.length - 1 ? '<div class="flex items-center px-1 text-muted-foreground"><i data-lucide="arrow-right" class="w-4 h-4"></i></div>' : ''}
    </div>
  `).join('');
  chIcons();
}
function wsLogLine(text) {
  const log = document.getElementById('ws-log');
  const time = new Date();
  const ts = [time.getHours(), time.getMinutes(), time.getSeconds()].map(n => String(n).padStart(2, '0')).join(':');
  const div = document.createElement('div');
  div.innerHTML = '<span class="text-emerald-500/60">[' + ts + ']</span> ' + text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
function wsLogClear() {
  document.getElementById('ws-log').innerHTML = '<div class="text-muted-foreground">// 点击「运行工作流」启动 Agent 协作…</div>';
}
function wsRunPipeline() {
  if (wsRunning) return;
  const t = WS_TEMPLATES[wsTemplateIdx];
  wsRunning = true;
  const btn = document.getElementById('ws-run-btn');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> 运行中…';
  chIcons();
  document.getElementById('ws-output').classList.add('hidden');
  wsLogClear();
  const statuses = t.nodes.map(() => 'pending');
  let i = 0;
  const step = () => {
    if (i > 0) { statuses[i - 1] = 'done'; wsLogLine(t.logs[i - 1]); }
    if (i < statuses.length) {
      statuses[i] = 'running';
      wsRenderPipeline(statuses);
      i++;
      setTimeout(step, 1300 + Math.random() * 600);
    } else {
      wsRunning = false;
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="play" class="w-3.5 h-3.5"></i> 再次运行';
      chIcons();
      wsShowOutput();
    }
  };
  wsLogLine('工作流「' + t.name + '」已启动，' + t.nodes.length + ' 个 Agent 待命');
  step();
}
function wsShowOutput() {
  const t = WS_TEMPLATES[wsTemplateIdx];
  const out = document.getElementById('ws-output');
  out.classList.remove('hidden');
  out.innerHTML = `
    <div class="bg-gradient-to-r from-[#8B0000]/5 to-[#C19A6B]/10 rounded-2xl border border-[#8B0000]/15 p-5 flex flex-col sm:flex-row items-center gap-4">
      <img src="${t.output.img}" alt="${t.output.title}" class="w-28 h-28 rounded-2xl object-cover border border-border/60 flex-shrink-0">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-1">
          <span class="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 text-[11px] font-bold rounded-full">产出完成</span>
          <span class="text-[11px] text-muted-foreground">由 ${t.nodes.length} 个 Agent 协同生成</span>
        </div>
        <h4 class="font-bold text-foreground">${t.output.title}</h4>
        <p class="text-xs text-muted-foreground mt-1 leading-relaxed">${t.output.text}</p>
      </div>
      <div class="flex flex-col gap-2 flex-shrink-0">
        <button onclick="showToast('💾 已保存到我的素材库')" class="px-4 py-2 bg-[#8B0000] text-white text-xs font-bold rounded-xl hover:bg-[#a00000] transition-all">保存产出</button>
        <button onclick="showToast('🔁 已基于本次产出发起迭代工作流')" class="px-4 py-2 bg-secondary/50 border border-border text-foreground text-xs font-bold rounded-xl hover:bg-secondary transition-all">迭代优化</button>
      </div>
    </div>
  `;
  showToast('🎉 工作流运行完成，产出已生成');
  chIcons();
}

/* ============================================================
 * 9. 智能体矩阵 am_*
 * ============================================================ */
const AM_DEFAULTS = [
  { id: 'planner', name: '选题策划官', icon: 'lightbulb', desc: '洞察热点、策划选题与内容方向', model: 'GLM-4.6', temp: 0.7, on: true, caps: { text: true, image: false, voice: false, video: false },
    prompt: '你是川剧院内容策划专家，擅长从非遗热点中提炼年轻人感兴趣的选题。' },
  { id: 'writer', name: '编剧作家', icon: 'pen-line', desc: '撰写脚本、剧本与文案', model: 'GLM-4.6', temp: 0.8, on: true, caps: { text: true, image: false, voice: false, video: false },
    prompt: '你是资深川剧编剧，文风兼具川味幽默与戏剧张力。' },
  { id: 'painter', name: '分镜画师', icon: 'palette', desc: '生成分镜、脸谱与场景视觉', model: 'CogView-4', temp: 0.6, on: true, caps: { text: false, image: true, voice: false, video: false },
    prompt: '你是戏曲视觉设计师，精通脸谱纹样与舞台构图。' },
  { id: 'voice', name: '配音演员', icon: 'mic', desc: '克隆音色、合成角色配音', model: 'GPT-SoVITS', temp: 0.5, on: true, caps: { text: false, image: false, voice: true, video: false },
    prompt: '你是川剧口播配音师，音色醇厚、节奏鲜明。' },
  { id: 'reviewer', name: '审校官', icon: 'shield-check', desc: '术语审校、史实核查与质量把关', model: 'GLM-4.6', temp: 0.2, on: true, caps: { text: true, image: false, voice: false, video: false },
    prompt: '你是非遗内容审校官，严格核查川剧术语与史实准确性。' },
  { id: 'restorer', name: '数据修复师', icon: 'wand-2', desc: '老照片/唱片 AI 修复增强', model: 'PhotoRestorer-v2', temp: 0.3, on: false, caps: { text: false, image: true, voice: true, video: true },
    prompt: '你是数字文保修复师，专注戏曲老物料的智能修复。' }
];
const AM_MODELS = ['GLM-4.6', 'GLM-4.5-Air', 'CogView-4', 'GPT-SoVITS', 'PhotoRestorer-v2', '本地 Llama-3'];
const AM_STORE_KEY = 'am_config_v1';
let amAgents = [];

function amInit() {
  try {
    const saved = JSON.parse(localStorage.getItem(AM_STORE_KEY) || 'null');
    amAgents = saved ? saved : JSON.parse(JSON.stringify(AM_DEFAULTS));
  } catch (e) {
    amAgents = JSON.parse(JSON.stringify(AM_DEFAULTS));
  }
  amRenderGrid();
  amRenderMatrix();
}
function amRenderGrid() {
  document.getElementById('am-grid').innerHTML = amAgents.map((a, i) => `
    <div class="bg-white rounded-2xl border border-border/60 p-4 space-y-3 ${a.on ? '' : 'opacity-60'}">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="w-10 h-10 rounded-xl bg-[#8B0000]/10 text-[#8B0000] flex items-center justify-center"><i data-lucide="${a.icon}" class="w-5 h-5"></i></div>
          <div>
            <div class="font-bold text-sm text-foreground">${a.name}</div>
            <div class="text-[11px] text-muted-foreground">${a.desc}</div>
          </div>
        </div>
        <button onclick="amToggle(${i})" class="w-11 h-6 rounded-full transition-all relative flex-shrink-0 ${a.on ? 'bg-emerald-500' : 'bg-gray-300'}">
          <span class="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${a.on ? 'left-[22px]' : 'left-0.5'}"></span>
        </button>
      </div>
      <div class="grid grid-cols-2 gap-2.5">
        <label class="space-y-1">
          <span class="text-[11px] font-bold text-muted-foreground">推理模型</span>
          <select onchange="amAgents[${i}].model=this.value" class="w-full px-2.5 py-2 rounded-xl border border-border bg-secondary/30 text-xs text-foreground focus:outline-none focus:border-[#8B0000]">
            ${AM_MODELS.map(m => `<option ${a.model === m ? 'selected' : ''}>${m}</option>`).join('')}
          </select>
        </label>
        <label class="space-y-1">
          <span class="text-[11px] font-bold text-muted-foreground flex justify-between"><span>创造性温度</span><span id="am-temp-val-${i}" class="text-[#8B0000]">${a.temp.toFixed(1)}</span></span>
          <input type="range" min="0" max="1.5" step="0.1" value="${a.temp}" oninput="amTempSlide(${i}, this.value)" onchange="amAgents[${i}].temp=parseFloat(this.value)" class="w-full accent-[#8B0000]">
        </label>
      </div>
      <details class="group">
        <summary class="text-[11px] font-bold text-[#8B0000] cursor-pointer select-none flex items-center gap-1">系统提示词 <i data-lucide="chevron-down" class="w-3 h-3 group-open:rotate-180 transition-transform"></i></summary>
        <textarea rows="3" onchange="amAgents[${i}].prompt=this.value" class="mt-2 w-full px-3 py-2.5 rounded-xl border border-border bg-secondary/30 text-xs text-foreground leading-relaxed focus:outline-none focus:border-[#8B0000]">${a.prompt}</textarea>
      </details>
    </div>
  `).join('');
  chIcons();
}
function amTempSlide(i, val) {
  document.getElementById('am-temp-val-' + i).textContent = parseFloat(val).toFixed(1);
}
function amToggle(i) {
  amAgents[i].on = !amAgents[i].on;
  amRenderGrid();
  showToast(amAgents[i].on ? '✅ 已启用 ' + amAgents[i].name : '⏸️ 已停用 ' + amAgents[i].name);
}
function amSave() {
  try { localStorage.setItem(AM_STORE_KEY, JSON.stringify(amAgents)); } catch (e) {}
  const badge = document.getElementById('am-saved-badge');
  badge.classList.remove('hidden');
  setTimeout(() => badge.classList.add('hidden'), 2500);
  showToast('💾 智能体矩阵配置已保存，全平台生效');
}
function amResetDefaults() {
  amAgents = JSON.parse(JSON.stringify(AM_DEFAULTS));
  try { localStorage.removeItem(AM_STORE_KEY); } catch (e) {}
  amRenderGrid();
  showToast('↩️ 已恢复默认配置');
}
function amRenderMatrix() {
  const capDefs = [
    { key: 'text', name: '文本' }, { key: 'image', name: '图像' },
    { key: 'voice', name: '语音' }, { key: 'video', name: '视频' }
  ];
  document.getElementById('am-matrix').innerHTML = `
    <thead>
      <tr>
        <th class="text-left p-2.5 border-b border-border/60 font-bold text-foreground">智能体</th>
        ${capDefs.map(c => `<th class="p-2.5 border-b border-border/60 font-bold text-foreground">${caT(c.id)}</th>`).join('')}
        <th class="p-2.5 border-b border-border/60 font-bold text-foreground">状态</th>
      </tr>
    </thead>
    <tbody>
      ${amAgents.map(a => `
        <tr>
          <td class="p-2.5 border-b border-border/40 font-bold text-xs text-foreground">${a.name}</td>
          ${capDefs.map(c => `<td class="p-2.5 border-b border-border/40 text-center">${a.caps[c.key] ? '<span class="text-emerald-600 font-bold">✓</span>' : '<span class="text-muted-foreground/40">—</span>'}</td>`).join('')}
          <td class="p-2.5 border-b border-border/40 text-center">${a.on ? '<span class="px-2 py-0.5 bg-emerald-500/10 text-emerald-600 text-[11px] font-bold rounded-full">启用</span>' : '<span class="px-2 py-0.5 bg-gray-200 text-gray-500 text-[11px] font-bold rounded-full">停用</span>'}</td>
        </tr>
      `).join('')}
    </tbody>
  `;
}

/* ============================================================
 * 10. 创作者中心 cc_*（等级 / 戏份 / 收益 / 赏金任务 / 提现）
 * ============================================================ */
const CC_LEVELS = [
  { id: 1, name: '学徒', threshold: 0,     icon: '🎓', desc: '注册即授 · 可接任务赚戏份' },
  { id: 2, name: '龙套', threshold: 500,   icon: '🎭', desc: '素材可上架资产库 · 授权分成 50%' },
  { id: 3, name: '角儿', threshold: 2000,  icon: '🌟', desc: '作品进 IP 授权库 · 设计上架文创旗舰店' },
  { id: 4, name: '名角', threshold: 8000,  icon: '👑', desc: 'Skills 库开课收学费 · 分成 70%' },
  { id: 5, name: '台柱', threshold: 30000, icon: '🏆', desc: '定制 AI 分身 · 演出票务分成' }
];
const CC_SIGN_KEY = 'cc_signin_date';
const CC_CHANNELS = [
  { name: '任务赏金',   icon: 'hammer',        amount: 1280.00, color: '#8B0000' },
  { name: '素材分成',   icon: 'database',      amount: 460.50,  color: '#C19A6B' },
  { name: '工作流售卖', icon: 'workflow',      amount: 298.00,  color: '#0d9488' },
  { name: 'IP 授权',    icon: 'coins',         amount: 0,       color: '#7c3aed' },
  { name: '课程分成',   icon: 'zap',           amount: 0,       color: '#2563eb', locked: true },
  { name: '商品入驻',   icon: 'shopping-bag',  amount: 0,       color: '#059669' }
];
const CC_TREND = [
  { label: '3月', v: 180 }, { label: '4月', v: 240 }, { label: '5月', v: 320 },
  { label: '6月', v: 410 }, { label: '7月', v: 610 }, { label: '8月', v: 686 }
];
const CC_TASK_SEED = [
  { id: 1, type: '老照片修复', title: '1958 年《秋江》剧照 · 褪色折痕修复', bounty: 200, points: 20, deadline: '3 天',  diff: '中等', status: 'open' },
  { id: 2, type: '老唱片修复', title: '1962 年高腔《拷红》蜡盘 · 噪声剥离', bounty: 400, points: 40, deadline: '5 天',  diff: '困难', status: 'open' },
  { id: 3, type: '海报设计',   title: '川剧节主视觉海报 · 面向年轻观众',     bounty: 800, points: 40, deadline: '12 天', diff: '中等', status: 'open' },
  { id: 4, type: '纹样补全',   title: '清末脸谱粉本矢量补全 · 12 帧',        bounty: 150, points: 20, deadline: '7 天',  diff: '简单', status: 'open' },
  { id: 5, type: '模型训练',   title: '三国戏人物 LoRA 训练 · 含测试报告',   bounty: 600, points: 40, deadline: '15 天', diff: '困难', status: 'open' }
];
const CC_TX_SEED = [
  { time: '今天 14:32', type: 'money',  amount: 150,  title: '任务赏金 ·《秋江》剧照修复（一期）' },
  { time: '今天 10:15', type: 'points', amount: 60,   title: '课程完成 · 旦角水袖十式 第 6 课' },
  { time: '昨天 21:40', type: 'money',  amount: 29.9, title: '素材分成 · 红脸关羽数字脸谱 商用授权 ×1' },
  { time: '3 天前',     type: 'money',  amount: 200,  title: '任务赏金 · 老唱片降噪' },
  { time: '3 天前',     type: 'points', amount: 2,    title: '素材被下载 ×1 · 蜀绣绷架 OBJ' },
  { time: '5 天前',     type: 'money',  amount: 98,   title: '工作流售卖 · 川剧短视频流水线 ×1' },
  { time: '上周',       type: 'money',  amount: -500, title: '提现 → 尾号 6688（已到账）' }
];
let ccState = null;
let ccTxTab = 'all';

function ccInit() {
  if (!ccState) {
    ccState = {
      points: 3260,
      totalEarnings: 2038.50,
      withdrawable: 438.50,
      monthEarnings: 686.00,
      tasks: JSON.parse(JSON.stringify(CC_TASK_SEED)),
      transactions: JSON.parse(JSON.stringify(CC_TX_SEED))
    };
  }
  ccRenderAll();
}
function ccRenderAll() {
  ccRenderOverview();
  ccRenderLevel();
  ccRenderRevenue();
  ccRenderTransactions();
  ccRenderTasks();
  chIcons();
}
function ccLevelInfo() {
  let idx = 0;
  CC_LEVELS.forEach((l, i) => { if (ccState.points >= l.threshold) idx = i; });
  const lv = CC_LEVELS[idx];
  const next = CC_LEVELS[idx + 1] || null;
  const pct = next ? Math.min(100, Math.round((ccState.points - lv.threshold) / (next.threshold - lv.threshold) * 100)) : 100;
  return { lv, idx, next, pct };
}
function ccSignedToday() {
  try { return localStorage.getItem(CC_SIGN_KEY) === new Date().toDateString(); } catch (e) { return false; }
}
function ccSignIn() {
  if (ccSignedToday()) return;
  try { localStorage.setItem(CC_SIGN_KEY, new Date().toDateString()); } catch (e) {}
  ccState.points += 5;
  ccState.transactions.unshift({ time: '刚刚', type: 'points', amount: 5, title: '每日签到' });
  ccRenderAll();
  showToast('📅 签到成功，戏份 +5');
}
function ccRenderOverview() {
  const { lv, next } = ccLevelInfo();
  const signed = ccSignedToday();
  const fmt = n => '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const toNext = next ? '距「' + next.name + '」还差 ' + (next.threshold - ccState.points).toLocaleString() : '已达最高等级';
  document.getElementById('cc-overview').innerHTML = `
    <div class="rounded-3xl p-5 sm:p-6 text-white space-y-5 shadow-lg bg-gradient-to-r from-[#8B0000] via-[#922b28] to-[#a0522d]">
      <div class="flex flex-col sm:flex-row sm:items-center gap-4">
        <div class="flex items-center gap-3 flex-1 min-w-0">
          <div class="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center text-3xl flex-shrink-0">${lv.icon}</div>
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-display text-lg font-bold">川剧学徒 · 芙蓉</span>
              <span class="px-2 py-0.5 bg-amber-400/90 text-[#8B0000] text-[11px] font-bold rounded-full">L${lv.id} ${lv.name}</span>
            </div>
            <p class="text-xs text-white/70 mt-0.5">花脸人格 · 包公型守护者 · 已入班 132 天</p>
          </div>
        </div>
        <button onclick="ccSignIn()" ${signed ? 'disabled' : ''} class="px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex-shrink-0 ${signed ? 'bg-white/15 text-white/60 cursor-default' : 'bg-amber-400 text-[#8B0000] hover:bg-amber-300 active:scale-95 shadow-md'}">
          ${signed ? '今日已签到 ✓' : '签到领 +5 戏份'}
        </button>
      </div>
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4">
          <div class="text-[11px] text-white/60 tracking-widest">戏份余额</div>
          <div class="text-2xl font-bold mt-1">${ccState.points.toLocaleString()}</div>
          <div class="text-[11px] text-amber-300/90 mt-0.5">${toNext}</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4">
          <div class="text-[11px] text-white/60 tracking-widest">累计收益</div>
          <div class="text-2xl font-bold mt-1">${fmt(ccState.totalEarnings)}</div>
          <div class="text-[11px] text-white/50 mt-0.5">六大通道合计</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4">
          <div class="text-[11px] text-white/60 tracking-widest">本月收益</div>
          <div class="text-2xl font-bold mt-1">${fmt(ccState.monthEarnings)}</div>
          <div class="text-[11px] text-emerald-300/90 mt-0.5">环比 +12.5% ↑</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4">
          <div class="text-[11px] text-white/60 tracking-widest">可提现余额</div>
          <div class="text-2xl font-bold mt-1">${fmt(ccState.withdrawable)}</div>
          <button onclick="ccOpenWithdraw()" class="mt-1.5 px-3 py-1 bg-white/90 text-[#8B0000] text-[11px] font-bold rounded-lg hover:bg-white active:scale-95 transition-all">提现</button>
        </div>
      </div>
    </div>
  `;
}
function ccRenderLevel() {
  const { lv, idx, next, pct } = ccLevelInfo();
  const fillPct = (80 * (idx + pct / 100) / (CC_LEVELS.length - 1)).toFixed(1);
  const nodes = CC_LEVELS.map((l, i) => {
    const reached = i <= idx;
    const isCurrent = i === idx;
    return `
      <div class="flex-1 flex flex-col items-center relative z-10">
        <div class="w-12 h-12 rounded-full flex items-center justify-center text-xl border-2 transition-all ${isCurrent ? 'bg-[#8B0000] text-white border-[#8B0000] shadow-lg scale-110' : reached ? 'bg-[#8B0000]/10 text-[#8B0000] border-[#8B0000]/40' : 'bg-secondary/50 text-muted-foreground border-border'}">${l.icon}</div>
        <div class="text-xs font-bold mt-1.5 ${isCurrent ? 'text-[#8B0000]' : reached ? 'text-foreground' : 'text-muted-foreground'}">${l.name}</div>
        <div class="text-[11px] text-muted-foreground mt-0.5">${l.threshold === 0 ? '起点' : l.threshold.toLocaleString() + ' 戏份'}</div>
      </div>`;
  }).join('');
  document.getElementById('cc-level-path').innerHTML = `
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h4 class="font-display text-lg font-bold text-foreground flex items-center gap-2">
          <i data-lucide="trending-up" class="w-5 h-5 text-[#8B0000]"></i> 科班成长路径
        </h4>
        ${next
          ? '<span class="text-xs text-muted-foreground">还差 <span class="font-bold text-[#8B0000]">' + (next.threshold - ccState.points).toLocaleString() + '</span> 戏份升至「' + next.name + '」</span>'
          : '<span class="text-xs text-amber-600 font-bold">已达最高等级</span>'}
      </div>
      <div class="relative pt-1 pb-2">
        <div class="absolute top-7 left-[10%] right-[10%] h-1 bg-secondary/60 rounded-full"></div>
        <div class="absolute top-7 left-[10%] h-1 bg-[#8B0000] rounded-full transition-all duration-700" style="width:${fillPct}%"></div>
        <div class="flex">${nodes}</div>
      </div>
      <div class="bg-[#8B0000]/5 border border-[#8B0000]/10 rounded-2xl p-4 flex flex-col sm:flex-row gap-3">
        <div class="flex-1">
          <div class="text-[11px] font-bold text-[#8B0000] mb-1">当前权益 · ${lv.name}</div>
          <p class="text-xs text-muted-foreground">${lv.desc}</p>
        </div>
        ${next ? `
        <div class="flex-1 sm:border-l sm:border-border/60 sm:pl-4">
          <div class="text-[11px] font-bold text-amber-600 mb-1">下一级解锁 · ${next.name}</div>
          <p class="text-xs text-muted-foreground">${next.desc}</p>
        </div>` : ''}
      </div>
    </div>
  `;
}
function ccRenderRevenue() {
  const fmt = n => '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const maxChannel = Math.max(...CC_CHANNELS.map(c => c.amount), 1);
  const maxTrend = Math.max(...CC_TREND.map(t => t.v));
  document.getElementById('cc-revenue').innerHTML = `
    <div class="space-y-4">
      <h4 class="font-display text-lg font-bold text-foreground flex items-center gap-2">
        <i data-lucide="bar-chart-3" class="w-5 h-5 text-[#8B0000]"></i> 收益看板
      </h4>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="bg-white rounded-2xl border border-border/60 p-4 space-y-3.5">
          <div class="text-xs font-bold text-foreground">通道分布 · 累计</div>
          ${CC_CHANNELS.map(c => `
            <div class="flex items-center gap-3 ${c.locked ? 'opacity-60' : ''}">
              <div class="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style="background:${c.color}14;color:${c.color}"><i data-lucide="${c.icon}" class="w-[18px] h-[18px]"></i></div>
              <div class="flex-1 min-w-0">
                <div class="flex justify-between text-xs mb-1">
                  <span class="font-bold ${c.locked ? 'text-muted-foreground' : 'text-foreground'}">${caT(c.id)}${c.locked ? ' · L4 解锁' : ''}</span>
                  <span class="font-bold ${c.amount > 0 ? 'text-foreground' : 'text-muted-foreground'}">${c.locked ? '🔒' : (c.amount > 0 ? fmt(c.amount) : '已解锁 · 暂无')}</span>
                </div>
                <div class="h-2 bg-secondary/50 rounded-full overflow-hidden">
                  <div class="h-full rounded-full transition-all duration-700" style="width:${(c.amount / maxChannel * 100).toFixed(1)}%;background:${c.color}"></div>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
        <div class="bg-white rounded-2xl border border-border/60 p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-xs font-bold text-foreground">近 6 个月收益趋势</div>
            <span class="text-[11px] text-muted-foreground">单位：元</span>
          </div>
          <div class="flex items-end gap-2 h-36 pt-2">
            ${CC_TREND.map(t => `
              <div class="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                <span class="text-[11px] font-bold text-[#8B0000]">${t.v}</span>
                <div class="w-full max-w-[34px] rounded-t-lg bg-gradient-to-t from-[#8B0000] to-[#C19A6B] transition-all duration-700" style="height:${Math.max(t.v / maxTrend * 78, 4)}%"></div>
                <span class="text-[11px] text-muted-foreground">${t.label}</span>
              </div>
            `).join('')}
          </div>
          <div class="text-[11px] text-muted-foreground bg-secondary/30 rounded-xl p-2.5">任务赏金为主要收入来源；开通课程分成（升 L4）可进一步提升收益天花板。</div>
        </div>
      </div>
    </div>
  `;
}
function ccRenderTransactions() {
  const list = ccState.transactions.filter(t => ccTxTab === 'all' || t.type === ccTxTab);
  const tabs = [
    { id: 'all', name: '全部' }, { id: 'money', name: '收益' }, { id: 'points', name: '戏份' }
  ];
  document.getElementById('cc-transactions').innerHTML = `
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h4 class="font-display text-lg font-bold text-foreground flex items-center gap-2">
          <i data-lucide="receipt" class="w-5 h-5 text-[#8B0000]"></i> 流水明细
        </h4>
        <div class="flex gap-1.5">
          ${tabs.map(t => `<button onclick="ccSetTxTab('${t.id}')" class="px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${t.id === ccTxTab ? 'bg-[#8B0000] text-white shadow-sm' : 'bg-secondary/50 border border-border text-foreground hover:bg-secondary'}">${t.name}</button>`).join('')}
        </div>
      </div>
      <div class="space-y-2 max-h-64 overflow-y-auto pr-1">
        ${list.length ? list.map(t => `
          <div class="flex items-center gap-3 p-3 rounded-xl bg-secondary/30">
            <span class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${t.amount >= 0 ? 'bg-emerald-500/10 text-emerald-600' : 'bg-red-500/10 text-red-500'}">
              <i data-lucide="${t.type === 'points' ? 'star' : (t.amount >= 0 ? 'plus' : 'minus')}" class="w-4 h-4"></i>
            </span>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-bold text-foreground truncate">${t.title}</div>
              <div class="text-[11px] text-muted-foreground">${t.time}</div>
            </div>
            <span class="text-sm font-bold flex-shrink-0 ${t.amount >= 0 ? 'text-emerald-600' : 'text-red-500'}">${t.amount >= 0 ? '+' : '-'}${t.type === 'money' ? '¥' + Math.abs(t.amount).toFixed(2) : Math.abs(t.amount) + ' 戏份'}</span>
          </div>
        `).join('') : '<div class="text-center text-sm text-muted-foreground py-8">暂无相关流水</div>'}
      </div>
    </div>
  `;
}
function ccSetTxTab(tab) {
  ccTxTab = tab;
  ccRenderTransactions();
  chIcons();
}
function ccRenderTasks() {
  const pool = ccState.tasks.filter(t => t.status === 'open').reduce((s, t) => s + t.bounty, 0);
  document.getElementById('cc-tasks').innerHTML = `
    <div class="space-y-3">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <h4 class="font-display text-lg font-bold text-foreground flex items-center gap-2">
          <i data-lucide="target" class="w-5 h-5 text-[#8B0000]"></i> 赏金任务大厅
          <span class="text-[11px] text-muted-foreground font-normal">官方认证需求 · 审核通过即结算</span>
        </h4>
        <span class="px-3 py-1 bg-amber-500/10 text-amber-600 text-[11px] font-bold rounded-full border border-amber-500/20">本期在悬赏池 ¥${pool.toLocaleString()}</span>
      </div>
      ${ccState.tasks.map(t => `
        <div class="bg-white rounded-2xl border border-border/60 p-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="px-2 py-0.5 bg-[#8B0000]/10 text-[#8B0000] text-[11px] font-bold rounded-full">${t.type}</span>
              <span class="text-[11px] text-muted-foreground">${t.diff} · 截止 ${t.deadline}</span>
            </div>
            <div class="font-bold text-xs text-foreground mt-1.5">${t.title}</div>
            ${t.status === 'progress' ? `
              <div class="h-1.5 bg-secondary/60 rounded-full overflow-hidden mt-2">
                <div class="cc-task-progress h-full bg-[#8B0000] rounded-full transition-all duration-[2400ms] ease-out" style="width:6%"></div>
              </div>
              <div class="text-[11px] text-[#8B0000] font-bold mt-1">创作提交中 · AI 预审 + 人工复核</div>` : ''}
          </div>
          <div class="flex items-center gap-3 flex-shrink-0 sm:flex-col sm:items-end sm:gap-0.5">
            <div class="text-lg font-bold text-[#8B0000] sm:text-right">¥${t.bounty}</div>
            <div class="text-[11px] text-muted-foreground">+${t.points} 戏份</div>
          </div>
          ${t.status === 'open' ? `
            <button onclick="ccClaimTask(${t.id})" class="px-4 py-2 bg-[#8B0000] text-white font-bold text-xs rounded-xl hover:bg-[#a00000] transition-all flex-shrink-0">认领</button>
          ` : t.status === 'progress' ? `
            <span class="px-4 py-2 bg-[#8B0000]/10 text-[#8B0000] font-bold text-xs rounded-xl flex-shrink-0">结算中…</span>
          ` : `
            <span class="px-4 py-2 bg-emerald-500/10 text-emerald-600 font-bold text-xs rounded-xl flex items-center gap-1 flex-shrink-0"><i data-lucide="check" class="w-3.5 h-3.5"></i> 已结算</span>
          `}
        </div>
      `).join('')}
      <p class="text-[11px] text-muted-foreground">规则：任务完成 = 赏金入可提现余额 + 戏份入账；分成比例创作者 85% / 平台 10% / 素材授权方 5%。</p>
    </div>
  `;
}
function ccClaimTask(id) {
  const t = ccState.tasks.find(x => x.id === id);
  if (!t || t.status !== 'open') return;
  t.status = 'progress';
  ccRenderTasks();
  chIcons();
  showToast('🛠️ 已认领「' + t.type + '」任务（demo 演示快速结算）');
  setTimeout(() => {
    const bar = document.querySelector('.cc-task-progress');
    if (bar) bar.style.width = '100%';
  }, 80);
  setTimeout(() => {
    t.status = 'done';
    ccState.withdrawable += t.bounty;
    ccState.monthEarnings += t.bounty;
    ccState.totalEarnings += t.bounty;
    ccState.points += t.points;
    ccState.transactions.unshift({ time: '刚刚', type: 'money', amount: t.bounty, title: '任务赏金 · ' + t.title });
    ccState.transactions.unshift({ time: '刚刚', type: 'points', amount: t.points, title: '任务完成奖励 · ' + t.type });
    ccRenderAll();
    showToast('💰 任务审核通过：赏金 +¥' + t.bounty + '，戏份 +' + t.points);
  }, 2700);
}
function ccOpenWithdraw() {
  const modal = document.getElementById('cc-withdraw-modal');
  modal.innerHTML = `
    <div class="bg-card border border-border rounded-3xl max-w-sm w-full overflow-hidden shadow-2xl" onclick="event.stopPropagation()">
      <div class="flex items-center justify-between p-4 border-b border-border/60">
        <h4 class="font-bold text-sm text-foreground flex items-center gap-2"><i data-lucide="banknote" class="w-4 h-4 text-[#8B0000]"></i> 提现</h4>
        <button onclick="ccCloseWithdraw()" class="w-8 h-8 rounded-full bg-secondary/60 flex items-center justify-center hover:bg-secondary transition-all"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <div class="p-4 space-y-4">
        <div class="bg-secondary/40 rounded-2xl p-3.5 flex items-center justify-between">
          <span class="text-xs text-muted-foreground">可提现余额</span>
          <span class="text-lg font-bold text-[#8B0000]">¥${ccState.withdrawable.toFixed(2)}</span>
        </div>
        <div class="space-y-2">
          <label class="text-xs font-bold text-foreground">提现金额</label>
          <div class="relative">
            <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-bold text-muted-foreground">¥</span>
            <input id="cc-wd-input" type="number" min="0" step="0.01" placeholder="最低 ¥100" class="w-full pl-8 pr-4 py-3 rounded-xl border border-border bg-secondary/30 text-sm text-foreground focus:outline-none focus:border-[#8B0000]">
          </div>
          <div class="flex gap-2">
            <button onclick="ccSetWdAmount(100)" class="flex-1 py-1.5 bg-secondary/50 border border-border rounded-lg text-xs font-bold text-foreground hover:bg-secondary transition-all">¥100</button>
            <button onclick="ccSetWdAmount(200)" class="flex-1 py-1.5 bg-secondary/50 border border-border rounded-lg text-xs font-bold text-foreground hover:bg-secondary transition-all">¥200</button>
            <button onclick="ccSetWdAmount('all')" class="flex-1 py-1.5 bg-secondary/50 border border-border rounded-lg text-xs font-bold text-foreground hover:bg-secondary transition-all">全部</button>
          </div>
        </div>
        <p class="text-[11px] text-muted-foreground leading-relaxed">规则：满 ¥100 起提 · T+7 个工作日到账 · 新账号分成阶梯释放（首月 30% / 次月 50% / 第三月 100%）。</p>
        <button onclick="ccSubmitWithdraw()" class="w-full py-3 bg-[#8B0000] text-white font-bold text-sm rounded-xl hover:bg-[#a00000] transition-all shadow-md">提交提现申请</button>
      </div>
    </div>
  `;
  modal.classList.remove('hidden');
  chIcons();
}
function ccCloseWithdraw(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('cc-withdraw-modal').classList.add('hidden');
}
function ccSetWdAmount(v) {
  const input = document.getElementById('cc-wd-input');
  if (input) input.value = v === 'all' ? ccState.withdrawable.toFixed(2) : v;
}
function ccSubmitWithdraw() {
  const input = document.getElementById('cc-wd-input');
  const amt = parseFloat((input.value || '').trim());
  if (isNaN(amt) || amt <= 0) { showToast('⚠️ 请输入提现金额'); return; }
  if (amt < 100) { showToast('⚠️ 最低提现金额 ¥100'); return; }
  if (amt > ccState.withdrawable + 0.001) { showToast('⚠️ 超出可提现余额'); return; }
  ccState.withdrawable = Math.round((ccState.withdrawable - amt) * 100) / 100;
  ccState.transactions.unshift({ time: '刚刚', type: 'money', amount: -amt, title: '提现申请 · T+7 个工作日到账' });
  document.getElementById('cc-withdraw-modal').classList.add('hidden');
  ccRenderAll();
  showToast('🏦 提现申请已提交，预计 T+7 到账');
}

/* ============================================================
 * 统一入口：openCreatorSub() 的钩子回调
 * ============================================================ */
window.onCreatorSubEnter = function (id) {
  switch (id) {
    case 'jubensha': jbsInit(); break;
    case 'restore': rstInit(); break;
    case 'zhiku': zkInit(); break;
    case 'skills': skInit(); break;
    case 'creator-assets': caInit(); break;
    case '3dgs': gsInit(); break;
    case 'qingju': qjInit(); break;
    case 'workshop': wsInit(); break;
    case 'agent-matrix': amInit(); break;
    case 'creator-center': ccInit(); break;
  }
};
