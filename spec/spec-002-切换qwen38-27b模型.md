# spec-002：问诊推理模型切换为 qwen3.8-27b

对应基线：spec-001-中医AI问诊平台搭建.md

## 变更原因

用户指定问诊推理与检索词生成模型使用 `qwen3.8-27b`。

## 排查过程

1. 仅改 config.py 的 LLM_MODEL 后调用报错：`400 InvalidParameter, url error` —— langchain-community 的 ChatTongyi 走 DashScope 原生端点，该新模型未在原生端点路由
2. 查询账号可用模型列表确认 `qwen3.8-27b` 存在（另有 qwen3.5-27b、qwen3.6-27b）
3. 经 OpenAI 兼容模式端点 `https://dashscope.aliyuncs.com/compatible-mode/v1` 调用成功

## 变更内容

| 文件 | 变更 |
|------|------|
| config.py | `LLM_MODEL` 改为 `qwen3.8-27b`；新增 `DASHSCOPE_BASE_URL` 兼容模式端点常量 |
| pipeline/form_query.py | ChatTongyi（原生端点）→ ChatOpenAI（兼容模式，带 base_url） |
| pipeline/diagnoser.py | 同上，流式参数 streaming=True 保留 |

向量化模型 text-embedding-v3 不变（DashScopeEmbeddings 原生端点可用）。

## 验证结果

- 冒烟：检索词生成（"反复不寐入睡困难多梦易醒神疲乏力"）与流式诊断（213 段）均正常
- 浏览器端到端：诊断 6 小节齐全、检索语句 caption 显示、参考医案来源 [1]~[6] 带出处与相关度分数、无错误无乱码
