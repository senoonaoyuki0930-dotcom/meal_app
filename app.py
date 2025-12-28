import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime,timezone, timedelta
import traceback

JST = timezone(timedelta(hours=9))

#OCR用
from google.cloud import vision
from PIL import Image
import io
import re

def ocr_with_vision(image_bytes: bytes) -> str:
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info)
    client = vision.ImageAnnotatorClient(credentials=creds)

    image = vision.Image(content=image_bytes)
    res = client.text_detection(image=image)
    if res.error.message:
        raise RuntimeError(res.error.message)

    return res.text_annotations[0].description if res.text_annotations else ""

def parse_nutrition(text: str) -> dict:
    t = text.replace("：", ":").replace("．", ".").replace("，", ",")
    t = t.replace("Ｋｃａｌ", "kcal").replace("Kcal", "kcal")

    def pick(patterns):
        for pat in patterns:
            m = re.search(pat, t, flags=re.IGNORECASE)
            if m:
                return float(m.group(1))
        return None

    return {
        "kcal": pick([
            r"エネルギー\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)\s*kcal",
            r"熱量\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)\s*kcal",
        ]),
        "protein_g": pick([
            r"たんぱく質\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)\s*g",
            r"タンパク質\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)\s*g",
        ]),
        "fat_g": pick([
            r"脂質\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)\s*g",
        ]),
        "carbs_g": pick([
            r"炭水化物\s*[: ]\s*([0-9]+(?:\.[0-9]+)?)\s*g",
        ]),
    }


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_worksheet():
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(st.secrets["SPREADSHEET_ID"])
    ws = sh.worksheet(st.secrets["WORKSHEET_NAME"])
    return ws

def calc_kcal(p: float, f: float, c: float) -> float:
    return p * 4 + c * 4 + f * 9

# ========= UI =========
st.set_page_config(page_title="Meal Log", page_icon="🍽️", layout="centered")
st.title("🍽️ 食事記録アプリ")
st.caption("P/F/Cを入力 → 確認 → スプレッドシートに保存")

mode = st.radio("入力方法", ["手入力（今はこれのみ）", "写真→OCR（Coming Soon!!）"], horizontal=True)

if "draft" not in st.session_state:
    st.session_state.draft = None

# --- 手入力 ---
if mode.startswith("手入力"):
    st.subheader("1) 入力")

    food_name = st.text_input("食べ物名", value="")

    col1, col2, col3 = st.columns(3)
    with col1:
        p = st.number_input("Protein (g)", min_value=0.0, step=1.0, value=0.0)
    with col2:
        f = st.number_input("Fat (g)", min_value=0.0, step=1.0, value=0.0)
    with col3:
        c = st.number_input("Carbs (g)", min_value=0.0, step=1.0, value=0.0)

    note = st.text_input("メモ（任意）", value="")

    kcal = calc_kcal(p, f, c)
    st.metric("計算カロリー (kcal)", f"{kcal:.0f}")

    if st.button("次へ（確認）", type="primary"):
        st.session_state.draft = {
            "timestamp": datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
            "food_name": food_name,
            "protein_g": float(p),
            "fat_g": float(f),
            "carbs_g": float(c),
            "calories": float(kcal),
            "note": note,
            "source": "manual",
        }
        st.rerun()

else:
    st.subheader("写真→OCR（β）")
    up = st.file_uploader("栄養成分表の写真", type=["png", "jpg", "jpeg"], key="uploader_ocr")

    if up is None:
        st.info("画像をアップロードしてください。")
    else:
        img_bytes = up.getvalue()
        st.image(img_bytes, caption="アップロード画像", use_container_width=True)
        st.success("画像を受け取りました。下のボタンでOCRします。")

        # ★ 押したかどうかを分かりやすくするデバッグ表示
        st.caption("※ ボタンを押すと数秒〜十数秒待つことがあります")

        if st.button("OCRして確認へ", type="primary", key="run_ocr"):
            st.write("✅ OCRボタン押下")  # ← これが出るか確認

            with st.spinner("OCR解析中です…"):
                text = ocr_with_vision(img_bytes)
                parsed = parse_nutrition(text)

                p = float(parsed.get("protein_g") or 0)
                f = float(parsed.get("fat_g") or 0)
                c = float(parsed.get("carbs_g") or 0)
                kcal = float(parsed.get("kcal") or calc_kcal(p, f, c))

                st.session_state.draft = {
                    "timestamp": datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
                    "food_name": "",
                    "protein_g": p,
                    "fat_g": f,
                    "carbs_g": c,
                    "calories": kcal,
                    "note": "OCR",
                    "source": "ocr",
                    "ocr_text": text,  # デバッグ用
                }

            st.rerun()

        # ★ OCR全文（デバッグ）: すでに保存したテキストだけ表示（再OCRしない）
        if st.session_state.draft and st.session_state.draft.get("ocr_text"):
            with st.expander("OCR全文（デバッグ）"):
                st.text(st.session_state.draft["ocr_text"])

  



# --- 確認＆保存 ---
if st.session_state.draft is not None:
    st.divider()
    st.subheader("2) 確認（修正OK）")

    d = st.session_state.draft

    food_name2 = st.text_input("食べ物名 [確認]", value=d.get("food_name", ""))

    col1, col2, col3 = st.columns(3)
    with col1:
        p2 = st.number_input("Protein (g) [確認]", min_value=0.0, step=1.0, value=float(d["protein_g"]))
    with col2:
        f2 = st.number_input("Fat (g) [確認]", min_value=0.0, step=1.0, value=float(d["fat_g"]))
    with col3:
        c2 = st.number_input("Carbs (g) [確認]", min_value=0.0, step=1.0, value=float(d["carbs_g"]))

    note2 = st.text_input("メモ [確認]", value=d.get("note", ""))

    kcal2 = calc_kcal(p2, f2, c2)
    st.metric("最終カロリー (kcal)", f"{kcal2:.0f}")

    colA, colB = st.columns(2)

    with colA:
        if st.button("キャンセル"):
            st.session_state.draft = None
            st.rerun()

    with colB:
        if st.button("登録（Sheetsへ保存）", type="primary"):
            try:
                ws = get_worksheet()

                row = [
                    datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"),
                    food_name2,               # ←ここに食べ物名を入れる（指定の順）
                    float(p2),
                    float(f2),
                    float(c2),
                    float(kcal2),
                    note2,
                    d.get("source", "manual"),
                ]

                ws.append_row(row, value_input_option="RAW")
                st.success("登録できました！")
                st.session_state.draft = None
                st.rerun()

            except Exception as e:
                st.error(f"保存に失敗しました: {type(e).__name__}: {e}")
                st.code(traceback.format_exc())
                st.stop()
