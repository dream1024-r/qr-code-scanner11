import streamlit as st
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import requests
import pandas as pd

st.set_page_config(page_title="QR Code 防詐騙掃描器", layout="wide")
st.title("QR Code 防詐騙掃描器（OpenCV 版）")

# ==== 後端防詐騙 API ====
def check_safe_browsing(url: str) -> str:
    api_key = "YOUR_GOOGLE_API_KEY"  # 改成你的 API Key
    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"
    payload = {
        "client": {"clientId": "qr-scanner", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE","SOCIAL_ENGINEERING","UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=5)
        data = resp.json()
        return "已知詐騙" if "matches" in data else "安全"
    except:
        return "API 錯誤"

# ==== Session 歷史紀錄 ====
if "history" not in st.session_state:
    st.session_state.history = []

blacklist = ["bit.ly","free","login","bank","password","update","verify"]

# ==== OpenCV QR Code 偵測函式 ====
def decode_qr_opencv(pil_image):
    qr_decoder = cv2.QRCodeDetector()
    img = np.array(pil_image.convert("RGB"))
    data, points, _ = qr_decoder.detectAndDecode(img)
    return [data] if data else []

# ==== 上傳圖片掃描 ====
st.subheader("上傳 QR Code 圖片掃描")
uploaded_image = st.file_uploader("上傳圖片檔 (PNG / JPG / JPEG)", type=["png","jpg","jpeg"])
if uploaded_image:
    image = Image.open(uploaded_image)
    decoded_list = decode_qr_opencv(image)
    if decoded_list:
        for qr_text in decoded_list:
            status = "安全"
            if any(keyword in qr_text.lower() for keyword in blacklist):
                status = "疑似詐騙"
            else:
                status = check_safe_browsing(qr_text)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.history.append({"qr": qr_text, "status": status, "time": timestamp})
        st.success("圖片掃描完成")
    else:
        st.warning("未偵測到 QR Code")

# ==== 顯示歷史紀錄 & CSV下載 ====
if st.session_state.history:
    st.subheader("掃描歷史列表")
    df_hist = pd.DataFrame(st.session_state.history)
    st.dataframe(df_hist)
    csv_bytes = df_hist.to_csv(index=False).encode("utf-8-sig")
    st.download_button("下載歷史紀錄 CSV", csv_bytes, "qr_history.csv")

# ==== 即時攝像頭掃描 ====
st.subheader("即時攝像頭掃描 QR Code")
start_scan = st.button("開始攝像頭掃描")
stop_scan = st.button("停止攝像頭掃描")

# 攝像頭掃描主要流程
if "cap" not in st.session_state:
    st.session_state.cap = None

if start_scan:
    st.session_state.cap = cv2.VideoCapture(0)
    st.session_state.stop = False

if st.session_state.cap:
    while True:
        ret, frame = st.session_state.cap.read()
        if not ret or getattr(st.session_state, "stop", False):
            st.session_state.cap.release()
            break
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        decoded_list = decode_qr_opencv(pil_img)
        for qr_text in decoded_list:
            if not any(h["qr"] == qr_text for h in st.session_state.history):
                status = "安全"
                if any(keyword in qr_text.lower() for keyword in blacklist):
                    status = "疑似詐騙"
                else:
                    status = check_safe_browsing(qr_text)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.history.append({"qr": qr_text, "status": status, "time": timestamp})
                if status in ["已知詐騙","疑似詐騙"]:
                    st.warning(f"⚠️ 掃描到 {status} QR Code: {qr_text}")
        st.image(frame, channels="BGR", use_column_width=True)
        if stop_scan:
            st.session_state.stop = True
            st.session_state.cap.release()
            break
