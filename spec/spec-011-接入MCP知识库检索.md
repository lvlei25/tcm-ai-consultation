# spec-011：接入 MCP 知识库检索（可配置开关）

对应基线：spec-001、spec-003、spec-007

## 变更原因

用户需要在 config 中配置是否使用 MCP 知识库。已确认的设计决策：

1. **开关切换检索后端**：`MCP_ENABLED=false` 时使用现有本地混合检索（FAISS + BM25，spec-001/007）；
   `true` 时 MCP 知识库作为**唯一**检索源
2. **服务端形态**：远程 MCP 服务，Streamable HTTP 传输，config 配 URL
3. **工具约定**：单一检索工具，工具名可配（默认 `search`），入参 `query`、`top_k`

## MCP 工具接口契约

MCP 服务端需提供一个检索工具（名默认 `search`）：

- 入参：`{"query": "<检索语句>", "top_k": 6}`
- 返回：JSON 数组字符串（TextContent），每个元素：
  `{"text": "<医案片段>", "metadata": {"source": "...", "章": "..."}, "score": 0.87}`
- `score` 为 0~1 的相关度（客户端会做 min-max 归一化，与本地混合检索口径一致）
- 返回不是合法 JSON 数组、或元素缺失 `text`/`score` 时，客户端抛出明确中文异常（无 fallback）

## 变更内容

| 文件 | 变更 |
|------|------|
| requirements.txt | 新增 `mcp==2.3.0`（官方 SDK，支持 Streamable HTTP 客户端） |
| config.py | 新增 MCP 常量：`MCP_ENABLED`（默认 false）、`MCP_SERVER_URL`、`MCP_SEARCH_TOOL="search"`、`MCP_TIMEOUT_SECONDS=60`，均支持经 `.env` 覆盖 |
| kb/mcp_retriever.py | 新增 `McpRetriever`：同步 `retrieve(query, top_k)`，内部 `asyncio.run` 建立临时 Streamable HTTP 会话并 `call_tool`；解析校验、归一化、按文本去重、截断 top_k；返回结构与本地检索一致（`text/metadata/score/vec_score/bm25_score`，后两者恒为 0.0，供界面明细表复用）；`MCP_ENABLED` 且 URL 为空时抛明确中文异常 |
| app.py | 知识库加载按 `MCP_ENABLED` 分流：`get_mcp_retriever()`（`@st.cache_resource`）或现有 `get_retriever()`；MCP 模式下 `RuntimeError`/`FileNotFoundError` 均中文报错并 `st.stop` |
| scripts/build_kb.py | 不变更；MCP 模式下本地构建仍可离线执行（本地库在 MCP_ENABLED=true 时不参与检索） |

## 验证

- `python -m pytest tests/ -q` 全量通过，新增 `tests/test_mcp_retriever.py`：
  - JSON 数组解析与分数归一化（正常）
  - 元素缺 `score`/`text`、非法 JSON 抛明确中文异常（异常）
  - top_k 截断与去重（边界）
  - `MCP_ENABLED=true` 且 URL 为空抛中文异常（异常）
- `MCP_ENABLED=false` 回归：现有 48 例 + 集成 3 例行为不变
- 真实 MCP 服务联调：待用户提供服务端 URL 后按本 spec 契约实测（浏览器步骤 2 明细表展示 MCP 命中）

## 注意事项

- 每次查询新建 MCP 会话（握手 + call_tool），实现简单、无长连接生命周期问题；
  若后续实测握手开销显著，再立 spec 优化为会话复用
- 无 fallback：MCP 调用失败不回退到本地检索，直接报错（开关由用户显式控制）
- `mcp==2.3.0` 客户端 API：`streamable_http_client(url)` 产出 `(read_stream, write_stream)`

## 修订（真实服务联调后发现接口差异，2026-10-17）

用户提供的真实服务端 `http://127.0.0.1:8000/mcp` 与初版契约不符，客户端按实际接口适配：

