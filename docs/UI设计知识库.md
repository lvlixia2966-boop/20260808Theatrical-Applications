# UI 设计知识库

> 版本 v1.0 · 2026-09-10
> 来源：四路 Agent 研究汇总（参考网站盘点 / 设计原则体系 / 文旅演出 UI 模式 / 微交互与中式氛围）
> 用途：本项目 UI 迭代的「找参照 → 对规范 → 抄模式」一站式知识库；每次改版先查 §6 对照表

---

## 1. 参考网站索引（找参照去哪）

**概念稿 vs 上线站，用途不同**：概念稿（Dribbble/Behance）找风格方向；上线站库（Awwwards/Siteinspire/Land-book）抄可落地版式；Mobbin 抄流程细节；设计系统抄规范。

| 网站 | 定位 | 最适合拿来抄什么 |
|---|---|---|
| Dribbble | 设计师概念稿社区（单张视觉） | 组件质感、视觉风格（勿照抄布局逻辑） |
| Behance | 完整项目案例集 | 多页面体系、文化类专题项目推导 |
| Awwwards | 获奖上线站评审榜 | 转场动效、scroll storytelling（按行业筛 SOTD） |
| Siteinspire | 上线站精选，按风格/行业标签 | 版式与字体排印；**直接用其 galleries-and-museums 分类** |
| Land-book | 上线落地页精选 | 整页结构、CTA、定价区 |
| Godly | 炫技/创意站 | 3D、WebGL、大胆视觉 |
| Httpster | 按排版风格归类 | 字体排印、复古大字风格 |
| Mobbin | 真实 App 截图按流程分类 | **收银台、列表/空态、购票流细节** |
| Screenlane / Pttrns | 按组件类型归类截图 | 单组件（导航、卡片、Feed） |
| Landingfolio / Lapa Ninja | 落地页按区块拆解 | 单区块写法、行业整页模板 |
| Dark Mode Design / dark.design | 暗色站精选 | 暗色配色与发光层次 |
| Material 3 / Apple HIG / Ant Design | 设计系统规范 | 色彩/状态/间距体系、控件行为 |
| shadcn/ui / Tailwind UI | 可复制源码组件（Tailwind 系） | 直接复制改代码（本项目技术栈同源） |
| Japan Web Design Gallery | 日式站精选+点评 | 留白、竖排、版式（对中式氛围有参考） |

**检索策略**（挖文化/文旅/演出参照的现成关键词）：
- 中：① 国风 UI 网站设计 博物馆 Behance ② 博物馆 官网 设计案例 2026 ③ 演出购票 小程序 UI 设计 ④ 戏曲 剧场 购票界面 座位选择 设计 ⑤ 演唱会 陪伴 App 界面设计
- 英：① museum website design site:siteinspire.com ② chinese traditional culture web design behance ③ opera theatre seat selection ticketing UI dribbble ④ event companion app live UI case study ⑤ theatre booking flow UI mobbin

## 2. 设计原则 Checklist（20 条，逐条可检查）

**排版**
1. 字号出自模数阶梯（16 基准 × 1.2/1.25）：16/20/25/31/39/49，出界值不通过
2. 行高与字号成反比：正文 1.5–1.75、标题 1.1–1.2；大标题字距 -0.02~-0.03em
3. 中西文混排：Latin 在前 CJK 回退后（Inter, "PingFang SC"…）；中西文间 ~0.15em；中文正文禁 letter-spacing，行高 ≥1.5
4. 字体 ≤2 族：UI 用 sans、长文标题可 serif，x-height 相近；禁两个装饰性字体同屏

**间距与栅格**
5. 8pt 网格：所有 padding/margin/gap 为 8 的倍数（微调允许 4）
6. 间距阶梯封闭：4/8/12/16/24/32/48/64
7. 正文行宽 45–75ch（66 最佳）：`max-width: 66ch`
8. 接近性分组：组内间距 < 组间，比值 ≥1:2

