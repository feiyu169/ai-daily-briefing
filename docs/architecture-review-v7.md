# AI Daily Briefing v7 架构审查报告

审查日期: 2026-05-16
审查范围: implementation-plan-v7.md, requirements-v7.md, 当前代码库
审查人: Hermes Agent (架构审查自动化)

---

## 审查结论概要

| 维度 | 评分 | 说明 |
|------|------|------|
| 模块划分合理性 | ⚠️ 中 | Slice 划分合理，但跨源聚类与因果链分析耦合在同一模块 |
| 接口设计一致性 | ⚠️ 中 | 函数签名基本一致，但存在重复的工具函数定义 |
| 依赖关系清晰度 | ✅ 高 | Slice 依赖明确，代码 import 树清晰 |
| 架构违规 | ✅ 无严重违规 | 存在 2 处需要注意的代码异味 |

**总体评估**: 计划可执行，建议在实施过程中修正 3 项中等问题。

---

## 1. 模块划分合理性

### 1.1 当前模块结构

```
src/
  collectors/
    exa_collector.py       # Exa API 采集
    github_collector.py    # GitHub 仓库采集
    trending_collector.py  # GitHub Trending 采集
  processors/
    classifier.py          # 关键词分类
    dedup.py               # 去重 + extract_keywords / jaccard_similarity
    cross_source.py        # 跨源聚类 (依赖 dedup)
    trends.py              # 趋势追踪 + 自有 extract_keywords
  utils/
    config.py              # 配置加载
    file_utils.py          # JSON 文件读写
    logger.py              # 日志
    security.py            # 安全工具
  delivery/                # 推送 (__init__.py 仅空)
  main.py                  # 编排入口
```

### 1.2 Slice 划分评价

计划中的 4 个 Slice 划分合理：

- **Slice 1 (扩大采集)** → 只动 config.yaml + exa_collector.py，边界清晰
- **Slice 2 (优化聚类)** → 只动 cross_source.py + 新增测试，范围精准
- **Slice 3 (深度分析)** → 动 cross_source.py + trends.py，注意二者存在交叉
- **Slice 4 (测试验证)** → 纯测试 + 兼容性验证，无代码风险

### 1.3 问题: 跨源聚类与因果链分析耦合过紧

**问题描述**:
计划将"优化聚类算法"(Slice 2)和"因果链分析 + 共识/分歧分析"(Slice 3)都放在 `cross_source.py` 中。当前 `cross_source.py` 只有 88 行、单一函数 `cross_source_cluster()`。如果继续往里塞因果链分析和共识/分歧分析，该文件将膨胀到 200+ 行且承担多个职责。

**建议**:
将因果链分析 (causal_chain) 和共识/分歧分析 (consensus_divergence) 拆为独立模块，例如:
```
src/processors/
  cross_source.py          # 仅做聚类 + 话题识别
  causal_chain.py (新增)   # 因果链分析
  consensus.py (新增)      # 共识/分歧分析
```
或者合并到 `src/processors/analysis/` 子包中。

**影响**: 如果不拆分，未来"单独修改聚类阈值"和"调整因果链逻辑"会互相干扰，违反单一职责原则。

### 1.4 问题: trends.py 与 dedup.py 存在重复的 extract_keywords

**问题描述**:
- `src/processors/dedup.py` 定义了 `extract_keywords()` 和 `jaccard_similarity()`
- `src/processors/trends.py` 定义了自己的 `extract_keywords()`（逻辑几乎相同，但停用词表独立维护）
- `src/processors/cross_source.py` 从 dedup 导入 `extract_keywords` 和 `jaccard_similarity`

两个 `extract_keywords` 实现略有差异（trends.py 的 STOP_WORDS 更短，缺少中文停用词），可能导致关键词提取结果不一致。

**建议**: 统一归到 `src/utils/text.py` 或 `src/processors/dedup.py`，让 trends.py 导入复用。

---

## 2. 接口设计一致性

### 2.1 采集器接口

所有采集器遵循隐式接口约定:
```python
def collect_xxx() -> List[Dict[str, Any]]
```
- exa_collector: ✅ `collect_exa()` 返回 `List[Dict]`
- github_collector: ✅ `collect_github()` 返回 `List[Dict]`
- trending_collector: ✅ `collect_github_trending()` 返回 `List[Dict]`
- 额外函数: `collect_exa_from_group(group_name)` 是新加的，返回相同格式 ✅

### 2.2 处理器接口

| 函数 | 签名 | 一致性 |
|------|------|--------|
| `dedup_and_filter(data, history)` | `(List[Dict], Dict[str,str]) -> List[Dict]` | ✅ |
| `cross_source_cluster(items, ...)` | `(List[Dict], float, int) -> List[Dict]` | ✅ |
| `detect_trend_keywords(items, ...)` | `(List[Dict], int) -> Set[str]` | ✅ |
| `get_trend_momentum(items, ...)` | `(List[Dict], str, int) -> Tuple[Set, Dict]` | ✅ |
| `classify_item(title, snippet)` | `(str, str) -> str` | ✅ |

### 2.3 配置接口

config.py 提供了清晰的 getter 函数: `get_config()`, `get_collector_config()`, `get_queries()`, `get_categories()`, `get_dedup_config()`, `get_noise_patterns()`, `get_output_config()` ✅

### 2.4 问题: 输出格式向后兼容性仅部分验证

向后兼容性矩阵列出了顶层字段（collected_at, date, total_items 等），但未检查 `items` 内部的字段结构是否稳定。计划中 Slice 1 在 exa_collector.py 中新增数据源查询后，items 中的 `source` 字段可能增加新值（如 techcrunch, ieee_spectrum），下游消费者如果依赖有限集合的 source 值可能需要适配。

