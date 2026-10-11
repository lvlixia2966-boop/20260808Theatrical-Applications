# 川蜀大剧院 语音导览系统（云端部署包）

本包仅包含项目前后端（backend + frontend + admin）。**全部 AI 能力已切换豆包云**
（本地不再部署 FunASR / CosyVoice / GPT-SoVITS）：
- 大模型 / 翻译 / 视觉 / 向量：**火山方舟 Ark**（OpenAI 兼容 REST），`.env` 配置 `ARK_API_KEY`
- 语音识别 / 语音合成：**豆包语音 openspeech**（流式 ASR + 流式/整段 TTS），配置 `DOUBAO_SPEECH_APP_ID` / `DOUBAO_SPEECH_ACCESS_TOKEN`
- 凭据未配置时各引擎自动降级（mock 演示 / 回退原文），不阻断主流程

## 近期更新（2026-09 · 豆包化改造 + Agent 伴游）

### 1. 豆包引擎层（services/doubao/）
- `ark_client`：LLM / 翻译 / 视觉多模态 / 向量 / 生图统一客户端；`asr_stream`/`asr_oneshot`：大模型流式 ASR；`tts_stream`：单向流式 TTS（RTC 低延迟）
- 原 FunASR / CosyVoice / GPT-SoVITS / Edge / Gemini 通路已全部移除
- 用量计量 `usage_meter`：ASR 秒数 / 翻译与 TTS 字符 / LLM token 全部落 `usage_logs`，月度预算 `DOUBAO_MONTHLY_BUDGET`（超 80% 管理端告警）

### 2. WebRTC 双端实时翻译（报价单 #15）
- 讲解员端（admin「实时翻译」页）创建会话生成游客二维码；游客扫码进入首页实时翻译视图
- aiortc 网关（`rtc_gateway`）：Opus → PCM16k → 豆包流式 ASR → 双向翻译链路（`rtc_pipeline`）→ 字幕广播 + 游客语 TTS
- 断线 60s 内同令牌重连复用会话；并发上限 `RTC_MAX_SESSIONS`

### 3. Agent 伴游 + 知识库（报价单 #10-14）
- 知识库三层结构：知识节点 → 知识单元 → 多语言译文，附实体图谱与验收问集
- 混合检索（`retrieval_service`）：BM25 + 向量余弦 → RRF 融合，索引变更自动重建
- Agent 伴游（`agent_service`）：RAG 召回 → 豆包 LLM（流式）→ 引用校验 → 安全降级话术；前端 `agent-companion.js` 支持文本/语音提问

### 4. 管理后台运营工具（报价单 #17/#18/#21）
- 角色权限：super（全部）/ ops（统计/直播/会话）/ content（知识库内容），后端 `require_role` 门禁 + 前端按角色装配菜单
- 运营统计页：豆包月度用量汇总、伴游会话量、用量明细
- 知识管理页：节点/单元/译文/实体/问集 CRUD、试查、一键生成向量
- 用户管理页（仅 super）：账号创建与角色分配

### 5. 部署与自检
- 一键部署脚本 `tools/deploy_doubao_upgrade.py`（同步 → docker cp → 重启 → 探活 → 容器内自检）
- 连通性自检 `backend/tools/check_connectivity.py`：数据库 / 方舟 LLM / 向量 / 豆包 TTS / ASR / aiortc 逐项 PASS/SKIP/FAIL
- 首次部署容器需补装依赖：`docker exec chuan-guide pip install aiortc websockets httpx pydantic-settings`

## 近期更新（2026-08）

### 1. 耳机准入流程（ble-guard.js）
- 扫码进入服务页后为**全屏准入页**：仅可选择语言 + 连接专用蓝牙耳机（namePrefix=`CHUAN`），连接成功才能进入正式页面
- 连接后读取电量（GATT 0x180F/0x2A19），60s 轮询；低于 20% 提示充电
- 蓝牙断连：自动暂停页面全部音频、派发 `ble:disconnected` 事件（各音频模块自行清理）、回退准入页并 3s 间隔自动重连
- 耳机为付费凭证：**租用在剧院门口柜台线下办理，线上不收费**；开发调试用 `?demo=1` 旁路

