# spec-012：Vue 前端与 FastAPI 接口

对应基线：spec-001、spec-003、spec-004、spec-009、spec-011

## 变更原因

现有界面为 Streamlit（`app.py`），形态受限（无独立部署、无自定义交互）。用户要求生成一版
基于 Vue 的前端。Streamlit 不能作为 API 后端，因此需要一并新增一个复用现有
kb/pipeline 模块的 FastAPI 接口层，Vue 前端经 HTTP/SSE 调用。

## 总体设计

```
frontend/（Vue 3 + Vite）
   │  POST /api/diagnose/stream（SSE）
   ▼
api.py（FastAPI，复用 config / kb / pipeline 全部现有逻辑）
   │
   ├─ form_query.generate_query        （检索语句生成，本地/MCP 后端随 config 开关）
   ├─ HybridRetriever / McpRetriever   （检索后端随 MCP_ENABLED 切换）
   └─ diagnoser.stream_diagnosis       （流式辨证诊断）
```

## 接口契约（api.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查，返回检索后端类型（local/mcp） |
| POST | /api/diagnose/stream | 请求体为问诊单 JSON（字段与 spec-004 表单一致）；返回 SSE 事件流 |

SSE 事件（`data: <json>`）：
- `{"type":"query","query":"..."}`：步骤 1 完成，附检索语句
- `{"type":"evidences","items":[...]}`：步骤 2 完成，附证据列表（含 score/出处/两路明细）
- `{"type":"chunk","text":"..."}`：步骤 3 诊断正文流式片段
- `{"type":"sections","sections":{...}}`：完成后的小节结构化结果（spec-009）
- `{"type":"error","message":"..."}`：任一步失败，流终止

校验：主诉缺失直接返回 `error` 事件（复用 `validate_form`）；无 fallback。

## 变更内容

| 文件 | 变更 |
|------|------|
| api.py | 新增 FastAPI 应用：健康检查 + SSE 诊断流；复用现有模块，不复制业务逻辑 |
| requirements.txt | 新增 `fastapi`、`uvicorn`（版本与环境一致） |
| frontend/package.json | Vue 3 + Vite + @vitejs/plugin-vue |
| frontend/vite.config.js | 开发代理 `/api` → `http://127.0.0.1:8000` |
| frontend/index.html、src/main.js、src/App.vue | 单页界面：渐变头部、七组问诊单（字段与选项与 app.py 一致）、开始诊断按钮、三步状态（检索语句/证据明细表/流式诊断）、按小节折叠展示（spec-009）、参考医案来源表 |
| tests/test_api.py | TestClient 覆盖：健康检查、主诉缺失返回 error 事件、mock 全链路 SSE 事件顺序与结构 |

## 运行方式

```bash
# 后端（使用 .venv）
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
# 前端开发模式
cd frontend && npm install && npm run dev    # http://localhost:5173
# 前端构建产物
cd frontend && npm run build
```

注意：MCP 模式（spec-011）默认占用 8000 端口时，后端改用 `--port 8010` 并同步修改
frontend/vite.config.js 的代理目标，避免端口冲突。

## 验证

- `python -m pytest tests/ -q` 全量通过（含新增 API 用例）
- `uvicorn api:app` 启动后 `GET /api/health` 返回 200
- `npm run build` 成功产出静态文件；`npm run dev` 页面可渲染七组表单
- 浏览器端到端（需用户启动后端+前端后实测）：三步流程与 Streamlit 版一致

## 注意事项

- 不改动现有 Streamlit 入口（app.py 保留，两版界面并存）
- 无 fallback：接口层不吞异常，错误以 error 事件透出
- Key 仍只经 `config.get_api_key()` 读取，前端不接触任何密钥

## 验证结果（2026-10-26 执行）

- `python -m pytest tests/ -q` → 58 passed, 3 deselected（新增用例 58~61，全部 mock、无真实请求）
- `npm install`（npmmirror 镜像）与 `npm run build` 成功：dist 产物 80.45 kB JS / 2.32 kB CSS
- `uvicorn api:app` 启动冒烟：`GET /api/health` 返回 200
- **顺带修复既有 bug**：`config.py` 的 `MCP_ENABLED` 比较值误写为 `== "false"`，
  导致 MCP 开关永远关闭（此前联调直接实例化 McpRetriever 未走开关，故未暴露）；
  修复后冒烟返回 `{"status":"ok","retriever":"mcp"}`
- 浏览器端到端（npm run dev + uvicorn 同时启动后填写问诊单实测）由用户执行
