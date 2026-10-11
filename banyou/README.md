# 凉山伴游 · 纯伴游导览系统

面向景区现场游客的**纯伴游模式**应用：无购票、无商城弹窗、无社交，只做
「地图导览 + 到点自动讲解 + 路线伴游引导」，并以**不打扰**的方式顺带解决
文创售卖——好物入口安静地待在手边，需要时一点即达，伴游进行中完全隐藏。
整体采用 **API 接入**方式——游客端 / 小程序 / 三方平台一律通过开放 API
读取内容，全部内容（景区、点位、讲解稿、路线、地图底图、公告文案、文创商品）
由管理后台配置，保存后实时生效。

已预置**凉山彝族自治州** 10 个景区、50 个讲解点位、11 条伴游路线、
12 件文创好物的完整内容。

## 快速启动

Windows 一键启动：双击 `banyou/start.bat`（自动检查依赖、首次运行自动建库灌数据、启动服务）。

手动方式：

```bash
cd banyou/backend
pip install -r requirements.txt        # 与主项目后端同栈，本机已有依赖可跳过
python seed_liangshan.py               # 灌入凉山州内容 + 管理员（--reset 全量重建）
python run.py                          # http://0.0.0.0:8300
```

| 入口 | 地址 | 说明 |
|---|---|---|
| 游客端 H5 | http://127.0.0.1:8300/ | 手机体验最佳；桌面端用「模拟到达」体验伴游 |
| 管理后台 | http://127.0.0.1:8300/admin/ | admin / 强口令（种子时经 ADMIN_INIT_PASSWORD 指定或随机生成见输出） |
| 接口文档 | http://127.0.0.1:8300/docs | Swagger UI |
| 健康检查 | http://127.0.0.1:8300/api/health | |

> 生产部署：非 localhost 环境下浏览器定位（Geolocation）**必须 HTTPS**，
> 请参照主项目 `deploy/nginx.conf` 配置证书后再对外。

## 游客端功能（纯伴游 · 单页对话）

**应用只有一个页面：AI 伴游对话**。耳机准入通过后即进入对话，没有首页/
景区列表/详情页——知识库和定位在对话之下工作，好物与设置经标题栏按钮以
浮层打开。

- **耳机准入**（与主项目同一套流程）：进入应用先过全屏准入页——选讲解语言 +
  连接租赁专用耳机（蓝牙名前缀 `CHUAN`）后才解锁；连接后读取电量（60s 轮询，
  低于 20% 提示充电）；断连自动停止全部语音并回退准入页，耳机回到范围内 3s
  间隔自动重连。开发旁路：`?demo=1` 或准入页「演示模式进入」
  （上线将 `frontend/assets/js/ble.js` 中 `SKIP_ENABLED` 置 false）

- **AI 伴游 · 纯对话模式**（核心，应用唯一页面）：
  - **耳机语音沟通为主**：点大麦克风说话 → 豆包 ASR 转文字 → 知识库应答 →
    豆包 TTS 播报回耳机（Audio 输出自动路由到已连接耳机）；讲解员的每句回答
    都自动播报。文字输入保留为兜底（服务端 ASR 未配置时自动落到浏览器
    语音识别，再退文字）
  - 讲解员结合**你此刻的位置 + 景区知识库**作答：讲景点故事、指路下一站、
    查门票开放时间、推荐玩法、找吃的
  - 位置获取保留：GPS 持续跟踪，首次定位自动锁定所在景区；顶部实时显示
    「距某点位多远」；进入点位触发半径时**主动推送该点位讲解**（自动语音
    播报，可在设置关闭）
  - **对话内富卡片**：讲到景点配**美景卡片**（实拍图 + 名称 + 停留建议，点击继续追问），
    聊到文创配**购物卡片**（商品图 + 价格，点击直达选购浮层）；
    换景区时推送**景区卡片**
  - 无定位也能用：直接说「我在泸沽湖」，对话即锁定景区上下文
  - 知识库即业务库：讲解稿、贴士、门票、路线全部来自管理后台配置的内容，
    无需单独维护语料；后台改完实时生效
- **标题栏浮层**：右上角「好物」打开文创售卖浮层（不打扰原则：无购物车、
  无注册，直接购买 + 沙盒收银，我的订单随时回查）；「设置」打开语言 /
  到站自动播报 / 语速 / 耳机状态浮层

## 管理后台功能

- **数据概览**：景区 / 点位 / 路线规模
- **景区管理**：全字段 CRUD，封面图上传，上下线
- **点位管理**：CRUD + **地图选点**（点击地图回填坐标）+ 中英讲解稿 +
  人工录音/图片上传 + 到站触发半径
- **路线管理**：CRUD + **排点器**（左右两栏，顺序即游客端播报顺序）
- **文创商品**：CRUD + 商品图上传 + 三级关联（全域好物 / 关联景区 / 关联点位，
  关联点位的仅在对应讲解页露出），划线价、库存、上下架
