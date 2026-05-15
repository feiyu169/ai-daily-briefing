# 🚀 AI 每日投研简报 (AI Daily Briefing) v6

自动采集 AI 领域多源信息，清洗去重后由 LLM 生成结构化日报，每天定时推送到飞书。

## v6 新增功能

- **新增芯片/半导体分类**：自动归类 NVIDIA、AMD、GPU、半导体等相关新闻
- **新增机器人/具身智能分类**：自动归类人形机器人、具身智能、Tesla Bot 等相关新闻
- **配置外置**：分类规则和采集查询通过 config.yaml 配置，无需修改代码
- **模块化架构**：代码拆分为 collectors、processors、utils 模块，便于维护
- **测试覆盖**：32 个单元测试用例，覆盖分类器、去重器、趋势追踪

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  每天 09:00 自动触发                                     │
│       │                                                  │
│       ▼                                                  │
│  Python 采集脚本 (~30s)                                  │
│  ├─ Exa API: 24组语义搜索 (EN+CN+官方+学术+讨论+芯片+机器人) │
│  ├─ GitHub: Search API + Trending                        │
│  └─ 清洗: URL去重 + 语义去重 + 自动分类 + 趋势追踪       │
│       │                                                  │
│       ▼                                                  │
│  LLM 分析+报告生成 (~2min)                               │
│  ├─ 8维度: 趋势/情绪/热点/芯片/机器人/关联/项目/洞察     │
│  └─ 按模板输出 Markdown                                  │
│       │                                                  │
│       ▼                                                  │
│  飞书推送                                                │
└─────────────────────────────────────────────────────────┘
```

## 数据源覆盖

| 信息源 | 采集方式 | 条数/天 | 说明 |
|--------|----------|---------|------|
| 英文 AI 新闻 | Exa 语义搜索 (6组) | ~40条 | 通用AI/LLM/融资/开源/政策/生成式 |
| 芯片/半导体 | Exa 语义搜索 (3组) | ~16条 | NVIDIA/AMD/GPU/半导体/算力 |
| 机器人/具身智能 | Exa 语义搜索 (3组) | ~16条 | 人形机器人/具身智能/Tesla Bot |
| 中文 AI 生态 | Exa 语义搜索 (5组) | ~32条 | 国产大模型/融资/Agent/36氪等 |
| 大厂官方动态 | Exa 语义搜索 (3组) | ~16条 | OpenAI/Anthropic/Google/Meta/Microsoft |
| 学术前沿 | Exa 语义搜索 (2组) | ~11条 | arXiv 论文/中文研究 |
| HN/Reddit 讨论 | Exa 间接采集 (3组) | ~21条 | 绕过 WSL 网络限制 |
| GitHub | Search API (5组) | ~25条 | 最近3天新建 AI repo |
| GitHub Trending | Exa 补充 (2组) | ~14条 | 今日 star 暴涨的 repo |

## 清洗流水线

```
原始数据 ~191条
  → URL 模式过滤 (huggingface datasets/models, kaggle, leetcode)
  → URL 精确去重 + 跨日历史去重 (7天窗口)
  → Jaccard 语义去重 (阈值 0.45，跨域名保留不同视角)
  → 自动分类 (7类别: 融资/并购 | 产品发布 | 技术突破 | 政策/监管 | 芯片/半导体 | 机器人/具身智能 | 行业动态)
  → 趋势关键词提取 + momentum 追踪 (3天窗口)
输出 ~170条结构化数据
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
# 需要 Python 3.10+ (exa-py 使用了 typing.Annotated)
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 Exa API Key、飞书凭据等
```

### 3. 在飞书开放平台创建应用

1. 打开 https://open.feishu.cn/
2. 创建自建应用 → 启用"机器人"能力
3. 开通权限: `im:message:send`
4. 获取 App ID 和 App Secret → 填入 .env

### 4. 创建 Cron Job (Hermes Agent)

```bash
# 如果使用 Hermes Agent:
hermes cron create "0 9 * * *" \
  --name "AI 每日投研简报" \
  --script ai_daily_collector.py \
  --prompt "$(cat ai_report_prompt.md)" \
  --deliver feishu:oc_your_chat_id
