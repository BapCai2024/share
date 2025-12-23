\
from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple
import re
import pandas as pd

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_EXTRACTED = DATA_DIR / "ppct" / "ppct_k5_extracted.csv"

def _extract_ppct_from_pdf_bytes(pdf_bytes: bytes) -> pd.DataFrame:
    """
    Trích số tiết theo bài từ PDF K5 (kế hoạch dạy học lớp 5).
    Cố gắng bắt pattern 'Bài xx ... (n tiết)'.
    """
    if PdfReader is None:
        raise RuntimeError("Thiếu thư viện pypdf. Hãy cài requirements.txt")

    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t:
            texts.append(t)
    full = "\n".join(texts)

    subjects = [
        ("Tiếng Việt", r"Môn\s+TIẾNG\s+VIỆT|Môn\s+Tiếng\s+Việt"),
        ("Toán", r"Môn\s+TOÁN|Môn\s+Toán"),
        ("Lịch sử và Địa lí", r"Môn\s+LỊCH\s+SỬ\s+VÀ\s+ĐỊA\s+LÍ|Môn\s+Lịch\s+sử\s+và\s+Địa\s+lí"),
        ("Khoa học", r"Môn\s+KHOA\s+HỌC|Môn\s+Khoa\s+học"),
        ("Tin học", r"Môn\s+TIN\s+HỌC|Môn\s+Tin\s+học"),
        ("Công nghệ", r"Môn\s+CÔNG\s+NGHỆ|Môn\s+Công\s+nghệ"),
    ]

    idxs = []
    for name, pat in subjects:
        m = re.search(pat, full, flags=re.I)
        if m:
            idxs.append((m.start(), name))
    idxs.sort()
    sections = {}
    for i, (start, name) in enumerate(idxs):
        end = idxs[i+1][0] if i+1 < len(idxs) else len(full)
        sections[name] = full[start:end]

    pat1 = re.compile(r"Bài\s*(\d{1,3})\s*[:\-–]?\s*([^\(\n\r]{0,120}?)\s*\(\s*(\d{1,2})\s*tiết\s*\)", flags=re.I)
    pat2 = re.compile(r"Bài\s*(\d{1,3})\s*[:\-–]?\s*([^\n\r]{0,120}?)\s*(\d{1,2})\s*tiết\b", flags=re.I)

    rows = []
    for subj, sec in sections.items():
        seen = {}
        for m in pat1.finditer(sec):
            num = int(m.group(1))
            title = re.sub(r"\s+", " ", m.group(2)).strip(" -–:;,.")
            periods = int(m.group(3))
            if (subj, num) not in seen:
                seen[(subj, num)] = (title, periods)

        for m in pat2.finditer(sec):
            num = int(m.group(1))
            if (subj, num) in seen:
                continue
            title = re.sub(r"\s+", " ", m.group(2)).strip(" -–:;,.")
            periods = int(m.group(3))
            if title and len(title) >= 3:
                seen[(subj, num)] = (title, periods)

        for (s, num), (title, periods) in sorted(seen.items(), key=lambda x: x[0][1]):
            rows.append({"Mon": s, "Bai_so": num, "Ten_bai_trich_xuat": title, "So_tiet": periods, "Nguon": "K5.pdf"})

    return pd.DataFrame(rows)

def load_ppct(extracted_csv: Path = DEFAULT_EXTRACTED) -> pd.DataFrame:
    """
    Load PPCT đã trích sẵn (CSV). Nếu không có thì trả DataFrame rỗng.
    """
    if extracted_csv.exists():
        df = pd.read_csv(extracted_csv)
        return df
    return pd.DataFrame(columns=["Mon","Bai_so","Ten_bai_trich_xuat","So_tiet","Nguon"])

def extract_and_save_from_upload(uploaded_pdf, out_csv: Path = DEFAULT_EXTRACTED) -> pd.DataFrame:
    """
    Nhận PDF upload (Streamlit UploadedFile), trích PPCT và lưu CSV để lần sau dùng.
    """
    pdf_bytes = uploaded_pdf.getvalue()
    df = _extract_ppct_from_pdf_bytes(pdf_bytes)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return df

def _lesson_num_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d{1,3})", str(text))
    return int(m.group(1)) if m else None

def find_periods(ppct_df: pd.DataFrame, subject: str, lesson_text: str) -> Tuple[Optional[int], str]:
    """
    Tìm số tiết dựa vào môn + số bài. Trả (so_tiet, note).
    """
    n = _lesson_num_from_text(lesson_text)
    if n is None:
        return None, "Không lấy được số bài từ trường 'Bài'."
    cand = ppct_df[(ppct_df["Mon"] == subject) & (ppct_df["Bai_so"] == n)]
    if len(cand) == 0:
        return None, f"Không tìm thấy Bài {n} trong PPCT của môn {subject}."
    so_tiet = int(cand["So_tiet"].iloc[0])
    title = str(cand["Ten_bai_trich_xuat"].iloc[0])
    return so_tiet, f"Khớp PPCT: Bài {n} – {title}."
