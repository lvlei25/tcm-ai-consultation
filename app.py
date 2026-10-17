# -*- coding: utf-8 -*-
"""中医在线问诊系统主界面：问诊单填写 + RAG 诊断结果展示"""
import streamlit as st

from config import TOP_K
from kb.builder import load_knowledge_base
from kb.retriever import HybridRetriever
from pipeline.diagnoser import (
    SECTION_TITLES,
    parse_diagnosis_sections,
    stream_diagnosis,
)
from pipeline.form_query import generate_query, validate_form

st.set_page_config(page_title="中医在线问诊系统", layout="wide")

# ===== 页面样式：渐变头部与红色提交按钮 =====
st.markdown(
    """
    <style>
    .tcm-header {
        background: linear-gradient(90deg, #7b2ff7 0%, #f107a3 100%);
        border-radius: 12px;
        padding: 28px 20px;
        text-align: center;
        color: #ffffff;
        margin-bottom: 24px;
    }
    .tcm-header h1 {margin: 0; font-size: 2rem; letter-spacing: 2px;}
    .tcm-header p {margin: 6px 0 0; font-size: 0.9rem; opacity: 0.92;}
    [data-testid="stFormSubmitButton"] button {
        background-color: #e63946;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 0.4rem 1.4rem;
        font-weight: 600;
    }
    [data-testid="stFormSubmitButton"] button:hover {
        background-color: #d62839;
        color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="tcm-header"><h1>中医在线问诊系统</h1>'
    "<p>基于名老中医医案 RAG 系统 | 结构化问诊单 · 向量检索 + LLM 推理</p></div>",
    unsafe_allow_html=True,
)


# ===== 知识库加载（进程内缓存一次） =====
@st.cache_resource(show_spinner="正在加载医案知识库 ...")
def get_retriever() -> HybridRetriever:
    """加载知识库产物并构造混合检索器"""
    faiss_store, chunks, bm25 = load_knowledge_base()
    return HybridRetriever(faiss_store, chunks, bm25)


try:
    retriever = get_retriever()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()


# ===== 问诊单表单（按四诊与十问组织，服务八纲/脏腑/气血津液辨证） =====
st.markdown("#### 中医问诊单")
with st.form("consult_form"):
    st.markdown("##### 基本信息")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        name = st.text_input("姓名（选填）", placeholder="请输入姓名")
    with b2:
        gender = st.radio("性别", options=["男", "女"], horizontal=True)
    with b3:
        age = st.number_input("年龄", min_value=0, max_value=120, value=30, step=1)
    with b4:
        duration = st.selectbox(
            "病程", options=["1天内", "1周内", "1月内", "半年内", "1年以上"]
        )

    st.markdown("##### 望诊与切诊（舌、面、脉）")
    w1, w2, w3, w4 = st.columns(4)
    with w1:
        face = st.selectbox(
            "面色", options=["正常", "萎黄", "苍白", "㿠白", "潮红", "晦暗"]
        )
    with w2:
        tongue_body = st.selectbox(
            "舌质", options=["淡红", "淡白", "红", "绛", "紫暗", "淡胖有齿痕"]
        )
    with w3:
        tongue_coat = st.selectbox(
            "舌苔", options=["薄白", "薄黄", "白厚", "黄厚", "少苔", "剥苔"]
        )
    with w4:
        pulse = st.text_input("脉象（选填）", placeholder="示例：脉细弱")

    st.markdown("##### 问寒热与汗出")
    h1, h2 = st.columns(2)
    with h1:
        cold_heat = st.selectbox(
            "寒热",
            options=["无特殊", "畏寒怕冷", "发热", "恶寒发热", "寒热往来", "五心烦热"],
        )
    with h2:
        sweating = st.selectbox(
            "汗出", options=["正常", "无汗", "自汗", "盗汗", "动则汗出"]
        )

    st.markdown("##### 问头身胸腹")
    torso = st.pills(
        "头身胸腹不适",
        options=["头晕", "头痛", "胸闷", "心悸", "胁胀", "脘腹胀满", "腰膝酸软", "身重困倦", "关节酸痛"],
        selection_mode="multi",
    )

    st.markdown("##### 问饮食口味")
    d1, d2, d3 = st.columns(3)
    with d1:
        diet = st.selectbox(
            "饮食", options=["正常", "纳呆食少", "多食易饥", "饥不欲食", "食后腹胀"]
        )
    with d2:
        thirst = st.selectbox(
            "口渴", options=["不渴", "口干欲饮", "渴喜冷饮", "渴喜热饮", "渴不欲饮"]
        )
    with d3:
        taste = st.selectbox(
            "口味", options=["正常", "口苦", "口淡", "口甜", "口酸", "口黏"]
        )

    st.markdown("##### 问睡眠情志")
    s1, s2 = st.columns(2)
    with s1:
        sleep = st.selectbox(
            "睡眠", options=["正常", "入睡困难", "多梦易醒", "早醒", "嗜睡"]
        )
    with s2:
        emotion = st.selectbox(
            "情志", options=["平稳", "急躁易怒", "情绪低落", "焦虑不安", "多思多虑"]
        )

    st.markdown("##### 问二便与经期")
    u1, u2, u3 = st.columns(3)
    with u1:
        stool = st.selectbox(
            "大便", options=["正常", "干结", "便秘", "溏薄", "腹泻", "先干后溏"]
        )
    with u2:
        urine = st.selectbox(
            "小便", options=["正常", "小便短赤", "小便清长", "尿频", "夜尿多", "淋沥不畅"]
        )
    with u3:
        menstruation = st.selectbox(
            "经期（女性）",
            options=["不适用", "正常", "提前", "推后", "先后不定期", "痛经", "闭经"],
        )

    chief_complaint = st.text_area(
        "主诉（主要不适症状、必填）",
        placeholder="例如：反复入睡困难，多梦易醒，白天精神不振",
        height=90,
    )
    history = st.text_area("既往史 / 过敏史（选填）", placeholder="手术史、慢性病史、药物过敏等", height=70)

    st.markdown("##### 其他伴随症状")
    symptoms = st.pills(
        "选择适用的症状",
        options=["咳嗽", "乏力", "气短", "咽干", "目眩", "耳鸣", "食不知味", "肢体麻木", "下肢水肿"],
        selection_mode="multi",
        label_visibility="collapsed",
    )

    submit = st.form_submit_button("开始诊断")

# 汇总问诊单数据（结构对应四诊信息，供检索词生成与辨证推理使用）
form_dict = {
    "姓名": name.strip(),
    "性别": gender,
    "年龄": int(age),
    "病程": duration,
    "望诊": {"面色": face, "舌质": tongue_body, "舌苔": tongue_coat},
    "脉象": pulse.strip(),
    "寒热": cold_heat,
    "汗出": sweating,
    "头身胸腹不适": list(torso),
    "饮食": diet,
    "口渴": thirst,
    "口味": taste,
    "睡眠": sleep,
    "情志": emotion,
    "大便": stool,
    "小便": urine,
    "经期": menstruation,
    "主诉": chief_complaint.strip(),
    "既往史": history.strip(),
    "其他伴随症状": list(symptoms),
}


def render_evidences(evidences: list[dict], query: str = "") -> None:
    """展示检索语句与参考医案来源折叠列表（含向量分/关键词分明细）"""
    if query:
        st.caption(f"本次检索语句：{query}")
    with st.expander("参考医案来源", expanded=False):
        for i, ev in enumerate(evidences, start=1):
            meta = ev["metadata"]
            origin = " > ".join(
                str(value) for key, value in meta.items() if key != "source" and value
            )
            st.markdown(
                f"**[{i}] {meta.get('source', '未知医案')}** {origin}"
                f"（融合 {ev['score']:.3f} · 向量 {ev.get('vec_score', 0.0):.3f}"
                f" · 关键词 {ev.get('bm25_score', 0.0):.3f}）"
            )
            preview = ev["text"][:200] + ("..." if len(ev["text"]) > 200 else "")
            st.text(preview)


def render_sections(sections: dict) -> None:
    """按小节折叠展示结构化诊断结果"""
    with st.expander("按小节查看诊断结果", expanded=False):
        for title in SECTION_TITLES:
            st.markdown(f"**{title}**")
            st.markdown(sections[title])


# ===== 诊断结果区域 =====
st.markdown("---")
st.markdown("### 诊断结果")

if submit:
    errors = validate_form(form_dict)
    if errors:
        for err in errors:
            st.warning(err)
    else:
        # 步骤 1：将问诊单整理为检索语句
        with st.status("步骤 1/3 生成检索语句", expanded=True) as step1:
            st.write("正在调用大模型将问诊单整理为检索语句 ...")
            try:
                query = generate_query(form_dict)
                st.markdown(f"生成的检索语句：**{query}**")
                step1.update(label="步骤 1/3 生成检索语句 完成", state="complete", expanded=False)
            except Exception as exc:
                st.error(f"生成检索语句失败：{exc}")
                step1.update(label="步骤 1/3 生成检索语句 失败", state="error")
                st.stop()

        # 步骤 2：向量 + 关键词混合检索医案
        with st.status("步骤 2/3 混合检索医案", expanded=True) as step2:
            st.write(f"正在以检索语句进行混合检索（向量 + 关键词，取前 {TOP_K} 条）...")
            try:
                evidences = retriever.retrieve(query)
                if evidences:
                    rows = []
                    for i, ev in enumerate(evidences, start=1):
                        meta = ev["metadata"]
                        origin = " > ".join(
                            str(value)
                            for key, value in meta.items()
                            if key != "source" and value
                        )
                        rows.append(
                            {
                                "编号": f"[{i}]",
                                "出处": meta.get("source", "未知医案"),
                                "标题层级": origin,
                                "向量分": round(ev.get("vec_score", 0.0), 3),
                                "关键词分": round(ev.get("bm25_score", 0.0), 3),
                                "融合分": round(ev["score"], 3),
                            }
                        )
                    st.dataframe(rows, hide_index=True)
                else:
                    st.warning("未检索到相关医案片段，诊断将仅基于问诊单信息进行")
                step2.update(label="步骤 2/3 混合检索医案 完成", state="complete", expanded=False)
            except Exception as exc:
                st.error(f"混合检索失败：{exc}")
                step2.update(label="步骤 2/3 混合检索医案 失败", state="error")
                st.stop()

        # 步骤 3：结合医案证据流式生成诊断，完成后解析为结构化小节
        with st.status("步骤 3/3 生成诊断结果", expanded=True) as step3:
            st.write("正在结合医案证据流式生成诊断 ...")
            try:
                result = st.write_stream(stream_diagnosis(form_dict, evidences))
                sections = parse_diagnosis_sections(result)
                step3.update(label="步骤 3/3 生成诊断结果 完成", state="complete")
            except Exception as exc:
                st.error(f"生成诊断失败：{exc}")
                step3.update(label="步骤 3/3 生成诊断结果 失败", state="error")
                st.stop()

        # 保存本次诊断结果，避免页面交互后丢失
        st.session_state["diagnosis_result"] = result
        st.session_state["diagnosis_sections"] = sections
        st.session_state["diagnosis_evidences"] = evidences
        st.session_state["diagnosis_query"] = query
        render_sections(sections)
        render_evidences(evidences, query)
elif "diagnosis_result" in st.session_state:
    # 复显最近一次诊断结果
    st.markdown(st.session_state["diagnosis_result"])
    if "diagnosis_sections" in st.session_state:
        render_sections(st.session_state["diagnosis_sections"])
    render_evidences(
        st.session_state.get("diagnosis_evidences", []),
        st.session_state.get("diagnosis_query", ""),
    )
else:
    st.info("请填写问诊单并点击「开始诊断」，诊断结果将显示在此处。")
