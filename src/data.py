\
from __future__ import annotations
import pandas as pd
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "khoi5_normalized.csv"
DEFAULT_XLSX = Path(__file__).resolve().parents[1] / "data" / "khoi5_normalized.xlsx"

# Chuẩn cột tối thiểu (sau khi chuẩn hoá tên cột)
REQUIRED_COLS = ["Môn", "Chủ đề/Chủ điểm", "Bài", "Tên bài học", "Yêu cầu cần đạt"]

# Các biến thể thường gặp -> chuẩn hoá
COL_ALIASES = {
    "mon": "Môn",
    "môn": "Môn",
    "chu de": "Chủ đề/Chủ điểm",
    "chủ đề": "Chủ đề/Chủ điểm",
    "chu de/chu diem": "Chủ đề/Chủ điểm",
    "chủ đề/chủ điểm": "Chủ đề/Chủ điểm",
    "bai": "Bài",
    "bài": "Bài",
    "bai hoc": "Tên bài học",
    "bài học": "Tên bài học",
    "ten bai hoc": "Tên bài học",
    "tên bài học": "Tên bài học",
    "yccd": "Yêu cầu cần đạt",
    "yeu cau can dat": "Yêu cầu cần đạt",
    "yêu cầu cần đạt": "Yêu cầu cần đạt",
    "yêu cầu cần đạt (tóm tắt)": "Yêu cầu cần đạt",
}

def _norm_col(c: str) -> str:
    c = str(c).strip()
    c = c.replace("_", " ")
    c = " ".join(c.split())
    return c

def _key_col(c: str) -> str:
    c = _norm_col(c).lower()
    # bỏ dấu tiếng Việt thô (chỉ phục vụ mapping alias cơ bản)
    c = (c.replace("đ", "d")
           .replace("á", "a").replace("à", "a").replace("ả", "a").replace("ã", "a").replace("ạ", "a")
           .replace("ă", "a").replace("ắ", "a").replace("ằ", "a").replace("ẳ", "a").replace("ẵ", "a").replace("ặ", "a")
           .replace("â", "a").replace("ấ", "a").replace("ầ", "a").replace("ẩ", "a").replace("ẫ", "a").replace("ậ", "a")
           .replace("é", "e").replace("è", "e").replace("ẻ", "e").replace("ẽ", "e").replace("ẹ", "e")
           .replace("ê", "e").replace("ế", "e").replace("ề", "e").replace("ể", "e").replace("ễ", "e").replace("ệ", "e")
           .replace("í", "i").replace("ì", "i").replace("ỉ", "i").replace("ĩ", "i").replace("ị", "i")
           .replace("ó", "o").replace("ò", "o").replace("ỏ", "o").replace("õ", "o").replace("ọ", "o")
           .replace("ô", "o").replace("ố", "o").replace("ồ", "o").replace("ổ", "o").replace("ỗ", "o").replace("ộ", "o")
           .replace("ơ", "o").replace("ớ", "o").replace("ờ", "o").replace("ở", "o").replace("ỡ", "o").replace("ợ", "o")
           .replace("ú", "u").replace("ù", "u").replace("ủ", "u").replace("ũ", "u").replace("ụ", "u")
           .replace("ư", "u").replace("ứ", "u").replace("ừ", "u").replace("ử", "u").replace("ữ", "u").replace("ự", "u")
           .replace("ý", "y").replace("ỳ", "y").replace("ỷ", "y").replace("ỹ", "y").replace("ỵ", "y"))
    return c

def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for c in df.columns:
        k = _key_col(c)
        if k in COL_ALIASES:
            rename[c] = COL_ALIASES[k]
        else:
            # giữ nguyên nếu đã đúng
            rename[c] = _norm_col(c)
    df = df.rename(columns=rename)
    return df

def load_yccd(uploaded_file=None) -> pd.DataFrame:
    """
    Load kho YCCĐ lớp 5 (đã chuẩn hoá). Ưu tiên file upload (csv/xlsx), fallback về data/.
    """
    if uploaded_file is not None:
        name = (uploaded_file.name or "").lower()
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        elif name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError("Chỉ hỗ trợ .csv hoặc .xlsx")
    else:
        if DEFAULT_CSV.exists():
            df = pd.read_csv(DEFAULT_CSV, encoding="utf-8-sig")
        elif DEFAULT_XLSX.exists():
            df = pd.read_excel(DEFAULT_XLSX)
        else:
            raise FileNotFoundError("Không tìm thấy khoi5_normalized.csv/xlsx trong thư mục data/. Bạn có thể upload ở sidebar.")

    df = _standardize_columns(df)

    # Chuẩn hoá kiểu dữ liệu, bỏ NaN
    for c in df.columns:
        df[c] = df[c].astype(str).fillna("").str.strip()

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Thiếu cột trong dữ liệu YCCĐ: {missing}. Cần có: {REQUIRED_COLS}. Cột hiện có: {list(df.columns)}")

    df = df[df["Yêu cầu cần đạt"].astype(str).str.strip() != ""].copy()
    return df
