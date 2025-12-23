\
from __future__ import annotations
import pandas as pd
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "khoi5_normalized.csv"
DEFAULT_XLSX = Path(__file__).resolve().parents[1] / "data" / "khoi5_normalized.xlsx"

REQUIRED_COLS = ["Môn", "Chủ đề/Chủ điểm", "Bài", "Tên bài học", "Yêu cầu cần đạt"]

def load_yccd(uploaded_file=None) -> pd.DataFrame:
    """
    Load kho YCCĐ lớp 5 (đã chuẩn hoá). Ưu tiên file upload (csv/xlsx), fallback về data/.
    """
    if uploaded_file is not None:
        name = (uploaded_file.name or "").lower()
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError("Chỉ hỗ trợ .csv hoặc .xlsx")
    else:
        if DEFAULT_CSV.exists():
            df = pd.read_csv(DEFAULT_CSV)
        elif DEFAULT_XLSX.exists():
            df = pd.read_excel(DEFAULT_XLSX)
        else:
            raise FileNotFoundError("Không tìm thấy khoi5_normalized.csv/xlsx trong thư mục data/")

    # Chuẩn hoá kiểu dữ liệu, bỏ NaN
    for c in df.columns:
        df[c] = df[c].astype(str).fillna("").str.strip()

    # Kiểm tra cột tối thiểu
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Thiếu cột trong dữ liệu YCCĐ: {missing}. Cần có: {REQUIRED_COLS}")

    # Bỏ dòng rỗng YCCĐ
    df = df[df["Yêu cầu cần đạt"].astype(str).str.strip() != ""].copy()
    return df