**建议**: 在向后兼容性矩阵中增加字段级别的兼容声明，或明确 add-only 策略（只增字段不改已有字段）。

---

## 3. 依赖关系清晰度

### 3.1 Slice 依赖

```
Slice 1 (扩大采集) ── 无外部依赖
    ↓
Slice 2 (优化聚类) ── 依赖 Slice 1 的新数据作为聚类输入
    ↓
Slice 3 (深度分析) ── 依赖 Slice 2 的聚类结果
    ↓
Slice 4 (测试验证) ── 依赖所有之前 Slice
```

依赖关系清晰，无循环依赖 ✅

### 3.2 代码层 import 依赖

```
main.py
  ├── collectors/exa_collector.py
  │     ├── utils/config.py
  │     └── processors/classifier.py
  │           └── utils/config.py
  ├── collectors/github_collector.py
  ├── collectors/trending_collector.py
  ├── processors/dedup.py
  │     └── utils/config.py
  ├── processors/trends.py
  │     ├── utils/config.py
  │     └── utils/file_utils.py
  ├── processors/cross_source.py
  │     └── processors/dedup.py (extract_keywords, jaccard_similarity)
  └── utils/*
```

**发现的问题**: `cross_source.py` 依赖 `dedup.py` 引入 `extract_keywords` 和 `jaccard_similarity`。这意味着修改 dedup.py 的关键词提取逻辑可能意外影响聚类结果。应当将这两个核心工具函数提升到公共层。

### 3.3 配置依赖

config.yaml 的 `dedup.cross_source_threshold` 同时被 `dedup.py` 和 `cross_source.py` 读取（虽然 cross_source 当前未从配置读取，而是通过参数传入）。Slice 2 计划将阈值从固定 0.35 改为动态阈值，需确保配置优先级和覆盖逻辑清晰。

---

## 4. 架构违规检查

### 4.1 无严重违规

| 违规类型 | 检查结果 |
|----------|----------|
| 循环依赖 | ✅ 无 |
| 代码重复 > 50% | ⚠️ extract_keywords 重复（见 1.4） |
| 模块职责过宽 | ⚠️ cross_source.py 即将膨胀（见 1.3） |
| 跨层直接调用数据库/文件 | ✅ 仅 utils/file_utils.py 处理文件 |
| 配置硬编码 | ✅ 配置分离 |
| 全局状态滥用 | ⚠️ config.py 使用模块级 `_config` 单例（可接受） |

### 4.2 代码异味

**异味 1: exa_collector.py 中的重复逻辑**

`collect_exa()` 和 `collect_exa_from_group()` 有大量重复的查询执行逻辑（~50 行）。建议提取一个内部的 `_execute_search(exa, query, num, seen_urls)` 辅助函数。

**异味 2: main.py 中的趋势追踪逻辑混合**

`main.py` 第 105-111 行手动处理趋势对比（continuing vs new），这部分逻辑本应由 `get_trend_momentum()` 封装。当前代码直接在编排层做了趋势的对比计算，弱化了模块封装。

```python
# main.py 当前做法:
today_keywords = detect_trend_keywords(merged)
old_trends = {kw for kw, dt in trends_history.items() if dt <= yesterday_str}
continuing_trends = today_keywords & old_trends
new_trends = today_keywords - old_trends

# 更好的做法:
# from trends import get_trend_momentum
# trend_kws, momentum_data = get_trend_momentum(merged)
```

### 4.3 不可追溯的配置项

config.yaml 中 `collector.max_concurrent_queries: 5` 和 `collector.query_timeout: 60` 在代码中未被实际使用（main.py 使用 ThreadPoolExecutor(max_workers=1) 且用硬编码超时处理）。这是 v6 遗留的配置定义未实装问题。

---

## 5. 具体改进建议

### 5.1 优先级: P0（必须改）

1. **统一 extract_keywords** — 将 dedup.py 和 trends.py 中的 extract_keywords 合二为一，提取到 `src/utils/text.py`

### 5.2 优先级: P1（建议改）

2. **拆分 cross_source.py** — 将因果链分析和共识/分歧分析拆为独立模块，保持 cross_source.py 负责纯聚类
3. **去重 exa_collector 中 collect_exa/collect_exa_from_group 的重复代码**

### 5.3 优先级: P2（可推迟）

4. 将 main.py 中的趋势对比逻辑下沉到 trends.py 的 `get_trend_momentum()` 中
5. 移除 config.yaml 中未实装的 `max_concurrent_queries` 或补全实现

---

## 6. 总结

**架构总体健康**。v7 实施计划的模块划分和依赖关系设计合理，无明显架构违规。主要风险在于：

1. **cross_source.py 职责膨胀** — 计划中把聚类优化+因果链+共识分歧全塞进一个文件，建议拆分
2. **extract_keywords 代码重复** — 两套实现可能导致行为不一致
3. **exa_collector.py 函数级重复** — collect_exa() 和 collect_exa_from_group() 共享大量逻辑

建议在 Slice 1 执行前先完成 extract_keywords 统一和 exa_collector 代码去重，将 cross_source 拆分纳入 Slice 2/3 计划中。

---

## 附录: 评分明细

| 审查项 | 评分 | 说明 |
|--------|------|------|
| 模块内聚性 | 7/10 | cross_source.py 即将超载 |
| 模块间耦合度 | 8/10 | import 树清晰，无循环依赖 |
| 接口一致性 | 8/10 | 采集器/处理器接口一致，但内部有重复逻辑 |
| 向后兼容规划 | 7/10 | 顶层字段保证了，items 内部未声明 |
| 测试覆盖规划 | 8/10 | 新增测试文件 + 覆盖率目标合理 |
| 风险识别 | 8/10 | 识别了 API 配额/误判/性能风险，但未识别架构风险 |
