# AI Daily Briefing v7 实施计划

## 目标

扩大芯片/机器人采集信息，优化跨源聚类算法，增加跨源关联深度分析。

## Non-Goals

- 不新增专题报告章节
- 不更换数据源（仍以 Exa API 为主力）
- 不更换推送渠道（仍使用飞书）

## Affected Files

| 文件 | 操作 | 说明 |
|------|------|------|
| config.yaml | 修改 | 增加芯片/机器人查询，调整聚类参数 |
| src/collectors/exa_collector.py | 修改 | 支持新增的数据源查询 |
| src/processors/cross_source.py | 修改 | 优化聚类算法，增加因果链分析 |
| src/processors/trends.py | 修改 | 增加跨源趋势追踪 |
| tests/test_collectors.py | 修改 | 更新测试用例 |
| tests/test_cross_source.py | 新增 | 跨源聚类测试 |
| tests/test_trends.py | 修改 | 趋势追踪测试 |

## Implementation Slices

### Slice 1: 扩大芯片/机器人采集信息（2小时）

**目标**: 增加芯片/机器人的查询数量和数据源

**任务**:
1. 更新 config.yaml
   - 芯片查询从 3 条增加到 6-8 条
   - 机器人查询从 3 条增加到 6-8 条
   - 新增芯片/机器人专项数据源查询
2. 更新 src/collectors/exa_collector.py
   - 支持新增的数据源查询（TechCrunch、IEEE Spectrum 等）

**验收标准**:
- [ ] 芯片查询 ≥ 6 条
- [ ] 机器人查询 ≥ 6 条
- [ ] 新增数据源查询可正常执行

### Slice 2: 优化跨源聚类算法（2小时）

**目标**: 提高跨源聚类的准确性

**任务**:
1. 更新 src/processors/cross_source.py
   - 调整 Jaccard 阈值（从 0.35 调整到动态阈值）
   - 增加关键词权重（高频词权重更高）
   - 增加跨域保留逻辑（不同域名的相似文章保留）
2. **拆分 cross_source.py**（P1-1 修复）
   - 创建 src/processors/causal_chain.py — 因果链分析
   - 创建 src/processors/consensus.py — 共识/分歧分析
   - cross_source.py 只保留聚类逻辑
3. 新增 tests/test_cross_source.py
   - 测试聚类准确性
   - 测试跨域保留逻辑

**验收标准**:
- [ ] 聚类准确性提高（测试用例验证）
- [ ] 跨域保留逻辑正常工作
- [ ] cross_source.py 拆分完成
- [ ] 测试覆盖率 > 60%

### Slice 3a: 因果链分析（2小时）

**目标**: 增加因果链分析和共识/分歧分析

**任务**:
1. 创建 src/processors/causal_chain.py（P1-1 拆分结果）
   - 实现因果链分析（A→B 逻辑关系）
   - 限制复杂度（max_depth=3, max_nodes=10, timeout=30s）
2. 创建 src/processors/consensus.py（P1-1 拆分结果）
   - 实现共识/分歧分析

**验收标准**:
- [ ] 因果链分析可正常执行
- [ ] 共识/分歧分析可正常执行
- [ ] 复杂度限制生效

### Slice 3b: 跨源趋势追踪（2小时）

**目标**: 增加跨源趋势追踪

**任务**:
1. 更新 src/processors/trends.py
   - 增加跨源趋势追踪（3 天窗口）
   - 增加趋势热度量化

**验收标准**:
- [ ] 跨源趋势追踪可正常执行
- [ ] 趋势热度量化可正常执行

### Slice 4: 测试覆盖 + 向后兼容验证（1小时）

**目标**: 确保测试覆盖和向后兼容

**任务**:
1. 更新测试用例
2. 运行全量测试
3. 验证 JSON 输出向后兼容

**验收标准**:
- [ ] 测试覆盖率 > 60%
- [ ] 所有测试通过
- [ ] JSON 输出结构向后兼容

## 时间估算

| Slice | 预计时间 | 依赖 |
|-------|----------|------|
| Slice 1 | 3小时 | 无 |
| Slice 2 | 3小时 | Slice 1 |
| Slice 3a | 2小时 | Slice 2 |
| Slice 3b | 2小时 | Slice 2 |
| Slice 4 | 2小时 | Slice 3a, 3b |
| **总计** | **12小时** | |

**注**: Slice 3a 和 3b 可并行执行，实际关键路径为 10 小时。

## 执行顺序

```
Slice 1 (扩大采集)
    ↓
Slice 2 (优化聚类)
    ↓
Slice 3 (深度分析)
    ↓
Slice 4 (测试验证)
```

## 向后兼容性矩阵

| 字段 | 类型 | 说明 | 兼容性 |
|------|------|------|--------|
| collected_at | str | 采集时间 | 必须保留 |
| date | str | 日期 | 必须保留 |
| total_items | int | 总条目数 | 必须保留 |
| source_counts | dict | 各源采集数 | 必须保留 |
| category_counts | dict | 各分类数量 | 必须保留（可新增分类） |
| trend_momentum | dict | 趋势数据 | 必须保留 |
| cross_platform_signals | list | 跨源信号 | 必须保留（可增强） |
| items | list | 采集条目 | 必须保留 |

## 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 查询增加导致 API 配额超限 | 采集失败 | 监控 API 使用量，设置告警，降级机制 |
| 聚类算法优化引入误判 | 聚类不准确 | 充分测试，保留回滚机制 |
| 因果链分析复杂度过高 | 性能下降 | 限制分析深度（max_depth=3），添加超时控制 |
| 向后兼容性风险 | 破坏现有功能 | 只增不删字段，保留默认行为 |
| _flatten_queries() 硬编码 | 新增查询分组不被采集 | 改为动态发现所有 queries 分组 |
| 动态阈值变更 | 聚类行为变化 | 新增 use_dynamic_threshold 参数，默认 False |