| 项 | 初版契约 | 实际接口（已适配） |
|---|---|---|
| 入参 | `{"query", "top_k"}` | `{"query", "limit"}`（另有可选 `category`，本客户端不传） |
| 返回 | JSON 数组 `[{text, metadata, score}]` | 分块纯文本：`### 类型/名称（命中 N 次）` + 片段，无命中时返回中文说明 |
| 服务端工具集 | 单一 search | `list_categories / list_entries / get_entry / search / get_links`，本客户端仅用 `search` |

适配规则：
- 每个命中块解析为一条证据：`text` = 片段文本，`metadata` = `{"source": 名称, "类型": 类型, "命中次数": N}`，`score` = 命中次数（客户端再做 min-max 归一化，唯一候选为 1.0）
- 返回「知识库中没有…」「命中 0 条」类说明时视为空结果（返回空列表，不报错）
- 出现无法识别的格式（既无命中块也非无命中说明）时抛明确中文异常，无 fallback

## 修订三（错误透传增强，2026-10-26）

Vue 前端实测报「unhandled errors in a TaskGroup」：MCP 客户端的 anyio TaskGroup 会把
真实异常（如 ConnectionRefusedError）包在 `__exceptions__` 里，`str(exc)` 只剩笼统描述。
`kb/mcp_retriever.py` 新增 `_describe_error()`：递归展开嵌套异常链拼接完整错误信息，
识别连接类错误时附加「请确认 MCP 服务端已启动并监听该地址」提示。包装位置位于同步入口
`_call_search`，异常包装与解析逻辑分离，便于测试 mock 异步层。

## 修订二（检索语义适配，2026-10-17）

实测服务端 `search` 为**严格 AND** 语义（空格分词、要求所有词同时出现，实测 5 词即 0 命中），
而本地检索语句生成器输出的是无空格的 80 字连贯语句，MCP 模式下必然 0 命中。两端适配：

| 文件 | 变更 |
|------|------|
| config.py | 新增 `MCP_MAX_TERMS = 4`（降级重试时的最大词数） |
| pipeline/form_query.py | `build_query_messages` 按 `config.MCP_ENABLED` 运行时选择提示词：MCP 模式输出 **2~4 个空格分隔的中医关键词**（如「不寐 心悸」），本地模式维持 80 字语句不变 |
| kb/mcp_retriever.py | 客户端降级重试：按全词 → 前 4 → 前 3 → 前 2 → 前 1 词的顺序调用 `search`，首个非空结果即用；全部为空返回空列表（诊断按无证据处理，非异常）；无空格长语句先用 jieba 分词再走同一降级序列 |

该策略为明确定义的检索行为（关键词化 + 降级），不属于静默兜底；本地混合检索链路不受影响。

## 验证结果（2026-10-17 执行）

- `mcp==2.3.0` 安装成功，`pip check` 无依赖冲突（pydantic/httpx 与现有版本兼容）
- `python -m py_compile app.py config.py kb/mcp_retriever.py` 通过
- `python -m pytest tests/ -q` → 54 passed, 3 deselected（新增用例 49~57，均离线、mock 网络）
- `MCP_ENABLED=false` 回归：既有用例与集成用例行为不变（开关默认关闭）

## 真实服务联调结果（http://127.0.0.1:8000/mcp，2026-10-17）

- 连接与握手正常，工具集：`list_categories / list_entries / get_entry / search / get_links`
- 3 词查询「不寐 多梦 心悸」：直接命中 1 条（医学衷中参西录，命中 47 次）
- 5 词查询：降级到前 4 词后命中 6 条，出处含 source/concept/entity 多种类型，归一化得分正常
- 无空格长语句：jieba 分词防御生效（离线用例 57 验证）
- `.env` 已配置 `MCP_ENABLED=true`、`MCP_SERVER_URL=http://127.0.0.1:8000/mcp`（不入库）
- 浏览器端到端（步骤 2 明细表展示 MCP 命中）由用户实测确认
