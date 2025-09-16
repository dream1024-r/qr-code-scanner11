import streamlit as st
import streamlit.components.v1 as components
from pyzbar.pyzbar import decode
from PIL import Image
from datetime import datetime
import requests
import pandas as pd

st.set_page_config(page_title="QR Code 防詐騙掃描器", layout="wide")
st.title("QR Code 防詐騙掃描器（攝像頭 + 圖片掃描）")

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

# ==== 即時攝像頭掃描 HTML ====
st.subheader("即時攝像頭掃描 QR Code")
html_code = """
<div id="qr-container"></div>
<video id="qr-video" width="300" height="200" autoplay muted></video>
<br>
<button id="start-scan">開始掃描</button>
<button id="stop-scan">停止掃描</button>
<button id="export-csv">下載 CSV</button>

<script src="https://unpkg.com/@zxing/library@latest"></script>
<script>
document.addEventListener("DOMContentLoaded", () => {
    const video = document.getElementById("qr-video");
    const container = document.getElementById("qr-container");
    let codeReader = new ZXing.BrowserQRCodeReader();
    let scanning = false;
    let stream = null;
    let history = [];
    const blacklist = ["bit.ly","free","login","bank","password","update","verify"];

    function getColor(status){
        if(status==="安全") return "green";
        else if(status==="疑似詐騙") return "orange";
        else return "red";
    }

    async function checkFraud(text){
        try { new URL(text); } catch { return "疑似詐騙"; }
        if(blacklist.some(k=>text.toLowerCase().includes(k))) return "疑似詐騙";
        const response = await fetch("/?url_to_check="+encodeURIComponent(text));
        const result = await response.text();
        return result || "安全";
    }

    function showAlert(status, qr){
        if(status==="已知詐騙"){
            alert("⚠️ 掃描到已知詐騙 QR Code: " + qr);
        } else if(status==="疑似詐騙"){
            alert("⚠️ 掃描到疑似詐騙 QR Code: " + qr);
        }
    }

    document.getElementById("start-scan").addEventListener("click", async ()=>{
        if(scanning) return;
        scanning = true;
        try {
            stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});
            video.srcObject = stream;
            codeReader.decodeFromVideoElement(video, async (result, err)=>{
                if(result){
                    if(!history.some(item=>item.qr===result.text)){
                        const status = await checkFraud(result.text);
                        showAlert(status, result.text);
                        const time = new Date();
                        const timestamp = time.getFullYear()+"-"+String(time.getMonth()+1).padStart(2,'0')+"-"+String(time.getDate()).padStart(2,'0')+" "+
                                          String(time.getHours()).padStart(2,'0')+":"+String(time.getMinutes()).padStart(2,'0')+":"+String(time.getSeconds()).padStart(2,'0');
                        history.push({qr: result.text, status: status, time: timestamp});
                        container.replaceChildren(...history.map((item,index)=>{
                            const p=document.createElement("p");
                            p.textContent=(index+1)+". QR: "+item.qr+" | 判定: "+item.status+" | 時間: "+item.time;
                            p.style.color = getColor(item.status);
                            return p;
                        }));
                    }
                }
            });
        } catch(err){ scanning=false; alert("無法存取相機"); }
    });

    document.getElementById("stop-scan").addEventListener("click", ()=>{
        if(!scanning) return;
        if(stream) stream.getTracks().forEach(track=>track.stop());
        video.srcObject=null;
        scanning=false;
    });

    document.getElementById("export-csv").addEventListener("click", ()=>{
        if(history.length===0){ alert("沒有掃描紀錄可下載！"); return; }
        let csvContent = "data:text/csv;charset=utf-8,序號,掃描結果,判定,掃描時間\\n";
        history.forEach((item,index)=>{ csvContent += (index+1)+","+item.qr+","+item.status+","+item.time+"\\n"; });
        const link=document.createElement("a");
        link.setAttribute("href", encodeURI(csvContent));
        link.setAttribute("download","qr_scan_history.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
});
</script>
"""
components.html(html_code, height=400)

# ==== 上傳圖片掃描 ====
st.subheader("上傳 QR Code 圖片掃描")
uploaded_image = st.file_uploader("上傳圖片檔 (PNG / JPG / JPEG)", type=["png","jpg","jpeg"])
if uploaded_image:
    image = Image.open(uploaded_image)
    decoded_objs = decode(image)
    if decoded_objs:
        for obj in decoded_objs:
            qr_text = obj.data.decode("utf-8")
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

# ==== 後端接收前端 URL 查詢 ====
query_params = st.query_params
if "url_to_check" in query_params:
    url = query_params["url_to_check"][0]
    result = check_safe_browsing(url)
    st.write(result)