- **订单管理**：全量订单查询（状态筛选）、发货 / 取消
- **应用设置**：应用名称 / 标语 / 公告 / 服务电话；**地图底图切换**
  （OSM / 高德街道 / 高德卫星 预设，含 WGS-84 ↔ GCJ-02 坐标系声明，
  前端自动纠偏）；到站触发半径 / 自动播放 / 语速默认值
- **API 接入**：开放接口与鉴权说明
- **账号**：修改密码

## API 接入（整体采用 API 方式）

### 开放接口（只读，游客端 / 小程序 / 三方平台）

```
GET /api/v1/bootstrap              # 冷启动一次拉全：公开设置 + 区域列表
GET /api/v1/regions                # 区域列表
GET /api/v1/scenic-areas           # 景区列表 ?region=liangshan&city=盐源县&keyword=泸沽湖
GET /api/v1/scenic-areas/{id}      # 景区详情（含点位与路线）
GET /api/v1/spots/{id}             # 点位详情（多语言讲解稿 / 音频 / 坐标 / 触发半径）
GET /api/v1/routes/{id}            # 伴游路线（按 seq 有序点位）
GET /api/v1/nearby?lat=&lng=       # 按距离排序的附近景区
POST /api/v1/companion/chat        # AI 伴游对话 {message, lat?, lng?, area_id?, history?}
GET  /api/v1/companion/locate      # 定位 → 最近点位/所属景区/是否到站 ?lat=&lng=
GET  /api/v1/companion/voice-status  # 服务端语音能力探测 {asr, tts}
POST /api/v1/companion/asr         # 录音 → 文本（豆包 ASR，multipart 字段 audio）
POST /api/v1/companion/tts         # 文本 → MP3（豆包 TTS，{text, lang, rate}）
GET /api/v1/products               # 文创好物 ?spot_id=(点位关联) ?area_id= ?keyword=
GET /api/v1/products/{id}          # 商品详情
POST /api/v1/orders                # 下单 {visitor_id, items:[{product_id, qty}]}（服务端计价）
GET  /api/v1/orders?vid=           # 我的订单
GET  /api/v1/orders/{id}?vid=      # 订单详情
POST /api/v1/orders/{id}/pay       # 沙盒支付 {visitor_id, channel}（置 paid 并扣库存）
```

字段契约见 `backend/app/api/content.py` 的 `ser_*` 序列化函数；
Swagger 全量定义见 `/docs`。

### 管理接口（JWT）

前缀 `/api/admin`：`POST /login` 签发 token，此后
`Authorization: Bearer <token>`。覆盖区域 / 景区 / 点位 / 路线 / 文创商品 CRUD、
`PUT /routes/{id}/stops` 路线排点、`GET /admin/orders` + `PUT /orders/{id}` 订单管理、
`GET|PUT /settings` 应用设置、`POST /uploads` 素材上传（图片 / 音频，≤20MB，落盘 `/uploads/`）。

## 已预置的凉山州内容

| 景区 | 县市 | 点位/路线 |
|---|---|---|
| 邛海泸山景区（4A） | 西昌市 | 9 / 2（环湖湿地线、泸山人文线） |
| 泸沽湖景区（4A） | 盐源县 | 9 / 1（环湖经典线） |
| 螺髻山景区（4A） | 普格县 | 7 / 1（高山湖泊徒步线） |
| 西昌卫星发射中心 | 冕宁县 | 4 / 1（航天研学线） |
| 会理古城（4A） | 会理市 | 5 / 1（历史漫游线） |
| 彝海景区（4A） | 冕宁县 | 3 / 1（红色教育线） |
| 灵山景区（4A） | 冕宁县 | 3 / 1（祈福森林线） |
| 马湖景区 | 雷波县 | 4 / 1（环湖休闲线） |
| 越西文昌故里景区（4A） | 越西县 | 3 / 1（文昌文化线） |
| 谷克德高原湿地 | 昭觉县 | 3 / 1（花海草原线） |

文创好物 12 件：彝族漆器、彝绣香囊、苦荞茶、摩梭手工花腰带、盐源苹果干、
螺髻山杜鹃标本书签、长征火箭模型、会理绿陶茶具、彝海结盟徽章、灵山蜂蜜、
马湖银鱼干、火把节帆布包——多数已关联到对应景区/点位。
**12 件全部配**网络搜索的演示商品图（后台「文创商品 → 编辑 → 商品图上传」可随时替换）。

> 点位坐标为演示用近似值，讲解稿为可运营内容草稿；上线前请在后台
> 「点位管理 → 地图选点」逐点校正坐标，并按需替换人工录音。
> 景区封面（10 张）与商品图（12 张）均为网络搜索的演示图
> （见 `backend/uploads/images/credits.json` 来源清单），
> **上线前请替换为自有版权或已授权图片**；替换方式：后台「景区管理 / 文创商品 → 编辑 → 图片上传」。

