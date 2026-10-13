# 中医 AI 问诊平台搭建方案

## Context

从零搭建一个"中医在线问诊系统"（用户已提供界面截图）：患者填写结构化问诊单，点击「开始诊断」后，系统将问诊单交给 LLM 转换为检索 query，从名老中医医案知识库（MD 医案构建）中做向量+BM25 混合检索，再把检索证据交给 LLM 推理，将诊断结果流式渲染到问诊单下方的「诊断结果」区域。

已确认选型：
- 模型服务：阿里云百炼 DashScope（qwen-plus 推理 + text-embedding-v3 向量化），API Key 写入 .env 的 `DASHSCOPE_API_KEY`
- 界面：Streamlit 1.64（st.pills 多选标签、st.write_stream 流式输出、自定义 CSS 渐变头部还原截图）
- 检索：FAISS 向量检索 + jieba 分词 BM25 关键词检索加权融合（0.6/0.4）
- 依赖全部已安装，无需新装

## 项目结构

```
k:\douyin_assistant\douyin_assiatan\
├── .env                        # 用户填写 DASHSCOPE_API_KEY=sk-xxx
├── config.py                   # 读取 .env（手写解析，不引入 python-dotenv）、模型名/路径/top_k 常量
├── app.py                      # Streamlit 主界面：问诊单 + 诊断结果区域
├── kb/
│   ├── __init__.py
│   ├── loader.py               # 扫描 data/medical_cases/*.md，MarkdownHeaderTextSplitter 按标题切分 + RecursiveCharacterTextSplitter 控长（chunk_size≈500，overlap≈80），元数据含书名(文件名)+标题路径
│   ├── builder.py              # 构建知识库：分块 → DashScopeEmbeddings 批量向量化 → FAISS 落盘；jieba 分词语料 + BM25Okapi → pickle 落盘（storage/kb/）
│   └── retriever.py            # HybridRetriever：FAISS top_n=20 + BM25 top_n=20，分数归一化加权融合去重取 top_k=6
├── pipeline/
│   ├── __init__.py
│   ├── form_query.py           # 问诊单结构化字段 → ChatTongyi(qwen-plus, 低温度) 生成一句≤80字中医证候检索 query
│   └── diagnoser.py            # 问诊单 + 检索证据 → 名老中医 system prompt → 流式生成诊断（辨证分析/证型/治法/参考方药与加减/调护建议/引用依据）
├── scripts/
│   └── build_kb.py             # 离线构建入口：python scripts/build_kb.py
├── data/
│   └── medical_cases/          # 用户放置 MD 医案的目录（空目录 + .gitkeep）
└── storage/
    └── kb/                     # 构建产物：faiss_index/、chunks.json、bm25.pkl（运行时生成）
```

## 实现步骤

### 1. config.py
- 手写 .env 解析（逐行 `KEY=VALUE`，忽略空行/#注释），写入 os.environ，供 langchain-community 的 DashScope 系列自动读取
- 常量：`MEDICAL_CASES_DIR`、`KB_DIR`、`EMBEDDING_MODEL="text-embedding-v3"`、`LLM_MODEL="qwen-plus"`、`TOP_K=6`、`VECTOR_WEIGHT=0.6`
- 缺少 DASHSCOPE_API_KEY 时抛出明确的中文异常

### 2. kb/loader.py + kb/builder.py
- loader：`MarkdownHeaderTextSplitter(headers_to_split_on=[("#","章"),("##","节"),("###","条")])`，再 `RecursiveCharacterTextSplitter` 控长；每块 Document metadata：`{"source": 文件名, "章": …, "节": …, "条": …}`
- builder：
  - 向量侧：`DashScopeEmbeddings(model=EMBEDDING_MODEL)` + `FAISS.from_documents(...)`，`save_local(KB_DIR/"faiss_index")`
  - BM25 侧：`jieba.lcut` 分词 → `BM25Okapi`，chunks 列表存 `chunks.json`，BM25 对象与分词存 `bm25.pkl`
  - 构建完成后打印统计（文件数、块数）
- `load_knowledge_base()`：从 storage/kb 加载 FAISS（`allow_dangerous_deserialization=True`）与 BM25，供 app 用 `@st.cache_resource` 缓存