### 2. 文创商城支付（沙盒演示模式）
- 后端新增支付模块：`/api/payments`（渠道查询/下单/查单/模拟确认/PayPal 扣款），订单表 `payment_orders`
- 网关抽象：`mock_gateway`（沙盒模拟）+ `paypal_gateway`（PayPal REST v2）；在 `backend/.env` 配置 `PAYPAL_CLIENT_ID/PAYPAL_SECRET` 即启用 PayPal 沙盒，未配置自动降级模拟
- 前端新增：`cart.js` 购物车（浮动球：文创视图常显、其他视图有商品才显）、`checkout.js` 收银台（微信/支付宝/PayPal 三渠道，iframe 沙盒收银 + 轮询感知支付成功）、`mock-cashier.html` 收银台页
- 微信/支付宝真实商户号就绪后替换 mock_gateway 即可上线

### 3. 多语言与文案
- 剧场介绍 16 语种全部手写预置（zh/en/ja/ko/es/fr/de/ru/hi/ar/pt/it/vi/th/tr/id），动态翻译有「医院词黑名单」后检
- 介绍**不含地址交通信息**（用户扫码时已在剧院内），仅保留时长/取票/迟到入场提示
- 新增川剧术语韵译库（`glossary_service.py`）：关键术语优先整句韵译

### 4. 字体服务器自托管
- 现场/境内网络无法访问 Google Fonts CDN，全部字体改为服务器直接提供（`frontend/assets/fonts/`）
- Ma Shan Zheng（本地 TTF）+ Noto Serif SC 700/900 + Outfit 400/600/800（woff2 子集，按需加载）
- 统一入口 `assets/fonts/fonts.css`，index.html 已移除 Google Fonts 引用

### 5. UI 修复
- 清理 i18n 中文残留：文创子导航、个人中心、剧场介绍按钮、视图切换 toast 全部接入 7 语种词典
- toast 移至底部居中、修复导航/印章徽章断行（Cultural IP 换行问题）

## 目录结构
```
shuyin/
├── backend/          FastAPI 后端
│   ├── app/          业务代码（含 services/payment/ 支付网关包）
│   ├── run.py        启动入口（本地）
│   ├── seed.py       初始化管理员与演示数据
│   ├── requirements.txt
│   └── .env          云服务器配置（已生成随机 JWT KEY）
├── frontend/         扫码页 / 首页 / 收银台（assets/fonts/ 为自托管字体）
├── admin/            管理后台
├── tools/            一次性运维脚本（字体下载/远程部署）
└── deploy/           部署辅助（start.sh / systemd / nginx）
```

## 一、环境准备（Linux）
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

## 二、上传解压并安装依赖
```bash
# 将本 zip 上传到服务器后
sudo mkdir -p /opt && sudo mv shuyin /opt/shuyin
cd /opt/shuyin
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

## 三、初始化数据库与管理员
```bash
cd /opt/shuyin/backend
.venv/bin/python seed.py            # 创建管理员 admin/admin123 与演示数据
# 如重跑并清空：.venv/bin/python seed.py --reset
```

## 四、启动后端
```bash
# 方式一：直接启动
cd /opt/shuyin/backend && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 方式二：用 systemd 守护（推荐）
sudo cp /opt/shuyin/deploy/shuyin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shuyin
sudo systemctl status shuyin
```

## 五、HTTPS 反向代理（重要）
Web Bluetooth 在非 localhost 环境**必须 HTTPS**，因此建议配置 Nginx + 证书：
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
# 参考 deploy/nginx.conf 调整反代配置
```
配置完成后，将 `backend/.env` 中 `CORS_ORIGINS` 改为你的域名，并重启服务。

## 六、访问
- 首页 / 扫码页：`https://your-domain.com/` 与 `https://your-domain.com/guide`
- 管理后台：`https://your-domain.com/admin/`（账号 admin / admin123，首次登录后请修改）

## 七、语音设置
在管理后台「语音设置」中填写阿里云 TTS 参数并启用，保存后合成自动优先走阿里云，
未启用或参数不全时回退 Edge TTS。
