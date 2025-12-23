# de-maker-grade5 V1.1 (AI Studio Gemini) – Minimal repo for GitHub + Streamlit Cloud

Repo tối giản để bạn **push lên GitHub** và deploy lên **Streamlit Community Cloud**.
- Dùng **Gemini API key (AI Studio)** qua REST `generateContent`.
- Có chế độ **offline** nếu chưa có key (để test pipeline).

## 1) Chạy local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 2) Deploy Streamlit Cloud
1. Push repo lên GitHub
2. Streamlit Cloud → New app → chọn repo/branch → `app.py`
3. App settings → Secrets → thêm:

```toml
GEMINI_API_KEY = "YOUR_AI_STUDIO_KEY"
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
```

> Bạn có thể copy từ `.streamlit/secrets.toml.example`

## 3) Dữ liệu
- Repo đã kèm `data/khoi5_normalized.csv` (kho YCCĐ lớp 5).
- Bạn cũng có thể upload lại file CSV/XLSX ở sidebar để test.

## 4) Tính năng (tối giản)
- Tab 1: tạo “ma trận tối giản” (mỗi dòng = 1 YCCĐ + dạng/mức/điểm/số câu)
- Tab 2: tạo đề / tạo lại (giữ form) / chỉnh sửa + validator cấu trúc
- Tab 3: xuất Word (DOCX) + tải session.json

## Ghi chú
- Mức độ dùng nhãn TT27: M1 Nhận biết, M2 Kết nối, M3 Vận dụng.
- Xuất Word: format cơ bản theo NĐ30 (lề, font TNR). Template đặc tả theo mẫu trường sẽ bổ sung ở phiên bản tiếp theo.


## PPCT / Số tiết (K5.pdf)
- Repo kèm `data/ppct/ppct_k5_extracted.csv` đã trích từ K5.pdf (nếu trích được).
- Bạn có thể upload lại **K5.pdf** ở sidebar để trích/ghi đè.
- Nút **Auto-fill Số tiết** trong Tab 1 sẽ điền số tiết theo môn + số bài.
- Nút **Tính tỉ lệ & số điểm** hỗ trợ chế độ 2 block (2,5/7,5) giống mẫu ma trận.
