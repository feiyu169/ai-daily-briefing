# AI Daily Briefing v6 实施计划

## 目标

将 AI Daily Briefing 从 v5 升级到 v6，新增芯片/半导体和机器人/具身智能两个类目，同时进行全面代码优化。

## Non-Goals

- 不更换数据源（仍以 Exa API 为主力）
- 不更换推送渠道（仍使用飞书）
- 不实现实时推送（仍为每日定时）

## Affected Files

| 文件 | 操作 | 说明 |
|------|------|------|
| ai_daily_collector.py | 重构 | 拆分为多模块 |
| config.yaml | 新增 | 外置配置 |
| requirements.txt | 新增 | 依赖管理 |
| collectors/ | 新增 | 采集器模块 |
| processors/ | 新增 | 数据处理模块 |
| utils/ | 新增 | 工具函数 |
| tests/ | 新增 | 测试用例 |
| ai_report_prompt.md | 更新 | 报告模板 |

## Implementation Slices

### Slice 1: 基础设施（2小时）

**目标**: 建立项目基础结构

**任务**:
1. 创建 requirements.txt（含 exa-py、pyyaml、python-dotenv）
2. 创建 .venv 并安装依赖
3. 创建 config.yaml 外置配置
4. 创建目录结构
5. **创建兼容性入口**：保留 `ai_daily_collector.py` 作为薄 wrapper
   ```python
   # ai_daily_collector.py (v6 兼容层)
   """v5 兼容入口 — cron job 无需修改"""
   from src.main import main
   if __name__ == "__main__":
       main()
   ```

**验收标准**:
- [ ] requirements.txt 包含所有依赖
- [ ] .venv 创建成功
- [ ] config.yaml 包含所有可配置项
- [ ] `python ai_daily_collector.py` 可正常运行（向后兼容）

### Slice 2: 模块化拆分（3小时）

**目标**: 将单文件拆分为多模块

**任务**:
1. 创建 collectors/ 目录
   - exa_collector.py
   - github_collector.py
   - trending_collector.py
2. 创建 processors/ 目录
   - dedup.py
   - classifier.py
   - trends.py
3. 创建 delivery/ 目录
   - feishu.py（从现有代码提取推送逻辑，保持接口不变）
4. 创建 utils/ 目录
   - file_utils.py
   - logger.py
   - config.py（加载 .env + config.yaml，优先级：环境变量 > YAML > 默认值）
5. 创建 src/main.py 入口文件

**配置管理策略**:
- 环境变量（.env）：API Key 等敏感信息
- config.yaml：业务配置（分类规则、查询语句、并发数）
- 优先级：环境变量 > YAML > 默认值
- 使用 python-dotenv 加载 .env

**验收标准**:
- [ ] 每个模块职责单一
- [ ] 模块间接口清晰
- [ ] src/main.py 可正常运行
- [ ] `python ai_daily_collector.py` 仍可正常运行（兼容层）

### Slice 3: 新增类目（2小时）

**目标**: 新增芯片和机器人分类

**任务**:
1. 更新 config.yaml
   - 新增芯片/半导体分类规则
   - 新增机器人/具身智能分类规则
2. 更新 collectors/exa_collector.py
   - 新增芯片专项查询（3条）
   - 新增机器人专项查询（3条）
3. 更新 processors/classifier.py
   - 新增分类规则
   - 更新优先级

**验收标准**:
- [ ] 芯片新闻自动归类
- [ ] 机器人新闻自动归类
- [ ] 采集查询增加 6+ 条

### Slice 4: 代码质量优化（2小时）

**目标**: 提升代码质量

**任务**:
1. 添加类型注解
2. 完善错误处理
3. 优化日志系统
4. 修复 ruff 错误

**验收标准**:
- [ ] ruff 错误数 = 0
- [ ] 类型注解覆盖率 > 80%
- [ ] 错误处理完善

### Slice 5: 测试覆盖（2小时）

**目标**: 建立测试体系

**任务**:
1. 创建 tests/ 目录
2. 编写单元测试
   - 测试分类器
   - 测试去重器
   - 测试采集器
3. 配置 pytest

**验收标准**:
- [ ] 测试覆盖率 > 60%
- [ ] 所有测试通过

### Slice 6: 报告模板升级（1小时）

**目标**: 更新报告模板

**任务**:
1. 更新 ai_report_prompt.md
   - 新增芯片专题章节
   - 新增机器人专题章节
2. 更新 README.md

**验收标准**:
- [ ] 报告包含芯片专题
- [ ] 报告包含机器人专题

### Slice 7: 集成测试 + 文档（1小时）

**目标**: 确保整体功能正常

**任务**:
1. 运行完整采集流程
2. 验证向后兼容性
3. 更新文档

**验收标准**:
- [ ] 完整流程正常运行
- [ ] JSON 输出向后兼容
- [ ] 文档完整

## Tests

| 测试类型 | 覆盖范围 | 工具 |
|----------|----------|------|
| 单元测试 | 分类器、去重器、工具函数 | pytest |
| 集成测试 | 采集流程、输出格式 | pytest |
| 兼容性测试 | JSON 输出结构 | pytest |

## Risks

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模块化拆分引入 bug | 功能异常 | 保留 v5 快照 + 逐模块测试 |
| 分类规则冲突 | 分类错误 | 优先级机制 + 测试用例 |
| Exa API 查询增加导致超时 | 采集失败 | 并行查询 + 超时控制 |
| Exa API 并发限制 | 采集失败 | 信号量限制并发数（max_concurrent=5）+ 重试退避 |

## Residual Risks

| 风险 | 状态 | 说明 |
|------|------|------|
| Exa API 配额限制 | 已知 | 当前 ~24次/天，增加查询后可能接近限制（1000次/月） |
| 分类规则误判 | 已知 | 基于关键词的分类可能有误判，需持续优化 |
| 飞书推送依赖 | 已知 | 推送模块保持不变，如飞书 API 变更需同步更新 |

## 向后兼容性矩阵

| 字段 | 类型 | 说明 | 兼容性 |
|------|------|------|--------|
| collected_at | str | 采集时间 | 必须保留 |
| date | str | 日期 | 必须保留 |
| total_items | int | 总条目数 | 必须保留 |
| source_counts | dict | 各源采集数 | 必须保留 |
| category_counts | dict | 各分类数量 | 必须保留（可新增分类） |
| trend_momentum | dict | 趋势数据 | 必须保留 |
| cross_platform_signals | list | 跨源信号 | 必须保留（可为空） |
| items | list | 采集条目 | 必须保留 |

**测试用例**:
```python
COMPATIBILITY_FIELDS = {'collected_at', 'date', 'total_items', 'source_counts', 'category_counts', 'trend_momentum', 'items'}
# 测试：新版本输出必须包含以上所有字段
```

## 时间估算

| Slice | 预计时间 | 依赖 |
|-------|----------|------|
| Slice 1 | 2小时 | 无 |
| Slice 2 | 3.5小时 | Slice 1 |
| Slice 3 | 2小时 | Slice 2 |
| Slice 4 | 2小时 | Slice 2 |
| Slice 5 | 2.5小时 | Slice 3, 4 |
| Slice 6 | 1.5小时 | Slice 3 |
| Slice 7 | 1.5小时 | Slice 5, 6 |
| **总计** | **15小时** | |

## 执行顺序

```
Slice 1 (基础)
    ↓
Slice 2 (拆分)
    ↓
Slice 3 (新类目) + Slice 4 (代码质量) ← 并行
    ↓
Slice 5 (测试)
    ↓
Slice 6 (报告模板)
    ↓
Slice 7 (集成测试)
```
