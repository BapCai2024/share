\
from __future__ import annotations
import json
import uuid
from dataclasses import asdict
from typing import Dict, Any, List

import streamlit as st
import pandas as pd

from src.data import load_yccd
from src.ppct import load_ppct, extract_and_save_from_upload, find_periods
from src.gemini import generate_json, GeminiError
from src.validators import (
    validate_question,
    QTYPE_MC, QTYPE_TF, QTYPE_MATCH, QTYPE_FILL, QTYPE_ESSAY
)
from src.export_docx import export_exam_docx

APP_TITLE = "V1.1 – Tool ra đề Lớp 5 (AI Studio Gemini) • Streamlit"
LEVELS_TT27 = ["M1 – Nhận biết", "M2 – Kết nối", "M3 – Vận dụng"]
# Map hiển thị -> nhãn gọn
LEVEL_KEY = {"M1 – Nhận biết": "M1", "M2 – Kết nối": "M2", "M3 – Vận dụng": "M3"}

QTYPES = [QTYPE_MC, QTYPE_TF, QTYPE_MATCH, QTYPE_FILL, QTYPE_ESSAY]

def init_state():
    st.session_state.setdefault("matrix_rows", [])  # list[dict]
    st.session_state.setdefault("exam", [])         # list[dict]
    st.session_state.setdefault("last_dataset_hash", "")
    st.session_state.setdefault("ppct_df", None)
    st.session_state.setdefault("ppct_source_note", "")


def compute_ratio_points(rows: List[Dict[str, Any]], mode: str, block1_points: float, block2_points: float):
    """
    mode:
      - "Toàn đề (10 điểm)"
      - "2 block (2,5 / 7,5)"
    Yêu cầu: rows có 'so_tiet' (int) và (nếu 2 block) có 'block' = 1/2.
    Ghi vào rows: 'ti_le', 'so_diem'
    """
    # reset
    for r in rows:
        r["ti_le"] = None
        r["so_diem"] = None

    if mode == "Toàn đề (10 điểm)":
        total = sum(int(r.get("so_tiet") or 0) for r in rows)
        if total <= 0:
            return rows, "Tổng số tiết = 0. Hãy điền Số tiết trước."
        for r in rows:
            stt = int(r.get("so_tiet") or 0)
            r["ti_le"] = round(stt * 100.0 / total, 4)
            r["so_diem"] = round(r["ti_le"] * 10.0 / 100.0, 5)
        return rows, "OK"
    else:
        # 2 blocks
        b1 = [r for r in rows if int(r.get("block") or 1) == 1]
        b2 = [r for r in rows if int(r.get("block") or 1) == 2]
        t1 = sum(int(r.get("so_tiet") or 0) for r in b1)
        t2 = sum(int(r.get("so_tiet") or 0) for r in b2)
        if (t1 <= 0 and len(b1)>0) or (t2 <= 0 and len(b2)>0):
            return rows, "Thiếu Số tiết trong một block. Hãy điền/auto-fill trước."
        if len(b1)>0 and t1>0:
            for r in b1:
                stt = int(r.get("so_tiet") or 0)
                r["ti_le"] = round(stt * 100.0 / t1, 4)
                r["so_diem"] = round(r["ti_le"] * float(block1_points) / 100.0, 5)
        if len(b2)>0 and t2>0:
            for r in b2:
                stt = int(r.get("so_tiet") or 0)
                r["ti_le"] = round(stt * 100.0 / t2, 4)
                r["so_diem"] = round(r["ti_le"] * float(block2_points) / 100.0, 5)
        return rows, "OK"


def points_options(step=0.5, max_point=10.0):
    vals = []
    x = step
    while x <= max_point + 1e-9:
        vals.append(round(x, 2))
        x += step
    return vals

