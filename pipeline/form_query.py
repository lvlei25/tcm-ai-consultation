# -*- coding: utf-8 -*-
"""问诊单整理：校验问诊单必填项，并将结构化问诊单转换为知识库检索 query"""
import json

from langchain_openai import ChatOpenAI

from config import DASHSCOPE_BASE_URL, LLM_MODEL, get_api_key

# 生成检索 query 的系统提示词
_QUERY_SYSTEM_PROMPT = (
    "你是中医医案检索词生成器。请将患者问诊单整理为一句用于检索名老中医医案的中文检索语句。"
    "要求：1.使用规范中医术语（如不寐、心脾两虚、纳呆等）；"
    "2.涵盖主诉、望诊舌面、脉象、寒热汗出、头身胸腹、饮食口味、睡眠情志、二便经期、伴随症状中的关键信息；"
    "3.不超过80字；4.只输出检索语句本身，不要任何解释和标点引号。"
)


def validate_form(form: dict) -> list[str]:
    """校验问诊单必填项，返回错误信息列表（空列表表示通过）"""
    errors = []
    chief = (form.get("主诉") or "").strip()
    if not chief:
        errors.append("主诉为必填项，请填写主要不适症状")
    return errors


def build_query_messages(form: dict) -> list:
    """根据问诊单构造生成检索词的消息列表（纯函数，便于测试）"""
    user_content = "问诊单信息：\n" + json.dumps(form, ensure_ascii=False, indent=2)
    return [("system", _QUERY_SYSTEM_PROMPT), ("user", user_content)]


def generate_query(form: dict) -> str:
    """调用大模型将问诊单转换为检索 query，返回检索语句文本"""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.2,
        api_key=get_api_key(),
        base_url=DASHSCOPE_BASE_URL,
    )
    response = llm.invoke(build_query_messages(form))
    return response.content.strip()