```

### 5. 手动测试

```bash
# 直接运行采集脚本测试
python3 ai_daily_collector.py

# 触发一次 cron job 测试全链路
hermes cron run <job_id>
```

## 报告模板

报告包含以下章节:

- **📊 市场脉搏**: 情绪评分 + 关键事件 + 趋势 (延续/新出现)
- **🔥 今日热点**: 5-8条重要新闻 (来源/分类/摘要/要点/链接)
- **🔧 芯片/半导体专题**: 2-3条芯片相关新闻 (v6 新增)
- **🤖 机器人/具身智能专题**: 2-3条机器人相关新闻 (v6 新增)
- **💎 值得关注**: 3-5个重点项目 (亮点/风险)
- **🔗 跨平台关联**: 跨源对比 + 因果链 + 共识分歧
- **💡 今日思考**: 基于全天数据的洞察

完整模板见 `ai_report_prompt.md`。

## 项目结构

```
ai-daily-briefing/
├── README.md                      # 本文件
├── .env.example                   # 环境变量模板
├── .gitignore                     # Git 排除规则
├── requirements.txt               # 依赖清单 (v6 新增)
├── config.yaml                    # 配置文件 (v6 新增)
├── ai_daily_collector.py          # v5 兼容入口 (v6 重构)
├── ai_report_prompt.md            # LLM 分析 prompt 模板
├── src/                           # 源代码 (v6 新增)
│   ├── __init__.py
│   ├── main.py                    # 主入口
│   ├── collectors/                # 采集器模块
│   │   ├── exa_collector.py
│   │   ├── github_collector.py
│   │   └── trending_collector.py
│   ├── processors/                # 数据处理模块
│   │   ├── classifier.py
│   │   ├── dedup.py
│   │   ├── trends.py
│   │   └── cross_source.py
│   └── utils/                     # 工具函数
│       ├── config.py
│       ├── file_utils.py
│       └── logger.py
├── tests/                         # 测试用例 (v6 新增)
│   ├── test_classifier.py
│   ├── test_dedup.py
│   └── test_trends.py
└── versions/                      # 版本快照
    ├── ai_daily_collector_v5.py
    └── ai_daily_collector_v5_pre_opt.py
```

## 技术细节

- **语言**: Python 3.10+
- **核心依赖**: exa-py, pyyaml, python-dotenv
- **采集耗时**: ~30s
- **LLM 分析**: 单次调用，不拆多 Agent (170条数据上下文足够)
- **推送**: 飞书 WebSocket 长连接 (无需公网 IP)
- **去重**: 三重 (URL精确 + 标题Jaccard语义 + 跨日历史)
- **分类**: 基于关键词规则的 7 类自动分类
- **趋势追踪**: 3天窗口的关键词频次，区分延续性/新出现趋势

## 配置说明

### config.yaml

配置文件包含以下部分:

- **collector**: 采集器配置（缓存TTL、历史保留天数、并发数等）
- **categories**: 分类规则（关键词、优先级）
- **queries**: 采集查询（按数据源分组）
- **dedup**: 去重配置（阈值、最小共享关键词数）
- **noise_patterns**: 噪声过滤模式
- **output**: 输出文件路径

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| EXA_API_KEY | 是 | Exa API Key |
| FEISHU_APP_ID | 是 | 飞书应用 ID |
| FEISHU_APP_SECRET | 是 | 飞书应用 Secret |
| FEISHU_HOME_CHANNEL | 是 | 飞书群聊 ID |
| GITHUB_TOKEN | 否 | GitHub Token (增加 API 限额) |

## 成本

| 项目 | 免费额度 | 日常消耗/天 |
|------|----------|------------|
| Exa API | 1000次/月 | ~27次 |
| LLM 推理 | 取决于 provider | ~2k tokens |
| 飞书 Bot | 免费 | 发消息 |
| GitHub API | 10次/分(未认证) | ~5次 |

日常运行成本接近 $0。

## License

MIT
