# AI Daily Briefing v7 安全审查报告

审查日期: 2026-05-16
审查范围: `~/ai-daily-briefing` 全部源码

---

## 1. API Key 管理

### 1.1 现状

| 项目 | 状态 | 说明 |
|------|------|------|
| 统一 `get_api_key()` 函数 | ✅ 已实现 | `src/utils/security.py` 中 `get_api_key(key_name, required=True)` |
| 仅从环境变量读取 | ✅ | `os.environ.get(key_name)` |
| .env 支持 | ✅ | `python-dotenv` + `.env.example` 模板 |
| `.gitignore` 保护 `.env` | ✅ | `.env` 和 `*.env.local` 均被忽略 |
| 缓存文件权限 | ❌ 需关注 | `/tmp/collector_*.json` 包含明文数据，无权限控制 |

### 1.2 安全问题

**【高危】`exa_collector.py` 第 215 行: API Key 从配置字典读取**

```python
# collect_exa_from_group() 中：
api_key: str = cfg.get("exa_api_key", "")  # 从 config 字典读取
```

这是 `_apply_env_overrides()` 将环境变量注入配置字典后导致的间接泄露风险。虽然最终来源是环境变量，但 `cfg` 是一个全局字典对象，存在以下隐患：
- 如果其他代码意外将 `cfg` 序列化输出（日志、缓存等），API Key 会泄露
- 违反"最小知识原则"——配置不应该持有敏感凭据

对比 `collect_exa()`（第 114-115 行）使用 `get_api_key("EXA_API_KEY")` 直接从环境变量读取，`collect_exa_from_group()` 应同样使用 `get_api_key()`。

**【中危】`github_collector.py` 第 50 行: GITHUB_TOKEN 直接从 os.environ 读取**

```python
token: str = os.environ.get("GITHUB_TOKEN", "")
```

没有使用统一的 `get_api_key()` 函数，导致缺乏一致的错误处理、日志和行为（required/optional 控制）。

**【信息】日志中可能包含 API Key 痕迹**

`security.py` 中 `sanitize_error_message()` 函数用于清理错误消息中的 API key，但目前**没有任何调用方使用此函数**。需要在所有采集器的异常处理中调用。

**【信息】.env.example 无 .env 合规检查**

项目有 `.env.example` 模板和 `.gitignore` 保护，但缺少启动时检查实际 `.env` 是否存在的机制。

### 1.3 建议修复

1. **`exa_collector.py` `collect_exa_from_group()`**: 改用 `get_api_key("EXA_API_KEY", required=True)` 替代 `cfg.get("exa_api_key", "")`
2. **`github_collector.py`**: 使用 `get_api_key("GITHUB_TOKEN", required=False)` 替代直接 `os.environ.get`
3. **在所有采集器的异常处理中调用 `sanitize_error_message()`** 清理日志中的敏感信息
4. 在 `main.py` 入口处添加 `.env` 文件存在性检查

---

## 2. 输入验证

### 2.1 现状

| 项目 | 状态 | 说明 |
|------|------|----|
| YAML 配置安全加载 | ✅ | 使用 `yaml.safe_load()` (config.py 第57行) |
| URL 噪声过滤 | ✅ | 关键词模式匹配过滤低质量来源 |
| 日期有效性校验 | ✅ | published 字段非空/非"unknown"/非超时校验 |
| 关键词提取输入验证 | ✅ | `extract_keywords()` 处理空字符串返回空集 |
| 配置键存在检查 | ✅ | `dict.get(key, default)` 安全访问模式广泛使用 |
| **查询模板注入** | **❌** | GitHub 查询中的 `{since}` 模板替换无输入验证 |
| **URL 注入/SSRF** | **⚠️ 弱** | 外部 URL 直接用于存储和展示，无验证 |
| **JSON 加载信任** | **⚠️ 中危** | `json.load(f)` 加载缓存文件，无签名校验 |

### 2.2 安全问题

**【中危】`github_collector.py` 第 69 行: 查询模板注入**

```python
return [q["query"].replace("{since}", since) for q in github_queries_raw]
```