**色彩**
9. 60-30-10：中性背景 60%、品牌色 30%、强调 ≤10%；主 CTA 每屏 ≤1 个
10. token 两层：primitive（gray-500）禁直写组件，组件只用 semantic（bg-surface/text-primary）
11. 语义色不挪用：success/warning/danger/info 各表其意
12. 深色模式：背景禁纯黑（#121212 类）；层次用表面明度递升不用阴影；正文 ~87% 白；品牌色降饱和

**可访问性**
13. 对比度：正文 ≥4.5:1（AA）；大字 ≥3:1；WebAIM 校验
14. 触控目标 ≥44×44px（iOS）/48dp（Android）
15. 状态不只靠颜色：必配图标或文字标签

**层级与可用性**
16. 相似性：同类卡片尺寸/圆角/边框一致；可点元素反馈统一
17. 闭合性：轮播露出相邻卡边缘，暗示可滑
18. 每屏一个视觉焦点：相邻层级字号差 ≥1 档（字号+字重+色彩三重拉开）
19. 状态可见（Nielsen #1，最常违反）：任何操作 ≤400ms 给反馈（loading/success/error 齐备）
20. 一致性（违规频率最高）：同一操作全站同文案同位置；错误提供恢复出口；破坏性操作二次确认

## 3. 文旅/演出类 UI 模式库

| 模式 | 出处 | 关键细节 |
|---|---|---|
| 海报头图+吸底信息条 | SeatGeek | 全宽剧照背景，紧贴其下「日期·场馆·起价」信息带，CTA 吸底常驻 |
| 比价染色选座 | SeatGeek | 座位图按性价比染色（绿=划算）+列表/地图联动 |
| 横滑场次选择器 | 大麦/TodayTix | 日期 pill 横排+时间 tab，选中刷新票档；未选时 CTA 置灰引导 |
| 实时字幕 Second-screen | SurtitleLive/Captify | 只读、超大字号、黑底白字，不做交互 |
| 当前曲目高亮 | 音乐会 companion 通用 | 节目单当前条放大+主色+自动滚动，其余灰化 |
| 编号触发音频 | 大英博物馆 Audio App | 输展品编号即播 + Favorites 收藏 |
| 馆内三分区 | Bloomberg Connects | 首页场馆卡 → 入馆切 Explore/Guides/Tours |
| 路线二选一 | 数字故宫 | 快速游/深度游模式 + 无障碍标识 |
| 订单聚合时间轴 | TripIt | 按天分组垂直时间轴：时间图标+标题+确认号 |
| 白底商品卡四件套 | 故宫文创/大英商店 | 图 3/4 + 名称单行省略 + 主色价格 + **角标只放 1 个**（角标多则失效 NNg） |
| 文物溯源标注 | 故宫文创官网 | 卡片注明取材文物+原图故事 = 天然授权背书 |
| 集章地图 | 通用+Codrops | 印章盖在地图点位，可拖动放大检视，集满解锁 |

**反模式（避雷）**
1. 首屏角标过载：热销/折扣/限量 4+ 角标打架，主标题被淹没
2. CTA 竞争：详情页多个同级按钮无主次
3. 票档状态不明：售罄/紧张仅灰字，无颜色图标语义
4. 时间轴无「当前态」：进行中与未来条目样式相同
5. 语言切换用国旗或藏太深；切换后币种/日期格式不同步

## 4. 微交互与氛围规则

**微交互数值**
- 时长：hover/按压 100–150ms；进场展开 200–300ms；退场更快（100–200ms）；<100ms 无意义，>1s 即卡顿
- 缓动：进场 ease-out `cubic-bezier(0.2,0,0,1)`、退场 ease-in、屏内位移 ease-in-out
- 卡片阴影：静置 2dp→hover 8dp + translateY(-2~4px)；双层公式 = 紧贴 key（y1-2px, blur 3px）+ 大范围 ambient（y8px, blur 24-48px, 低不透明度）
- Toast：显示 2–7s，hover 暂停；同屏 1–3 条；≤3 行；aria-live 播报
- 骨架屏：布局可预测且加载 >300ms 用骨架（与真实元素同形防跳动，shimmer 1.5-2s）；<300ms 不显示 loading
- 可访问性：`prefers-reduced-motion` 降级为纯 opacity；1 秒内闪烁 ≤3 次（WCAG 2.3.1）；循环装饰 ≤5s
- 空状态公式：1 个插画 + 「这里是什么」+「为什么是空的」+ 动词开头 CTA；搜索无结果给替代建议

