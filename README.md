# 中医AI问诊平台

[中文](#中医ai问诊平台) | [English](#english-version)

基于名老中医医案 RAG（检索增强生成）的在线中医问诊系统。患者填写按四诊（望闻问切）组织的结构化问诊单，系统将问诊单转换为规范中医术语检索语句，从医案知识库中混合检索相关医案片段，再由大模型结合医案证据进行辨证推理，输出结构化诊断结果。

## 功能特性

- 四诊结构化问诊单：基本信息、望诊与切诊（面色/舌质/舌苔/脉象）、问寒热汗出、问头身胸腹、问饮食口味、问睡眠情志、问二便与经期、其他伴随症状
- 检索语句生成：大模型将问诊单整理为不超过 80 字的规范中医术语检索语句（MCP 模式下生成空格分隔的关键词）
- 混合检索：FAISS 向量检索（权重 0.6）+ jieba 分词 BM25 关键词检索（权重 0.4），归一化加权融合后按 MMR 去冗余，返回带两路得分明细的前 6 条医案片段
- MCP 知识库检索：通过开关切换，把外部 MCP 知识库服务作为唯一检索源，支持 AND 语义下的逐词降级重试
- 流式辨证诊断：结合医案证据，从八纲（表里寒热虚实阴阳）、脏腑、气血津液角度辨证分析，输出证型（标注八纲属性）、治法、推荐方药与加减、调护建议、引用医案依据
- 分步执行展示：生成检索语句、混合检索、流式诊断三步状态可视，每步成功打勾、失败标红，检索明细表可逐行核对加权得分
- 参考医案溯源：诊断结果可关联到具体医案出处（文件名与标题层级）及原文预览
- 双界面：Vue3 + Vite 单页前端（对接 FastAPI SSE 接口），以及保留的 Streamlit 界面

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端接口 | Python 3.10+、FastAPI、Uvicorn、SSE 流式响应 |
| 检索与推理 | LangChain、FAISS（faiss-cpu）、rank-bm25、jieba、DashScope（阿里云百炼） |
| 前端 | Vue 3、Vite |
| 备用界面 | Streamlit |
| 测试 | pytest |

## 项目结构

```text
├── api.py                     # FastAPI 接口层（SSE 流式诊断，默认 8010 端口）
├── app.py                     # Streamlit 界面（备用入口，问诊单 + 诊断展示）
├── config.py                  # 模型、路径、检索参数配置
├── requirements.txt           # Python 依赖清单
├── kb/
│   ├── loader.py              # MD 医案按标题层级加载与切分
│   ├── builder.py             # 知识库构建与产物加载（FAISS / chunks / BM25）
│   ├── retriever.py           # 向量 + BM25 混合检索器（含 MMR 去冗余）
│   └── mcp_retriever.py       # MCP 知识库检索客户端
├── pipeline/
│   ├── form_query.py          # 问诊单转检索语句
│   └── diagnoser.py           # 医案证据结合的流式辨证诊断与结构化解析
├── scripts/
│   └── build_kb.py            # 知识库构建脚本（离线执行）
├── frontend/                  # Vue3 + Vite 前端
│   ├── src/App.vue            # 问诊单与三步诊断展示
│   ├── src/main.js
│   └── vite.config.js         # /api 代理到 127.0.0.1:8010
├── data/medical_cases/        # MD 格式医案文件（知识库语料）
├── storage/kb/                # 知识库产物（index.faiss / index.pkl / chunks.json / bm25.pkl）
├── tests/                     # pytest 测试用例与测试文档
└── spec/                      # 功能方案与变更记录（spec-001 ~ spec-012）
```

## 环境要求

- Python 3.10 及以上
- Node.js 18 及以上（Vue 前端）

安装 Python 依赖（版本与开发环境一致）：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

安装前端依赖：

```bash
cd frontend
npm install
```

## 配置

在项目根目录创建 `.env` 文件（已列入 .gitignore，不会提交）：

```text
DASHSCOPE_API_KEY=你的阿里云百炼API Key

# 以下为可选配置，不填则使用默认值
MCP_ENABLED=false
MCP_SERVER_URL=http://127.0.0.1:8000/mcp
MCP_SEARCH_TOOL=search
MCP_TIMEOUT_SECONDS=60
```

模型与检索参数见 config.py：

- 问诊推理模型：qwen3.8-27b（经 DashScope OpenAI 兼容模式端点调用）
- 向量化模型：text-embedding-v3
- `MCP_ENABLED` 为 true 时以 MCP 知识库为唯一检索源；为 false 时使用本地 FAISS + BM25 混合检索

## 使用步骤

1. 将 MD 格式医案放入 `data/medical_cases/` 目录（支持一级到四级标题的医书或医案文件）
2. 构建知识库：

```bash
python scripts/build_kb.py
```

3. 启动后端接口：

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8010
```

4. 启动前端：

```bash
cd frontend
npm run dev
```

5. 浏览器打开 http://localhost:5173，填写问诊单并点击「开始诊断」

如需使用 Streamlit 界面（不依赖 Node.js）：

```bash
streamlit run app.py
```

浏览器打开 http://localhost:8501。

## 运行测试

```bash
python -m pytest tests/ -q                 # 离线用例（默认跳过 integration）
python -m pytest tests/ -m integration -q  # 集成用例（需 .env Key 与已构建知识库）
```

共 62 个用例（59 离线 + 3 集成），覆盖知识库构建、混合检索融合、检索词生成、问诊单校验、SSE 事件流等正常、异常与边界场景。详见 `tests/测试文档.md`。

## 免责声明

本项目仅用于中医知识学习与技术演示，诊断结果由 AI 模型基于医案文本生成，不构成医疗建议，实际诊疗请咨询执业中医师。

---

# English Version

[中文](#中医ai问诊平台) | [English](#english-version)

An online Traditional Chinese Medicine (TCM) consultation system built on RAG (Retrieval-Augmented Generation) over classic physician case records. The patient fills in a structured intake form organized by the four diagnostic methods (observation, listening/smelling, inquiry, palpation). The system converts the form into standardized TCM terminology queries, performs hybrid retrieval over the medical case knowledge base, and then lets the LLM reason over the retrieved evidence to produce a structured diagnosis.

## Features

- Four-diagnosis structured intake form: basic information, observation and palpation (complexion / tongue body / tongue coating / pulse), chills and fever with sweating, head-body-chest-abdomen complaints, appetite and taste, sleep and emotions, stool/urine and menstruation, other accompanying symptoms
- Query generation: the LLM condenses the intake form into a standardized TCM query of at most 80 characters (in MCP mode, into space-separated keywords)
- Hybrid retrieval: FAISS vector search (weight 0.6) + jieba-tokenized BM25 keyword search (weight 0.4), normalized weighted fusion followed by MMR de-duplication, returning the top 6 case snippets with per-channel score breakdowns
- MCP knowledge base retrieval: a switch makes an external MCP knowledge base the sole retrieval source, with word-by-word degradation retries under AND semantics
- Streaming syndrome differentiation: reasoning over the retrieved evidence from the eight principles (exterior/interior, cold/heat, deficiency/excess, yin/yang), zang-fu organs, and qi-blood-fluids perspectives; outputs syndrome type (tagged with eight-principle attributes), treatment principle, recommended formula with modifications, nursing advice, and cited case evidence
- Step-by-step execution display: query generation, hybrid retrieval, and streaming diagnosis are shown as three visible steps with success/failure states; the retrieval detail table allows row-by-row verification of weighted scores
- Case traceability: diagnosis results link back to specific case sources (file name and heading hierarchy) with original text previews
- Dual interfaces: a Vue 3 + Vite single-page frontend backed by FastAPI SSE endpoints, plus a retained Streamlit interface

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend API | Python 3.10+, FastAPI, Uvicorn, SSE streaming |
| Retrieval and reasoning | LangChain, FAISS (faiss-cpu), rank-bm25, jieba, DashScope (Alibaba Cloud Bailian) |
| Frontend | Vue 3, Vite |
| Alternative UI | Streamlit |
| Testing | pytest |

## Project Structure

```text
├── api.py                     # FastAPI layer (SSE streaming diagnosis, default port 8010)
├── app.py                     # Streamlit UI (alternative entry: intake form + diagnosis display)
├── config.py                  # Model, path, and retrieval parameter configuration
├── requirements.txt           # Python dependency list
├── kb/
│   ├── loader.py              # Loads and splits MD cases by heading hierarchy
│   ├── builder.py             # Knowledge base construction and artifact loading (FAISS / chunks / BM25)
│   ├── retriever.py           # Vector + BM25 hybrid retriever (with MMR de-duplication)
│   └── mcp_retriever.py       # MCP knowledge base retrieval client
├── pipeline/
│   ├── form_query.py          # Intake form to retrieval query
│   └── diagnoser.py           # Streaming syndrome differentiation and structured parsing
├── scripts/
│   └── build_kb.py            # Knowledge base build script (run offline)
├── frontend/                  # Vue 3 + Vite frontend
│   ├── src/App.vue            # Intake form and three-step diagnosis display
│   ├── src/main.js
│   └── vite.config.js         # Proxies /api to 127.0.0.1:8010
├── data/medical_cases/        # MD case files (knowledge base corpus)
├── storage/kb/                # Knowledge base artifacts (index.faiss / index.pkl / chunks.json / bm25.pkl)
├── tests/                     # pytest test cases and test documentation
└── spec/                      # Design specs and change records (spec-001 to spec-012)
```

## Requirements

- Python 3.10 or later
- Node.js 18 or later (Vue frontend)

Install Python dependencies (versions match the development environment):

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

## Configuration

Create a `.env` file in the project root (already listed in .gitignore and never committed):

```text
DASHSCOPE_API_KEY=your Alibaba Cloud Bailian API key

# Optional settings, defaults apply when omitted
MCP_ENABLED=false
MCP_SERVER_URL=http://127.0.0.1:8000/mcp
MCP_SEARCH_TOOL=search
MCP_TIMEOUT_SECONDS=60
```

Model and retrieval parameters live in config.py:

- Reasoning model: qwen3.8-27b (called through the DashScope OpenAI-compatible endpoint)
- Embedding model: text-embedding-v3
- When `MCP_ENABLED` is true, the MCP knowledge base is the sole retrieval source; when false, local FAISS + BM25 hybrid retrieval is used

## Usage

1. Put MD case files into `data/medical_cases/` (heading levels 1 to 4 are supported)
2. Build the knowledge base:

```bash
python scripts/build_kb.py
```

3. Start the backend API:

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8010
```

4. Start the frontend:

```bash
cd frontend
npm run dev
```

5. Open http://localhost:5173 in a browser, fill in the intake form, and click "开始诊断" (Start Diagnosis)

To use the Streamlit interface instead (no Node.js required):

```bash
streamlit run app.py
```

Then open http://localhost:8501.

## Running Tests

```bash
python -m pytest tests/ -q                 # Offline cases (integration skipped by default)
python -m pytest tests/ -m integration -q  # Integration cases (requires .env key and a built knowledge base)
```

62 test cases in total (59 offline + 3 integration), covering knowledge base construction, hybrid retrieval fusion, query generation, intake form validation, and SSE event streams across normal, exceptional, and boundary scenarios. See `tests/测试文档.md` for details.

## Disclaimer

This project is intended solely for TCM knowledge learning and technical demonstration. Diagnosis results are generated by an AI model based on case texts and do not constitute medical advice. For actual treatment, please consult a licensed TCM practitioner.
