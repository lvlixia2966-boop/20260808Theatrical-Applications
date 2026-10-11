# quiz 后端化 · 任务分解

版本：v1.0（2026-09-29）　状态：待评审，未写代码
前置：商品后端化已完成（T1-T7 + 冒烟工具，待部署）。本表结构与 API 沿用同一套模式（FastAPI + SQLAlchemy + require_role + ApiResponse）。

## 一、现状

| 项 | 现状 | 问题 |
|---|---|---|
| 题库 | 10 题硬编码在 `frontend/assets/js/quiz.js` 的 `BANK` 数组（zh/en 双语：`{q:{zh,en}, opts:[{zh,en}×3], a:正确下标}`） | 换题/增题需改代码并部署 |
| 抽题 | 每轮 `shuffle(BANK)` 抽 5 题，答对 ≥3 通关（`PASS_LINE=3`） | 题池小，固定 10 题 |
| 结果 | 最佳成绩仅 `localStorage('chuan_quiz_best')`；通关派发 `app:quiz:passed` 由 passport.js 授「懂戏之人」印章 + 文创九折码 | 无答题数据，路线图的运营分析/进度云同步缺数据源 |
| 管理 | 无题库管理 | 运营不可自助 |

## 二、表结构

**quiz_questions（题库）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| question_zh | VARCHAR(255) NOT NULL | 题干（中） |
| question_en | VARCHAR(255) | 题干（英，可空则回退中文） |
| options_zh | TEXT NOT NULL | 选项 JSON 数组（中文），如 `["表演特技","唱腔流派","乐器演奏"]` |
| options_en | TEXT | 选项 JSON 数组（英文，可空） |
| answer_idx | INTEGER NOT NULL | 正确下标（0-2，与现有 BANK 的 `a` 一致） |
| tag | VARCHAR(16) | 题签：绝技 / 历史 / 礼仪 / 常识（现状 10 题可归入） |
| status | INTEGER | 1 上架 / 0 下架 |
| sort | INTEGER | 排序 |
| created_at / updated_at | DATETIME | 时间戳 |

**quiz_attempts（答题记录，可选 T6；为进度云同步/运营分析预留）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| visitor_key | VARCHAR(64) | 访客标识（耳机号/设备号；进度云同步的 key 预留） |
| score | INTEGER | 答对数 |
| total | INTEGER | 总题数 |
| passed | INTEGER | 1 通关 / 0 |
| created_at | DATETIME | 时间 |

## 三、API 端点清单

**公开（游客端）**

| 端点 | 说明 |
|---|---|
| `GET /api/quiz/questions?count=5` | 从上架题中随机抽 count 题；**响应含 answer_idx**（现场娱乐无防作弊需求，保持前端本地判定，零交互改动） |

**管理端（require_role，复用现有鉴权）**

| 端点 | 说明 |
|---|---|
| `GET /api/admin/quiz/questions` | 全量（含下架） |
| `POST /api/admin/quiz/questions` | 新建（双语字段对） |
| `PUT /api/admin/quiz/questions/{id}` | 编辑 / 上下架 |
| `DELETE /api/admin/quiz/questions/{id}` | 下架（软删） |

**可选（T6）**

| 端点 | 说明 |
|---|---|
| `POST /api/quiz/attempts` | 答题结果上报（匿名 visitor_key） |

## 四、前端改造点

1. **quiz.js**：`BANK` 硬编码 → 启动时 `fetch /api/quiz/questions?count=5`；**失败回退内置 10 题**（现场断网保底娱乐，题面结构一致渲染无感）
2. 判定/渲染/印章/九折码逻辑**零改动**（响应结构即现 BANK 条目）
3. **管理台**（`admin/index.html`）：新增"题库管理"页（双语题干 + 6 个选项输入 + 正确下标下拉 + 上下架），仿商品管理页
4. （可选 T6）通关后上报 attempts（visitor_key 优先取耳机号，无则设备随机 id）

## 五、任务分解与验收标准

| # | 任务 | 验收标准 |
|---|---|---|
| T1 | 模型 + 建表 + seed 迁移现有 10 题 | 初始化后表存在；公开接口可查得 10 题；字段与现 BANK 逐题一致 |
| T2 | 公开抽题 API | 200；仅上架；`count` 生效（5）；重复请求随机性可见 |
| T3 | 管理 CRUD API | 无 token 401；无权限角色 403；增改/下架回读一致 |
| T4 | quiz.js 接 API + 内置回退 | 断网仍可玩（内置题）；正常时用 API 题；通关印章/九折码联动无回归 |
| T5 | 管理台题库页 | 增题/改题/下架后，游客端抽题池即时反映（下架题不再出现） |
| T6 | attempts 上报（可选） | 答题后记录落库，字段齐 |
| T7 | 部署后冒烟 | 并入 `tools/smoke_shop.py` 或独立 `smoke_quiz.py`：抽题 200 / 字段齐 / 管理端鉴权 |

工作量预估：T1-T3 约 0.5 天，T4 约 0.5 天，T5 约 0.5 天，T6 可选 0.5 天，T7 约 0.5 小时。

## 六、边界与风险

- **防作弊不做**：响应含答案下标，前端本地判定——现场娱乐场景接受，与现状一致；若将来发实名奖励再改服务端判定
- **语言范围**：题目仅 zh/en（与现状一致，不扩 7 语）
- **回退双源**：API 与内置题结构相同，混用无感；内置题长期保留作为断网兜底
- **部署**：与商品后端化同批部署即可（无前端强绑定，但建议同批减少往返）
- **进度云同步联动**：quiz_attempts.visitor_key 即进度同步的访客键预留，届时复用