**渐变与光效**
- Aurora：低饱和底上叠 2-3 个大半径模糊 radial，全页色相 ≤3，漂移 ≥20s 循环
- 必叠 3%-5% 噪点纹理去塑料感；追光只给 1 个主 CTA 或主视觉

**中式氛围克制用法 6 条**
1. 留白优先：版面留白 ≥50%，写意不堆符号
2. 印章只做点睛：全页 ≤2 处、单枚 < 视口 1%、朱红只在米白/灰底上
3. 纹样垫底不抢戏：透明度 3%-8% 单色低对比，拆解重构后用，绝不原样满版平铺
4. 色彩取自材质：红墙/黄瓦/朱门/金钉/宣纸/墨，一主一辅一点缀 70/25/5，拒绝高饱和国风撞色
5. 书法字体限量：只用于大标题或一句 slogan，正文用现代无衬线
6. 叙事代替贴图：文化感来自方言文案、典故、拟人语气，不是龙纹祥云叠加

## 5. 检索来源汇总

四路研究全部基于以下站点的一手信息：[Mobbin](https://mobbin.com)、[Siteinspire](https://www.siteinspire.com/websites/category/galleries-and-museums)、[Land-book](https://land-book.com/)、[Dark Mode Design](https://www.darkmodedesign.com/)、[typescale.com](https://typescale.com/)、[Baymard 行宽](https://baymard.com/blog/line-length-readability)、[Atmos 色彩 tokens](https://atmos.style/blog/dark-mode-ui-best-practices)、[W3C 中文排版 CLREQ](https://www.w3.org/TR/clreq/)、[NN/g 启发式](https://www.nngroup.com/articles/ten-usability-heuristics/)、[NN/g 动效时长](https://www.nngroup.com/articles/animation-duration/)、[Material 3 Motion](https://m3.material.io/styles/motion/easing-and-duration)、[Codrops 集章](https://tympanus.net/codrops/2026/06/09/building-an-interactive-digital-stamp-collection-with-shaders-postcards-and-playful-inspection/)、[数字故宫](https://www.dpm.org.cn/bottom/friend.html)、[故宫文创](https://www.dpm.org.cn/Creative.html)、[Bloomberg Connects 评析](https://ixd.prattsi.org/2025/02/design-critique-bloomberg-connect/)、[Smashing 语言选择器](https://www.smashingmagazine.com/2022/05/designing-better-language-selector/)。

## 6. 本项目对照自查（2026-09-10 快照）

**✅ 已符合**
- 色彩取自材质（红金宣纸体系 70/25/5）、印章点睛 ≤2 处、纹样垫底 3%-8%（§4 中式 2/3/4 条）
- 深色模式非纯黑、表面明度递升（§2.12）
- 零打扰演出中短卡纪律、reduced-motion 降级、空态公式（竞答规则页/大厅空态）
- 图标语言已统一 Lucide；入场卡同构（§2.16 相似性）

**⚠️ 待改进（下次改版优先）**
1. **字号阶梯未模数化**：11/12/13/14px 混用 → 收敛到 12/14/16/20/32（§2.1）
2. **间距非严格 8pt**：存在 6/10/14/18 等值 → 逐步归拢（§2.5/6）
3. **文本对比度待校验**：字幕区 amber-on-dark、水印上正文 → WebAIM 全量过一遍（§2.13）
4. **触控目标**：语言 chips、字幕语言切换 ≈32px 高 → 移动端放大到 44px（§2.14）
5. **CTA 主次**：个别卡片双主色按钮（伴游+开始提问）→ 每屏保留 1 个主 CTA（§2.9）
6. **当前态缺失**：节目单时间轴的「上演中」已做，但收播后的时间轴无「回看态」（§3 反模式 4）

> 使用约定：每次 UI 迭代开工前，先扫 §6 对应条目；新增界面按 §2 checklist 自查；找参照按 §1 索引与检索策略。
