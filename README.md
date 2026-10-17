# 中医AI问诊平台

基于名老中医医案 RAG（检索增强生成）的在线中医问诊系统。患者填写按四诊（望闻问切）组织的结构化问诊单，系统将问诊单转换为规范中医术语检索语句，从本地医案知识库中混合检索相关医案片段，再由大模型结合医案证据进行辨证推理，输出结构化诊断结果。

## 功能特性

- 四诊结构化问诊单：基本信息、望诊与切诊（面色/舌质/舌苔/脉象）、问寒热汗出、问头身胸腹、问饮食口味、问睡眠情志、问二便与经期、其他伴随症状
- 检索语句生成：大模型将问诊单整理为不超过 80 字的规范中医术语检索语句
- 混合检索：FAISS 向量检索（权重 0.6）+ jieba 分词 BM25 关键词检索（权重 0.4），归一化加权融合，返回带两路得分明细的前 6 条医案片段
- 流式辨证诊断：结合医案证据，从八纲（表里寒热虚实阴阳）、脏腑、气血津液角度辨证分析，输出证型（标注八纲属性）、治法、推荐方药与加减、调护建议、引用医案依据
- 分步执行展示：生成检索语句、混合检索、流式诊断三步状态可视，每步成功打勾、失败标红，检索明细表可逐行核对加权得分
- 参考医案溯源：诊断结果可关联到具体医案出处（文件名与标题层级）及原文预览

## 项目结构

```text
├── app.py                     # Streamlit 前端入口（问诊单、分步诊断流程展示）
├── config.py                  # 模型、路径、检索参数配置
├── kb/
│   ├── loader.py              # MD 医案按标题层级加载与切分
│   ├── builder.py             # 知识库构建与产物加载（FAISS / chunks / BM25）
│   └── retriever.py           # 向量 + BM25 混合检索器
├── pipeline/
│   ├── form_query.py          # 问诊单转检索语句
│   └── diagnoser.py           # 医案证据结合问诊单的流式辨证诊断
├── scripts/
│   └── build_kb.py            # 知识库构建脚本（离线执行）
├── data/medical_cases/        # MD 格式医案文件（知识库语料）
├── storage/kb/                # 知识库产物（index.faiss / index.pkl / chunks.json / bm25.pkl）
├── tests/                     # pytest 测试用例与测试文档
└── spec/                      # 功能方案与变更记录（spec-001 ~ spec-004）
```

## 环境要求

- Python 3.10 及以上
- 依赖清单见 requirements.txt（版本与开发环境一致），安装命令：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 配置

在项目根目录创建 `.env` 文件（已列入 .gitignore，不会提交）：

```text
DASHSCOPE_API_KEY=你的阿里云百炼API Key
```

模型配置见 config.py：

- 问诊推理模型：qwen3.8-27b（经 DashScope OpenAI 兼容模式端点调用）
- 向量化模型：text-embedding-v3

## 使用步骤

1. 将 MD 格式医案放入 `data/medical_cases/` 目录（支持一级到四级标题的医书或医案文件）
2. 构建知识库：

```bash
python scripts/build_kb.py
```

3. 启动应用：

```bash
streamlit run app.py
```

4. 浏览器打开 http://localhost:8501，填写问诊单并点击「开始诊断」

## 运行测试

```bash
python -m pytest tests/ -q
```

测试覆盖知识库构建、混合检索融合逻辑、检索词生成、问诊单校验等 32 个用例（正常、异常、边界场景）。

## 免责声明

本项目仅用于中医知识学习与技术演示，诊断结果由 AI 模型基于医案文本生成，不构成医疗建议，实际诊疗请咨询执业中医师。