### 3. kb/retriever.py
- `retrieve(query, top_k)`：向量检索（`similarity_search_with_score`，距离转相似度）与 BM25 打分各自取前 20，min-max 归一化后加权融合，按 source+内容去重，返回 `[(Document, 融合分)]`

### 4. pipeline/form_query.py
- 输入问诊单字典（姓名/年龄/性别/病程/舌象/寒热/主诉/既往史/睡眠/饮食/大便/小便/伴随症状）
- ChatTongyi(qwen-plus, temperature=0.2) 生成检索 query：包含主症、舌象特征、寒热、二便饮食睡眠、伴随症状，用中医术语表述，≤80 字

### 5. pipeline/diagnoser.py
- system prompt：名老中医角色，必须结合所给医案证据辨证，输出固定结构：辨证分析 / 证型诊断 / 治法 / 推荐方药与加减 / 调护建议 / 引用医案依据（编号）
- user prompt：问诊单 JSON + 编号后的检索证据（含出处）
- `stream_diagnosis(...)` 生成器：ChatTongyi `streaming=True` 逐段 yield，供 `st.write_stream` 消费

### 6. scripts/build_kb.py
- 调 kb.loader + kb.builder；data/medical_cases/ 无 .md 文件时打印中文提示并退出
- 运行前清空 storage/kb 旧产物，避免索引与语料不一致

### 7. app.py（还原截图 UI）
- 自定义 CSS 渐变头部（紫→粉红 linear-gradient）：「中医在线问诊系统」+ 副标题「基于名老中医医案 RAG 系统 | 结构化问诊单 · 向量检索 + LLM 推理」
- 表单用 `st.form`：
  - 三列：姓名 text_input（选填）｜年龄 number_input(默认30)｜舌象 text_input（placeholder 示例）
  - 三列：性别 radio 横排(男/女)｜病程 selectbox(1天内/1周内/1月内/半年内/1年以上)｜寒热 text_input（placeholder 示例）
  - 主诉 text_area（必填，placeholder 示例）｜既往史/过敏史 text_area（选填）
  - 四列：睡眠/饮食/大便/小便 selectbox（正常 + 常见异常选项）
  - 伴随症状 `st.pills(selection_mode="multi")`：咳嗽/乏力/头晕/心悸/口干/自汗/盗汗/怕冷/食不知味
  - `st.form_submit_button("开始诊断")`
- 诊断结果区域：
  - 初始：`st.info("请填写问诊单并点击「开始诊断」，诊断结果将显示在此处。")`
  - 主诉未填：中文警告
  - 提交后：`st.spinner` + `st.write_stream` 流式渲染诊断；完成后 `st.expander("参考医案来源")` 列出证据出处（文件名+标题路径+融合得分）
  - `session_state` 保存上次诊断结果与来源，避免页面交互后丢失
- 知识库未构建时 `st.stop` 并提示先运行 `python scripts/build_kb.py`

## 数据流

```
问诊单填写 → [form_query] qwen-plus 生成检索 query
          → [retriever] FAISS(0.6) + BM25(0.4) 混合检索 top_k=6 医案片段
          → [diagnoser] qwen-plus 结合证据流式推理
          → app.py 「诊断结果」区域流式渲染 + 参考医案来源
```

## 验证

1. 用户将 MD 医案放入 `data/medical_cases/`，运行 `python scripts/build_kb.py`，确认输出块数统计且 storage/kb 生成三件产物
2. .env 填入 `DASHSCOPE_API_KEY`
3. `streamlit run app.py` 启动，浏览器打开，核对界面与截图还原度（头部渐变、三列/四列布局、pills 标签、红色提交按钮）
4. 填写问诊单点击「开始诊断」，确认：query 生成 → 检索 → 流式诊断输出 → 参考医案来源折叠列表
5. 用 browser_use 截图对比截图效果，验证中文无乱码
## 测试
建立的单独的测试用例文件就，撰写测试文档，准备20个以上测试用例，包含正常情况、异常情况、边界情况，测试系统在不同场景下的表现。
包括但不限用，知识库检索，问诊单整理，诊断结果输出。

## 注意事项

- 全部代码注释用中文、UTF-8、无 emoji、无 fallback 逻辑
- 依赖已全部安装，不新建 requirements/说明文档
- 用户尚未提供 MD 医案文件：实现完成后请用户将医案放入 data/medical_cases/，若用户在实现时已提供则直接使用
