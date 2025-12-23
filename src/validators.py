\
from __future__ import annotations
from typing import Any, Dict, List, Tuple

QTYPE_MC = "Trắc nghiệm nhiều lựa chọn"
QTYPE_TF = "Đúng/Sai"
QTYPE_MATCH = "Nối cột"
QTYPE_FILL = "Điền khuyết"
QTYPE_ESSAY = "Tự luận"

def validate_question(qtype: str, obj: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Trả (ok, message). Validator cứng để đảm bảo cấu trúc sư phạm tối thiểu.
    """
    if not isinstance(obj, dict):
        return False, "Nội dung câu hỏi không phải JSON object."

    stem = (obj.get("stem") or "").strip()
    if not stem:
        return False, "Thiếu 'stem' (nội dung câu hỏi)."

    if qtype == QTYPE_MC:
        options = obj.get("options")
        if not isinstance(options, dict):
            return False, "MCQ: thiếu 'options' dạng object."
        for k in ["A", "B", "C", "D"]:
            if not (options.get(k) or "").strip():
                return False, f"MCQ: thiếu phương án {k}."
        ans = (obj.get("correct_answer") or "").strip().upper()
        if ans not in ["A", "B", "C", "D"]:
            return False, "MCQ: 'correct_answer' phải là A/B/C/D."
        return True, "OK"

    if qtype == QTYPE_TF:
        tf = obj.get("true_false")
        if not isinstance(tf, list) or len(tf) < 2:
            return False, "Đúng/Sai: cần ít nhất 2 mệnh đề trong 'true_false'."
        for i, it in enumerate(tf, 1):
            if not isinstance(it, dict):
                return False, f"Đúng/Sai: mệnh đề {i} không hợp lệ."
            if not (it.get("statement") or "").strip():
                return False, f"Đúng/Sai: thiếu statement ở mệnh đề {i}."
            if not isinstance(it.get("answer"), bool):
                return False, f"Đúng/Sai: answer ở mệnh đề {i} phải là true/false."
        return True, "OK"

    if qtype == QTYPE_MATCH:
        mt = obj.get("matching")
        if not isinstance(mt, dict):
            return False, "Nối cột: thiếu 'matching' dạng object."
        left = mt.get("left")
        right = mt.get("right")
        ans = mt.get("answer")
        if not isinstance(left, list) or len(left) < 2:
            return False, "Nối cột: 'left' phải có ít nhất 2 mục."
        if not isinstance(right, list) or len(right) < 2:
            return False, "Nối cột: 'right' phải có ít nhất 2 mục."
        if not isinstance(ans, dict) or len(ans) < 2:
            return False, "Nối cột: 'answer' phải có mapping tối thiểu 2 cặp."
        return True, "OK"

    if qtype == QTYPE_FILL:
        fb = obj.get("fill_blank")
        if not isinstance(fb, dict):
            return False, "Điền khuyết: thiếu 'fill_blank' dạng object."
        text = (fb.get("text") or "")
        if "____" not in text:
            return False, "Điền khuyết: 'text' phải có chỗ trống '____'."
        if not (fb.get("answer") or "").strip():
            return False, "Điền khuyết: thiếu đáp án 'answer'."
        return True, "OK"

    if qtype == QTYPE_ESSAY:
        es = obj.get("essay")
        if not isinstance(es, dict):
            return False, "Tự luận: thiếu 'essay' dạng object."
        if not (es.get("prompt") or "").strip():
            return False, "Tự luận: thiếu 'prompt'."
        rubric = es.get("rubric")
        if rubric is not None and not isinstance(rubric, list):
            return False, "Tự luận: 'rubric' nếu có phải là list."
        return True, "OK"

    return False, f"Không hỗ trợ dạng câu hỏi: {qtype}"