def build_prompt(meta: Dict[str, Any]) -> str:
    """
    Prompt bám TT27 3 mức (M1/M2/M3) và yêu cầu trả JSON đúng schema.
    """
    qtype = meta["qtype"]
    level = meta["level"]
    subject = meta["subject"]
    topic = meta["topic"]
    lesson = meta["lesson"]
    yccd = meta["yccd"]
    grade = meta.get("grade", 5)
    pts = meta["points"]

    level_desc = {
        "M1": "Nhận biết: nhắc lại/mô tả/áp dụng trực tiếp trong tình huống quen thuộc.",
        "M2": "Kết nối: kết nối/sắp xếp kiến thức để giải quyết vấn đề tương tự.",
        "M3": "Vận dụng: vận dụng kiến thức vào tình huống mới/gần thực tế.",
    }[LEVEL_KEY[level]]

    schema = f"""
Trả về DUY NHẤT 1 JSON object (không markdown, không giải thích thêm ngoài JSON), theo dạng {qtype}:

- Với Trắc nghiệm nhiều lựa chọn:
{{
  "stem": "...",
  "options": {{"A":"...","B":"...","C":"...","D":"..."}},
  "correct_answer": "A|B|C|D",
  "explanation": "Giải thích ngắn gọn."
}}

- Với Đúng/Sai:
{{
  "stem": "...",
  "true_false": [{{"statement":"...","answer":true}},{{"statement":"...","answer":false}}],
  "explanation": "Giải thích ngắn gọn."
}}

- Với Nối cột:
{{
  "stem": "Nối cột A với cột B cho phù hợp: ...",
  "matching": {{
     "left": ["1) ...","2) ...","3) ...","4) ..."],
     "right": ["A) ...","B) ...","C) ...","D) ..."],
     "answer": {{"1":"A","2":"B","3":"C","4":"D"}}
  }},
  "explanation": "Giải thích ngắn gọn."
}}

- Với Điền khuyết:
{{
  "stem": "...",
  "fill_blank": {{"text":"... ____ ...", "answer":"..."}},
  "explanation": "Giải thích ngắn gọn."
}}

- Với Tự luận:
{{
  "stem": "...",
  "essay": {{"prompt":"...", "rubric":["Ý 1 (x điểm)","Ý 2 (y điểm)"]}},
  "explanation": "Gợi ý/nhận xét ngắn."
}}

Ràng buộc sư phạm:
- Phù hợp học sinh lớp {grade}, câu văn rõ, không mẹo, không mơ hồ.
- Bám sát YCCĐ: {yccd}
- Mức độ theo TT27: {level_desc}
- Điểm câu: {pts} điểm.
"""
    user = f"""
Môn: {subject}
Chủ đề: {topic}
Bài: {lesson}
YCCĐ: {yccd}
Dạng: {qtype}
Mức: {level} ({LEVEL_KEY[level]})
Điểm: {pts}

{schema}
"""
    return user.strip()