`since` 变量来自 `(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")`，当前是安全的（ISO 日期格式）。但如果有其他模板变量被引入且来源不可控，则存在注入风险。目前不是直接漏洞，但缺乏防御性编程。

**【中危】`classifier.py` 第 31 行: 关键词匹配过于宽松**

```python
if kw in text:  # 子串匹配
```

配置中的关键词如 `"chip"` 会匹配到 `"chip"`, `"chips"`, `"chipmaker"`, `"microchip"` 等。虽然这不是严格意义上的安全漏洞，但可能导致错误分类。更严重的是，关键词 `"process"` 会匹配到 `"processor"`, `"processing"`, `"processes"` 等几乎所有与芯片间接相关的内容。

**【低危】`main.py` 第 57-58 行: JSON 缓存文件无完整性校验**

```python
with open(cache_file, "r", encoding="utf-8") as f:
    cached = json.load(f)
```

缓存文件存储在 `/tmp/` 下，如果攻击者能写入该路径，可注入恶意 JSON 数据影响程序行为。应：
- 限制 `/tmp/` 文件的读取权限（`0o600`）
- 考虑对缓存文件添加校验和或签名

**【信息】跨源聚类中的域名解析**

`cross_source.py` 中 `_extract_domain()` 使用 `urlparse` 解析 URL，这是安全的。但域名提取结果用于聚类策略决策，如果 URL 被篡改可能影响聚类结果。

### 2.3 建议修复

1. **`classifier.py`**: 在 `if kw in text` 匹配中加入单词边界检查，或使用正则 `\bkeyword\b`
2. **`main.py`**: 缓存文件写入后设置 `os.chmod(path, 0o600)`，加载时验证文件权限
3. **为所有 json.load() 操作添加架构校验**（如输出格式预期检查）
4. 在配置模板替换中增加输入白名单验证

---

## 3. 错误处理

### 3.1 现状

| 项目 | 状态 | 说明 |
|------|------|----|
| 采集器异常捕获 | ✅ | 每个采集器有 `try/except` 包装 |
| 单次查询失败不影响整体 | ✅ | 每次查询独立 try/except，跳过失败的查询继续 |
| 主流程超时控制 | ✅ | `ThreadPoolExecutor` + `future.result(timeout=query_timeout)` |
| 日志记录 | ✅ | 统一的 logging 配置 |
| **API Key 缺失退出** | **⚠️** | `raise SystemExit(1)` — testability 差 |
| **缓存文件损坏恢复** | **❌ 弱** | 加载失败返回默认值，但输出可能为空 |
| **敏感信息泄露** | **⚠️ 中危** | 异常信息直接入日志，可能包含敏感 URL 参数 |

### 3.2 安全问题

**【中危】日志中异常信息未清理敏感数据**

所有采集器的 `except` 块都直接记录原始异常：

```python
# exa_collector.py 第 188 行
logger.warning("Exa 查询失败: %s... -> %s", query[:30], e)

# github_collector.py 第 156 行
except json.JSONDecodeError as exc:
    logger.warning("GitHub API 响应解析失败: %s — %s", query[:40], exc)
```

如果 `exc` 或查询响应中包含 API Key 或 token，会直接写入日志。虽然 Exa/GitHub 的异常消息通常不含 API Key，但防御性不足。

**【中危】`quota.py` 第 35 行: 配额文件路径硬编码且无权限保护**

```python
QUOTA_FILE = ".cache/api_quota.json"
```

相对路径 `.cache/` 依赖于工作目录，在多目录执行场景下可能导致：
- 多个实例争抢同一文件（竞态条件）
- 工作目录不正确时文件创建失败（静默失败，见第 42 行 `save_json_file` 的 except 仅 warning）

**【信息】缓存路径基于配置，无路径遍历保护**

```python
cache_file = output_config.get("cache_file", "/tmp/collector_output.json")
```

如果用户配置恶意路径（如 `../../etc/passwd`），存在路径遍历风险。但用户自己配置自己的风险较低。

### 3.3 建议修复