## 目录结构

```
banyou/
├── backend/               FastAPI 后端（与主项目同栈：SQLAlchemy + JWT + 静态托管）
│   ├── app/
│   │   ├── api/           开放 API（content）+ 管理 API（auth/admin_content/admin_settings）
│   │   ├── core/          JWT / bcrypt
│   │   ├── models/        区域/景区/点位/路线/管理员/设置
│   │   ├── schemas/       Pydantic 请求模型
│   │   ├── services/      geo（距离/方位角）+ settings（KV 白名单）
│   │   └── main.py        路由装配 + 静态托管 + MIME 兜底 + no-cache 中间件
│   ├── seed_liangshan.py  凉山州内容种子（10 景区 / 50 点位 / 11 路线）
│   └── banyou.db          SQLite 单文件（seed 后生成）
├── frontend/              游客端 H5（ES Module 自治模块，零 CDN 依赖）
│   └── assets/js/         api/geo/tts/ui/map + views(home/area/spot/follow/settings)
└── admin/                 管理后台 SPA（原生 JS，Leaflet 选点 + 排点器）
```

## 设计约定（与主项目一致）

- **高内聚低耦合**：前端功能均为自治 ES Module，CustomEvent 通信；后端 service 域分离
- **零外网 CDN 依赖**：Leaflet / lucide 全部自托管（`assets/vendor/`），现场弱网可用
- **内容与代码分离**：游客端代码不含任何业务硬编码，一切经 `/api/v1`
- **优雅降级**：无定位 → 手动到站；无录音 → TTS；无英文稿 → 回退中文

## 回归测试

```bash
cd banyou/backend
python tests/test_companion_cards.py     # 对话卡片回归：导航边界用例×3 + 无定位点名讲解（参数化：权限缺失/拒绝/显式null）
python tests/test_order_flow.py          # 文创订单回归：下单计价→沙盒支付→库存扣减→我的订单（测试数据自动复原）
python tests/verify_sync_and_laststop.py # 差异清单同步核查 + 单站点路线（单末站）末站分支实测（自动造数与清理）
python tests/check_image_paths.py        # 图片路径一致性：credits/磁盘/数据库/种子/代码 五方核对
```

四个脚本零依赖可直跑（对话卡片脚本也可被 pytest 收集）；跑对话/订单脚本前需先启动服务。

## 远端备份（待配置）

仓库目前**仅有本地单副本**，需要配置一个私有远端做异地备份。等待提供的信息与格式：

- **远端 URL**（任选其一格式，Gitee / GitLab / 自建 Gitea 均可）：
  - `https://<host>/<group>/<repo>.git`（HTTPS，首次 push 需输账号 + 访问令牌）
  - `git@<host>:<group>/<repo>.git`（SSH，需先配好密钥）
- 示例：`git@gitee.com:yourname/banyou.git`
- 拿到后执行一次即可：
  ```bash
  cd banyou
  git remote add origin <远端URL>
  git push -u origin master
  ```

## 已知事项

- **耳机语音链**（说话 → ASR → 应答 → TTS 回耳机）需在 `backend/.env` 配置
  `DOUBAO_SPEECH_APP_ID` / `DOUBAO_SPEECH_ACCESS_TOKEN`（与主项目共用同一组
  凭据）。未配置时自动降级：麦克风走浏览器语音识别（Chrome 可用），
  播报走本机 TTS，文字输入始终兜底
- AI 伴游默认使用**本地规则引擎**（知识库检索 + 意图路由，离线可用）；在
  `backend/.env` 配置 `ARK_API_KEY` 后自动升级为豆包 LLM 组织语言
  （知识内容仍只来自本地库注入，防编造），调用失败自动回退规则引擎
- 耳机准入的 Web Bluetooth 需要 **HTTPS（或 localhost）+ Chrome/Edge/Android**；
  iPhone 与微信内置浏览器不支持，准入页会引导换浏览器或到服务台
- 支付为**沙盒模拟**（点击即模拟成功并扣库存）；微信/支付宝真实商户号就绪后，
  替换 `backend/app/api/product.py` 中 `pay_order` 的实现即可（主项目后端已有
  mock/paypal 网关抽象可参照）
- 高德 / 天地图瓦片为 GCJ-02 坐标系：后台切换瓦片预设时会同步声明坐标系，
  前端对 GPS（WGS-84）自动纠偏，点位不会漂移
- iOS Safari 的 TTS 需要用户首次交互后才能发声（系统限制），首次播放请点一次按钮
- 泸沽湖为川滇共辖景区，环湖路线含云南侧点位，属正常运营口径