def offline_question(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback khi không có API key: tạo câu theo mẫu cấu trúc để test pipeline.
    """
    qtype = meta["qtype"]
    level_short = LEVEL_KEY[meta["level"]]
    yccd = meta["yccd"]

    if qtype == QTYPE_MC:
        return {
            "stem": f"({level_short}) Chọn đáp án đúng: {yccd}",
            "options": {"A": "Phương án A", "B": "Phương án B", "C": "Phương án C", "D": "Phương án D"},
            "correct_answer": "A",
            "explanation": "Giải thích ngắn gọn theo nội dung bài học."
        }
    if qtype == QTYPE_TF:
        return {
            "stem": f"({level_short}) Đánh dấu Đ/S theo yêu cầu: {yccd}",
            "true_false": [{"statement": "Mệnh đề 1", "answer": True}, {"statement": "Mệnh đề 2", "answer": False}],
            "explanation": "Giải thích ngắn gọn."
        }
    if qtype == QTYPE_MATCH:
        return {
            "stem": f"({level_short}) Nối cột A với cột B cho phù hợp: {yccd}",
            "matching": {
                "left": ["1) A1", "2) A2", "3) A3", "4) A4"],
                "right": ["A) B1", "B) B2", "C) B3", "D) B4"],
                "answer": {"1": "A", "2": "B", "3": "C", "4": "D"},
            },
            "explanation": "Giải thích ngắn gọn."
        }
    if qtype == QTYPE_FILL:
        return {
            "stem": f"({level_short}) Điền vào chỗ trống: {yccd}",
            "fill_blank": {"text": "Nội dung ____ cần điền.", "answer": "đáp án"},
            "explanation": "Giải thích ngắn gọn."
        }
    return {
        "stem": f"({level_short}) Trả lời: {yccd}",
        "essay": {"prompt": "Viết câu trả lời đầy đủ.", "rubric": ["Ý 1 (0,5–1 điểm)", "Ý 2 (0,5–1 điểm)"]},
        "explanation": "Gợi ý chấm."
    }

def make_question(meta: Dict[str, Any], api_key: str, model: str, api_base: str, temperature: float, max_tokens: int):
    prompt = build_prompt(meta)
    if api_key:
        obj = generate_json(prompt, api_key=api_key, model=model, api_base=api_base,
                           temperature=temperature, max_output_tokens=max_tokens)
    else:
        obj = offline_question(meta)

    ok, msg = validate_question(meta["qtype"], obj)
    if not ok:
        # nếu AI trả sai cấu trúc -> fallback offline để không "kẹt"
        obj = offline_question(meta)
        ok2, msg2 = validate_question(meta["qtype"], obj)
        return obj, False, f"AI trả chưa đạt ({msg}). Dùng mẫu tạm để test."
    return obj, True, "OK"

# ---------------- UI ----------------
st.set_page_config(page_title=APP_TITLE, layout="wide")
init_state()
st.title(APP_TITLE)

with st.sidebar:
    st.subheader("AI Studio Gemini")
    api_key = st.text_input("GEMINI_API_KEY", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    model = st.text_input("Model", value=st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash"))
    api_base = st.text_input("API base", value=st.secrets.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"))
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05)
    max_tokens = st.slider("Max output tokens", 256, 2048, 1024, 128)

    st.divider()
    st.subheader("Dữ liệu YCCĐ")
    up = st.file_uploader("Upload khoi5_normalized (.csv/.xlsx) (tuỳ chọn)", type=["csv","xlsx"])
    st.caption("Nếu không upload, app dùng data/khoi5_normalized.csv trong repo.")

    st.divider()
    st.subheader("PPCT / Số tiết (từ K5.pdf)")
    ppct_pdf = st.file_uploader("Upload K5.pdf (tuỳ chọn) để trích số tiết", type=["pdf"], key="ppct_pdf")
    use_extracted = st.checkbox("Dùng ppct_k5_extracted.csv trong repo (khuyến nghị)", value=True)
    if use_extracted or ppct_pdf is None:
        ppct_df = load_ppct()
        st.session_state.ppct_df = ppct_df
        st.session_state.ppct_source_note = "Đang dùng data/ppct/ppct_k5_extracted.csv"
    else:
        try:
            ppct_df = extract_and_save_from_upload(ppct_pdf)
            st.session_state.ppct_df = ppct_df
            st.session_state.ppct_source_note = "Đã trích từ K5.pdf upload và lưu vào data/ppct/ppct_k5_extracted.csv"
        except Exception as e:
            st.warning(f"Không trích được từ PDF: {e}")
            st.session_state.ppct_df = load_ppct()
            st.session_state.ppct_source_note = "Fallback: dùng CSV trích sẵn (nếu có)"
    st.caption(st.session_state.ppct_source_note)


# Load dataset
try:
    df = load_yccd(up)
except Exception as e:
    st.error(str(e))
    st.stop()

tabs = st.tabs(["1) Ma trận (tối giản)", "2) Tạo đề & chỉnh sửa", "3) Tải xuống"])

# ---- Tab 1: Matrix builder (minimal) ----
with tabs[0]:
    st.subheader("Tạo ma trận tối giản theo YCCĐ (để test V1.1)")
    st.caption("Mỗi dòng = 1 YCCĐ + cấu hình dạng/mức/điểm/số câu. Đây là bản tối giản để chạy trên GitHub + Streamlit Cloud.")

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        subject = st.selectbox("Môn", sorted(df["Môn"].unique().tolist()))
    df_s = df[df["Môn"] == subject].copy()

    with c2:
        topic = st.selectbox("Chủ đề/Chủ điểm", sorted(df_s["Chủ đề/Chủ điểm"].unique().tolist()))
    df_t = df_s[df_s["Chủ đề/Chủ điểm"] == topic].copy()

    with c3:
        lesson = st.selectbox("Bài", sorted(df_t["Bài"].unique().tolist(), key=lambda x: (len(x), x)))
    df_l = df_t[df_t["Bài"] == lesson].copy()

    lesson_name = df_l["Tên bài học"].iloc[0] if len(df_l) else ""
    st.write(f"**Tên bài học:** {lesson_name}")

    # gợi ý số tiết từ PPCT (nếu có)
    ppct_df_state = st.session_state.get("ppct_df")
    so_tiet_suggest = None
    so_tiet_note = ""
    if ppct_df_state is not None and len(ppct_df_state) > 0:
        so_tiet_suggest, so_tiet_note = find_periods(ppct_df_state, subject, str(lesson))
    if so_tiet_suggest is not None:
        st.info(f"Gợi ý số tiết: **{so_tiet_suggest}**. {so_tiet_note}")


    yccd = st.selectbox("YCCĐ", df_l["Yêu cầu cần đạt"].tolist())

    cA, cB, cC, cD = st.columns([1,1,1,1])
    with cA:
        qtype = st.selectbox("Dạng câu hỏi", QTYPES)
    with cB:
        level = st.selectbox("Mức độ (TT27)", LEVELS_TT27)
    with cC:
        points = st.selectbox("Điểm (mặc định – có thể tính từ số tiết)", points_options(0.5, 5.0), index=0)
    with cD:
        n_questions = st.number_input("Số câu", min_value=1, max_value=10, value=1, step=1)
    cE, cF = st.columns([1,1])
    with cE:
        so_tiet_manual = st.number_input("Số tiết (auto từ K5 nếu có)", min_value=0, max_value=10, value=0, step=1)
    with cF:
        block = st.selectbox("Block (tính tỉ lệ/điểm)", [1,2], index=0)


    if st.button("➕ Thêm vào ma trận", type="primary"):
        st.session_state.matrix_rows.append({
            "id": str(uuid.uuid4())[:8],
            "subject": subject,
            "topic": topic,
            "lesson": f"Bài {lesson}: {lesson_name}".strip(),
            "yccd": yccd,
            "qtype": qtype,
            "level": level,
            "points": float(points),
            "n": int(n_questions),
            "so_tiet": int(so_tiet_suggest) if (so_tiet_manual == 0 and so_tiet_suggest is not None) else int(so_tiet_manual),
            "block": int(block),
            "ti_le": None,
            "so_diem": None,
        })
        st.success("Đã thêm 1 dòng vào ma trận.")

    if st.session_state.matrix_rows:
        st.markdown("### Ma trận hiện tại")
        mdf = pd.DataFrame(st.session_state.matrix_rows)
        st.dataframe(mdf.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)

        colx1, colx2, colx3, colx4 = st.columns([1,1,1,1])
        with colx1:
            if st.button("🧠 Auto-fill Số tiết từ K5 (PPCT)"):
                ppct_df_state = st.session_state.get("ppct_df")
                if ppct_df_state is None or len(ppct_df_state) == 0:
                    st.warning("Chưa có PPCT. Hãy upload K5.pdf hoặc dùng CSV trích sẵn ở sidebar.")
                else:
                    new_rows = []
                    for r in st.session_state.matrix_rows:
                        if int(r.get("so_tiet") or 0) > 0:
                            new_rows.append(r); continue
                        so_tiet, note = find_periods(ppct_df_state, r.get("subject",""), r.get("lesson",""))
                        r["so_tiet"] = int(so_tiet) if so_tiet is not None else 0
                        r["so_tiet_note"] = note
                        new_rows.append(r)
                    st.session_state.matrix_rows = new_rows
                    st.success("Đã auto-fill Số tiết (những dòng khớp được).")
        with colx2:
            mode = st.selectbox("Chế độ tính tỉ lệ/điểm", ["Toàn đề (10 điểm)", "2 block (2,5 / 7,5)"], index=1)
        with colx3:
            b1p = st.number_input("Điểm block 1", min_value=0.0, max_value=10.0, value=2.5, step=0.5)
        with colx4:
            b2p = st.number_input("Điểm block 2", min_value=0.0, max_value=10.0, value=7.5, step=0.5)

        if st.button("🧮 Tính Tỉ lệ & Số điểm theo số tiết"):
            rows, msg = compute_ratio_points(st.session_state.matrix_rows, mode, b1p, b2p)
            st.session_state.matrix_rows = rows
            if msg == "OK":
                st.success("Đã tính tỉ lệ & số điểm.")
            else:
                st.warning(msg)

        colx1, colx2 = st.columns([1,1])
        with colx1:
            if st.button("🧹 Xoá toàn bộ ma trận"):
                st.session_state.matrix_rows = []
                st.success("Đã xoá ma trận.")
        with colx2:
            st.caption("Bước tiếp theo: sang Tab 2 để tạo đề theo ma trận.")

# ---- Tab 2: Generate + edit ----
with tabs[1]:
    st.subheader("Tạo đề theo ma trận & chỉnh sửa")
    if not st.session_state.matrix_rows:
        st.info("Chưa có ma trận. Hãy thêm dòng ở Tab 1.")
        st.stop()

    colg1, colg2, colg3 = st.columns([1,1,1])
    with colg1:
        meta_title = st.text_input("Tiêu đề đề", value="ĐỀ KIỂM TRA ĐỊNH KÌ")
    with colg2:
        meta_time = st.text_input("Thời gian (phút)", value="40")
    with colg3:
        grade = st.selectbox("Lớp", [5], index=0)

    # Build blueprint
    blueprint = []
    for row in st.session_state.matrix_rows:
        for _ in range(int(row["n"])):
            pts = float(row.get("so_diem")) if row.get("so_diem") not in (None, "", 0) else float(row.get("points", 1))
            blueprint.append({
                "subject": row["subject"],
                "topic": row["topic"],
                "lesson": row["lesson"],
                "yccd": row["yccd"],
                "qtype": row["qtype"],
                "level": row["level"],
                "points": pts,
            })

    st.caption(f"Số câu theo ma trận: **{len(blueprint)}**")

    colb1, colb2, colb3 = st.columns([1,1,1])
    with colb1:
        if st.button("⚙️ TẠO ĐỀ", type="primary"):
            st.session_state.exam = []
            for meta in blueprint:
                qobj, ok, msg = make_question(meta, api_key, model, api_base, temperature, max_tokens)
                st.session_state.exam.append({
                    "qtype": meta["qtype"],
                    "level": meta["level"],
                    "points": meta["points"],
                    "subject": meta["subject"],
                    "topic": meta["topic"],
                    "lesson": meta["lesson"],
                    "yccd": meta["yccd"],
                    "content": qobj,
                    "status": "OK" if ok else msg,
                })
            st.success("Đã tạo đề xong.")
    with colb2:
        if st.button("🔁 TẠO LẠI ĐỀ (giữ form)"):
            if not st.session_state.exam:
                st.warning("Chưa có đề. Bấm TẠO ĐỀ trước.")
            else:
                new_exam = []
                for q in st.session_state.exam:
                    meta = {k: q[k] for k in ["subject","topic","lesson","yccd","qtype","level","points"]}
                    qobj, ok, msg = make_question(meta, api_key, model, api_base, temperature, max_tokens)
                    new_exam.append({**q, "content": qobj, "status": "OK" if ok else msg})
                st.session_state.exam = new_exam
                st.success("Đã tạo lại đề (giữ form).")
    with colb3:
        st.caption("Không có API key vẫn chạy (offline mẫu cấu trúc) để bạn test xuất Word.")

    st.divider()
    if not st.session_state.exam:
        st.info("Chưa có đề. Bấm TẠO ĐỀ.")
        st.stop()

    total_points = sum(float(q["points"]) for q in st.session_state.exam)
    st.write(f"**Tổng câu:** {len(st.session_state.exam)}  •  **Tổng điểm (tham chiếu):** {total_points}")

    st.markdown("### Chỉnh sửa nhanh từng câu")
    for idx, q in enumerate(st.session_state.exam, 1):
        with st.expander(f"Câu {idx} • {q['qtype']} • {q['level']} • {q['points']} điểm  ({q.get('status','')})", expanded=False):
            content = q["content"]
            # edit stem
            stem = st.text_area("Stem", value=content.get("stem",""), key=f"stem_{idx}", height=80)
            content["stem"] = stem

            if q["qtype"] == QTYPE_MC:
                opts = content.get("options", {"A":"","B":"","C":"","D":""})
                for k in ["A","B","C","D"]:
                    opts[k] = st.text_input(f"Option {k}", value=opts.get(k,""), key=f"opt_{idx}_{k}")
                content["options"] = opts
                content["correct_answer"] = st.selectbox("Đáp án đúng", ["A","B","C","D"],
                                                        index=["A","B","C","D"].index((content.get("correct_answer") or "A")),
                                                        key=f"ans_{idx}")
            elif q["qtype"] == QTYPE_TF:
                tf = content.get("true_false", [])
                if len(tf) < 2:
                    tf = [{"statement":"","answer":True},{"statement":"","answer":False}]
                for j in range(len(tf)):
                    tf[j]["statement"] = st.text_input(f"Mệnh đề {j+1}", value=tf[j].get("statement",""), key=f"tf_s_{idx}_{j}")
                    tf[j]["answer"] = st.selectbox(f"Đ/S {j+1}", [True, False],
                                                   index=0 if tf[j].get("answer", True) else 1,
                                                   key=f"tf_a_{idx}_{j}")
                content["true_false"] = tf
            elif q["qtype"] == QTYPE_MATCH:
                mt = content.get("matching", {"left": [], "right": [], "answer": {}})
                left = mt.get("left", [])
                right = mt.get("right", [])
                # enforce 4 lines editor
                n = st.number_input("Số cặp (khuyến nghị 4)", min_value=2, max_value=8, value=max(4, len(left), len(right)), step=1, key=f"mt_n_{idx}")
                while len(left) < n: left.append("")
                while len(right) < n: right.append("")
                for j in range(n):
                    left[j] = st.text_input(f"Cột A {j+1}", value=left[j], key=f"mt_l_{idx}_{j}")
                    right[j] = st.text_input(f"Cột B {j+1}", value=right[j], key=f"mt_r_{idx}_{j}")
                mt["left"], mt["right"] = left, right
                # answer mapping
                letters = [chr(ord("A")+i) for i in range(n)]
                ans = mt.get("answer", {})
                for j in range(n):
                    ans[str(j+1)] = st.selectbox(f"Đáp án cho {j+1}", letters, index=min(j, n-1), key=f"mt_a_{idx}_{j}")
                mt["answer"] = ans
                content["matching"] = mt
            elif q["qtype"] == QTYPE_FILL:
                fb = content.get("fill_blank", {"text":"", "answer":""})
                fb["text"] = st.text_area("Văn bản (có ____)", value=fb.get("text",""), key=f"fb_t_{idx}", height=70)
                fb["answer"] = st.text_input("Đáp án", value=fb.get("answer",""), key=f"fb_a_{idx}")
                content["fill_blank"] = fb
            else:
                es = content.get("essay", {"prompt":"", "rubric":[]})
                es["prompt"] = st.text_area("Đề bài tự luận", value=es.get("prompt",""), key=f"es_p_{idx}", height=80)
                rb = es.get("rubric", [])
                rb_text = "\n".join([str(x) for x in rb]) if rb else ""
                rb_text = st.text_area("Rubric (mỗi ý 1 dòng)", value=rb_text, key=f"es_r_{idx}", height=90)
                es["rubric"] = [x.strip() for x in rb_text.splitlines() if x.strip()]
                content["essay"] = es

            ok, msg = validate_question(q["qtype"], content)
            if ok:
                st.success("Validator: OK")
            else:
                st.error(f"Validator: {msg}")
            st.session_state.exam[idx-1]["content"] = content

# ---- Tab 3: Export ----
with tabs[2]:
    st.subheader("Tải xuống")
    if not st.session_state.exam:
        st.info("Chưa có đề để tải.")
        st.stop()

    meta = {
        "title": st.text_input("Tiêu đề (xuất Word)", value="ĐỀ KIỂM TRA ĐỊNH KÌ"),
        "subject": st.session_state.exam[0].get("subject",""),
        "grade": 5,
        "time": st.text_input("Thời gian (phút)", value="40", key="time_export"),
    }

    docx_bytes = export_exam_docx(meta, st.session_state.exam)
    st.download_button("⬇️ Tải Đề (DOCX)", data=docx_bytes, file_name="De_kiem_tra_lop5.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    session = {"matrix_rows": st.session_state.matrix_rows, "exam": st.session_state.exam}
    st.download_button("⬇️ Tải session.json", data=json.dumps(session, ensure_ascii=False, indent=2),
                       file_name="session.json", mime="application/json")