1. **在所有 `logger.warning/exc_info` 调用前清理敏感数据**
2. **`quota.py`**: 使用绝对路径 `os.path.join(os.path.dirname(__file__), ...)` 替代相对路径
3. **`main.py`**: 增加缓存文件损坏时的 fallback 处理（重新采集而非输出空数据）
4. **配置文件路径**: 添加路径遍历检测或白名单

---

## 4. 依赖安全

### 4.1 现状

```
exa-py>=1.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
```

| 依赖 | 版本范围 | 用途 | 安全性 |
|------|----------|------|--------|
| `exa-py` | >=1.0.0 | Exa API 客户端 | 依赖包源为 PyPI，版本锁定宽松 |
| `pyyaml` | >=6.0 | YAML 配置解析 | 使用 `safe_load()`，安全 |
| `python-dotenv` | >=1.0.0 | .env 文件加载 | 成熟包，低风险 |
| `urllib` (stdlib) | - | GitHub API HTTP | 需关注 HTTPS/TLS 验证 |
| `logging` (stdlib) | - | 日志 | 标准库，安全 |

### 4.2 安全问题

**【中危】无依赖版本锁定机制**

所有依赖使用 `>=` 宽松锁定，没有 `requirements.lock` 或 `poetry.lock` / `pip freeze` 等锁定文件。这导致：
- **供应链攻击**: 如果 `exa-py` 被恶意更新，项目会自动拉取恶意版本
- **构建不可重复**: 不同时间安装可能得到不同版本，行为不一致
- **无 CVE 扫描**: 无法自动检测依赖漏洞

**【低危】无依赖安全审计配置**

- 没有 `safety` / `pip-audit` 集成
- 没有 CI 中的依赖漏洞扫描
- 没有 Dependabot / Renovate 配置

**【信息】标准库模块**

项目使用 Python 标准库 `urllib.request` 发送 HTTPS 请求（GitHub API），这些请求默认验证 TLS 证书，但项目没有显式配置 `context=ssl.create_default_context()`。当前是安全的但不够防御。

### 4.3 建议修复

1. **生成 `requirements.lock` 文件** 锁定所有传递依赖版本
2. **配置 Dependabot** 或 Renovate 自动更新依赖
3. **集成 `safety`** 到测试流程中进行 CVE 检查
4. **考虑使用 `requests` 库** 替代 `urllib.request`，获得更好的 SSL 处理和安全头支持
5. **为 `urllib` 请求显式配置 SSL context**

---

## 5. 综合风险评级

| 严重程度 | 数量 | 关键问题 |
|----------|------|----------|
| 🔴 高危 | 1 | `collect_exa_from_group()` 从配置字典读取 API Key |
| 🟠 中危 | 5 | 日志未清理敏感信息、GITHUB_TOKEN 未统一管理、分类关键词过于宽松、无依赖锁定、配额文件路径问题 |
| 🟡 低危 | 3 | 缓存文件无权限保护、JSON 无完整性校验、urllib SSL 未显式配置 |

### 7 天内应优先修复

1. **`exa_collector.py` `collect_exa_from_group()`** — 改用 `get_api_key()` 直接从环境变量读取
2. **为所有采集器异常日志添加 `sanitize_error_message()`**
3. **生成 `requirements.lock`** 锁定依赖版本
4. **缓存文件写入后设置 `os.chmod(0o600)`**

---

## 6. 总结

AI Daily Briefing v7 在安全方面有良好的基础：API Key 管理有统一的 `get_api_key()` 函数、YAML 使用 `safe_load`、输入检查有基本的类型和空值校验、错误处理有适当的 try/except 覆盖。主要问题集中在：

1. **API Key 管理不完全一致**: `collect_exa_from_group()` 函数绕过了安全抽象层，是最高优先级的修复项
2. **日志中潜在的敏感信息泄露**: 异常信息未经清理直接记录
3. **依赖管理缺乏锁定**: 无法保证供应链安全和构建可重复性
4. **文件存储缺乏权限控制**: 缓存和配额文件对所有用户可读

整体安全基线处于"可接受但需改进"水平，上述修复工作量估计在 2-4 小时内可完成。
