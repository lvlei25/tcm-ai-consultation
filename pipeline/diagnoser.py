# -*- coding: utf-8 -*-
"""诊断推理：结合问诊单与检索到的医案证据，以名老中医视角流式生成诊断结果"""
import json

from langchain_openai import ChatOpenAI

from config import DASHSCOPE_BASE_URL, LLM_MODEL, get_api_key

# 诊断推理的系统提示词
_DIAGNOSIS_SYSTEM_PROMPT = (
    "你是一位经验丰富的名老中医，正在为患者进行在线问诊辨证。"
    "请严格依据【医案证据】中的真实医案经验，结合【问诊单】信息进行辨证，"
    "按以下固定结构输出（Markdown 格式，全程使用中文）：\n"
    "## 辨证分析\n（结合四诊信息，从八纲（表里寒热虚实阴阳）、脏腑、气血津液角度分析病因病机）\n"
    "## 证型诊断\n（给出主要证型及兼证，标注八纲属性，如：心脾两虚（里虚证））\n"
    "## 治法\n（确定治则治法）\n"
    "## 推荐方药与加减\n（给出参考方剂组成与随症加减，注明本建议仅供医师参考）\n"
    "## 调护建议\n（饮食、起居、情志调养）\n"
    "## 引用医案依据\n（列出所引用证据编号及对应医案要点，如 [1][3]）\n"
    "若证据不足以确定证型，需在辨证分析中说明不确定之处。"
)


def format_evidences(evidences: list[dict]) -> str:
    """将检索到的证据列表格式化为带编号的证据文本块（纯函数，便于测试）"""
    lines = []
    for i, ev in enumerate(evidences, start=1):
        meta = ev["metadata"]
        origin = " > ".join(
            str(value) for key, value in meta.items() if key != "source" and value
        )
        lines.append(
            f"[{i}] 出处：{meta.get('source', '未知医案')} {origin}\n内容：{ev['text']}"
        )
    return "\n\n".join(lines) if lines else "（未检索到相关医案证据）"


def build_diagnosis_messages(form: dict, evidences: list[dict]) -> list:
    """构造诊断推理的消息列表（纯函数，便于测试）"""
    user_content = (
        f"【问诊单】\n{json.dumps(form, ensure_ascii=False, indent=2)}\n\n"
        f"【医案证据】\n{format_evidences(evidences)}"
    )
    return [("system", _DIAGNOSIS_SYSTEM_PROMPT), ("user", user_content)]


def stream_diagnosis(form: dict, evidences: list[dict]):
    """流式生成诊断结果，逐段 yield 文本，供 st.write_stream 消费"""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.3,
        streaming=True,
        api_key=get_api_key(),
        base_url=DASHSCOPE_BASE_URL,
    )
    for chunk in llm.stream(build_diagnosis_messages(form, evidences)):
        if chunk.content:
            yield chunk.content
