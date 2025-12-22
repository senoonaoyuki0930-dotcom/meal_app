import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import traceback

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

from google.oauth2.service_account import Credentials
import gspread
import streamlit as st

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

# モード（将来OCRを足すための導線）
mode = st.radio("入力方法", ["手入力（今はこれのみ）", "写真→OCR（Coming Soon!!）"], horizontal=True)

if "draft" not in st.session_state:
    st.session_state.draft = None

# --- 手入力 ---
if mode.startswith("手入力"):
    st.subheader("1) 入力")

    # ★追加：食べ物名
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
            "timestamp": datetime.now().isoformat(),
            "food_name": food_name,          # ★追加
            "protein_g": float(p),
            "fat_g": float(f),
            "carbs_g": float(c),
            "calories": float(kcal),
            "note": note,
            "source": "manual"
        }
        st.rerun()

# --- 写真→OCR（今は未実装の置き場だけ） ---
else:
    st.subheader("写真→OCR（Coming Soon!!）")
    st.info("ここに写真アップ→OCR→候補表示→修正→保存 を後で追加します。")
    st.file_uploader("栄養成分表の写真（任意）", type=["png", "jpg", "jpeg"])

# --- 確認＆保存 ---
if st.session_state.draft is not None:
    st.divider()
    st.subheader("2) 確認（修正OK）")

    d = st.session_state.draft

    # ★追加：食べ物名（確認）
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



...
with colB:
    if st.button("登録（Sheetsへ保存）", type="primary"):
        try:
            ws = get_worksheet()

            row = [
                datetime.now().isoformat(),
                float(p2),
                float(f2),
                float(c2),
                float(kcal2),
                note2,
                d.get("source", "manual"),
            ]

            ws.append_row(row, value_input_option="USER_ENTERED")
            st.success("登録できました！")
            st.session_state.draft = None
            st.rerun()

        except Exception as e:
            st.error(f"保存に失敗しました: {type(e).__name__}: {e}")
            st.code(traceback.format_exc())
            st.stop()


