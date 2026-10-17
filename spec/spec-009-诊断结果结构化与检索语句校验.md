# spec-009：诊断结果结构化与检索语句校验

对应基线：spec-001、spec-003、spec-004

## 变更原因

1. 诊断结果是纯 Markdown 文本流，`app.py` 只能整体渲染，无法按小节导出、核对或断言，
   spec-008 的输出结构校验也只能靠字符串匹配
2. 检索语句「≤80 字」仅写在提示词里，模型超长时无任何代码侧校验或提示

## 设计依据

- 提示词要求模型输出固定六小节，可据此做确定性解析（不做语义兜底）
- 解析失败按 spec-001「无 fallback」约束抛出明确中文异常，由 `st.status` 标红展示
- 检索语句长度校验放在 `generate_query` 返回前，超长即抛错，不做截断（避免静默改变语义）

## 变更内容

| 文件 | 变更 |
|------|------|
| pipeline/diagnoser.py | 新增 `SECTION_TITLES` 常量（六个小节标题）与 `parse_diagnosis_sections(text)`：按 `## ` 标题切分为 {标题: 正文} 字典 |
| pipeline/diagnoser.py | `stream_diagnosis` 保持流式 yield 不变；新增 `stream_diagnosis_structured()`：流式结束后返回 `(全文, 小节字典)` |
| pipeline/form_query.py | 新增 `MAX_QUERY_LEN = 80` 常量与 `check_query_length(query)`：超过则抛明确中文异常 |
| pipeline/form_query.py | `generate_query()` 返回前调用长度校验 |
| app.py | 步骤 3 完成后，除全文渲染外，按小节字典以 `st.expander` 分块展示（辨证分析/证型诊断/治法/推荐方药与加减/调护建议/引用医案依据） |
| config.py | 不新增常量（长度与标题常量就近定义在各自模块） |

## 验证

- `python -m pytest tests/ -q` 全量通过，新增解析与校验用例见 spec-008
- 单元级：`parse_diagnosis_sections` 对完整六小节文本解析出 6 个键；缺小节时抛明确中文异常
- `check_query_length` 对 81 字抛错、80 字通过
- 浏览器实测：诊断结果按小节折叠展示，内容与原全文一致

## 注意事项

- 不做静默兜底：解析失败或超长一律抛错并显示原文错误，不生成替代内容
- 流式输出逻辑保持 `st.write_stream` 兼容，不破坏 spec-003 的分步展示

## 验证结果（2026-10-17 执行）

- `python -m py_compile app.py pipeline/diagnoser.py pipeline/form_query.py` 通过
- `python -m pytest tests/ -q` → 44 passed, 3 deselected（新增用例 45~47）
- 界面（AppTest 覆盖 app.py 全量渲染）：分组标题、诊断区域渲染正常，无运行异常
- 检索语句超长时 `generate_query` 抛出明确中文异常，由步骤 1 的 st.status 标红展示
- 诊断六小节折叠展示入口为「按小节查看诊断结果」expander，全文流式渲染保持不变
