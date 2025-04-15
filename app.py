# ================================
# 📦 IMPORT LIBRARY
# ================================
import os
import time
import json
import threading
import sqlite3
import pandas as pd
import streamlit as st
from flask import Flask, request, jsonify
import google.generativeai as genai

# ================================
# ⚙️ KONFIGURASI GEMINI
# ================================
genai.configure(api_key="AIzaSyCsaRx6DBvrFQfFC80rnkmv9dwZporDbbY")

# ================================
# 🔧 FLASK SETUP
# ================================
flask_app = Flask(__name__)
DATA_FILE = "latest_data.json"
SERVO_FILE = "servo_status.json"
BUZZER_FILE = "buzzer_status.json"
POMPA_FILE = "pompa_status.json"
KIPAS_FILE = "kipas_status.json"


# ================================
# 🗃️ INISIALISASI DATABASE
# ================================
def init_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS kompos_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            gas REAL,
            distance REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================================
# 🤖 FUNGSI ANALISIS AI (GEMINI)
# ================================
def analisa_ai(temp, hum, gas):
    prompt = f"""
Kamu adalah AI yang mengatur alat pengomposan otomatis berdasarkan data sensor berikut:

📊 Data Sensor:
- Suhu: {temp:.2f}°C
- Kelembaban: {hum:.2f}%
- Kadar Gas: {gas} (rentang ADC 0–4095)

📌 Aturan:
1. Jika Suhu > 55°C:
   - Aktifkan Buzzer (peringatan)
   - Aktifkan Kipas (pendinginan)
   - Aktifkan Servo (distribusi panas)

2. Jika Kelembaban < 40%:
   - Aktifkan Pompa (penambahan kelembaban)
   - Aktifkan Servo (pencampuran cairan)

3. Jika Gas > 3000:
   - Aktifkan Buzzer (peringatan gas)
   - Aktifkan Kipas (sirkulasi udara)
   - Aktifkan Servo (percepatan dekomposisi)

⚙️ Output:
- Tanggapan AI dalam format JSON **tanpa teks tambahan**
- Format wajib:
{{
  "analisis": "penjelasan singkat kondisi saat ini",
  "rekomendasi": "langkah lanjutan yang disarankan",
  "aktifkan_servo": true/false,
  "aktifkan_buzzer": true/false,
  "aktifkan_pompa": true/false,
  "aktifkan_kipas": true/false
}}

Hanya berikan JSON. Jangan tambahkan penjelasan lain atau teks tambahan apa pun.
"""


    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip()

    # Bersihkan blok kode jika ada
    if text.startswith("```json"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        hasil = json.loads(text)
        # Tambahkan default jika ada field yang hilang
        return {
            "analisis": hasil.get("analisis", "Tidak ada analisis."),
            "rekomendasi": hasil.get("rekomendasi", "Tidak ada rekomendasi."),
            "aktifkan_servo": hasil.get("aktifkan_servo", False),
            "aktifkan_buzzer": hasil.get("aktifkan_buzzer", False),
            "aktifkan_pompa": hasil.get("aktifkan_pompa", False),
            "aktifkan_kipas": hasil.get("aktifkan_kipas", False)
        }


    except Exception:
        print("⚠️ Gagal parsing JSON dari Gemini:")
        print(response.text)
        return {
            "analisis": response.text.strip(),
            "rekomendasi": "Parsing otomatis gagal. Cek analisis.",
            "aktifkan_servo": False,
            "aktifkan_buzzer": False,
            "aktifkan_pompa": False,
            "aktifkan_kipas": False
        }


# ================================
# 📥 ENDPOINT POST DATA
# ================================
@flask_app.route("/post-data", methods=["POST"])
def post_data():
    data = request.json
    print(f"📥 Data dari ESP32: {data}")

    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

    # Simpan ke database
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO kompos_data (timestamp, temperature, humidity, gas, distance) VALUES (?, ?, ?, ?, ?)",
        (time.strftime("%Y-%m-%d %H:%M:%S"),
         data["temperature"],
         data["humidity"],
         data["gas"],
         data.get("distance", None))  # Gunakan None jika tidak ada
    )
    conn.commit()
    conn.close()

    # Simpan ke data_log.json
    log_file = "data_log.json"
    log_data = []

    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                log_data = json.load(f)
        except:
            log_data = []

    data_with_time = {
        "timestamp": time.time(),
        "temperature": data["temperature"],
        "humidity": data["humidity"],
        "gas": data["gas"],
        "distance": data.get("distance")
    }

    log_data.append(data_with_time)
    log_data = log_data[-100:]

    with open(log_file, "w") as f:
        json.dump(log_data, f)

    return jsonify({"status": "success", "data_received": data})


# ================================
# 🔄 ENDPOINT STATUS SERVO & BUZZER
# ================================
@flask_app.route("/servo-status", methods=["GET"])
def servo_status():
    return jsonify(json.load(open(SERVO_FILE)) if os.path.exists(SERVO_FILE) else {"status": "idle"})

@flask_app.route("/update-servo", methods=["POST"])
def update_servo():
    status = request.json
    with open(SERVO_FILE, "w") as f:
        json.dump(status, f)
    print("🔧 Servo diperbarui:", status)
    return jsonify({"status": "updated", "new_status": status})

@flask_app.route("/buzzer-status", methods=["GET"])
def buzzer_status():
    return jsonify(json.load(open(BUZZER_FILE)) if os.path.exists(BUZZER_FILE) else {"status": "idle"})

@flask_app.route("/update-buzzer", methods=["POST"])
def update_buzzer():
    status = request.json
    with open(BUZZER_FILE, "w") as f:
        json.dump(status, f)
    print("🔔 Buzzer diperbarui:", status)
    return jsonify({"status": "updated", "new_status": status})

@flask_app.route("/pompa-status", methods=["GET"])
def pompa_status():
    return jsonify(json.load(open(POMPA_FILE)) if os.path.exists(POMPA_FILE) else {"status": "idle"})

@flask_app.route("/update-pompa", methods=["POST"])
def update_pompa():
    status = request.json
    with open(POMPA_FILE, "w") as f:
        json.dump(status, f)
    print("💧 Pompa diperbarui:", status)
    return jsonify({"status": "updated", "new_status": status})

@flask_app.route("/kipas-status", methods=["GET"])
def kipas_status():
    return jsonify(json.load(open(KIPAS_FILE)) if os.path.exists(KIPAS_FILE) else {"status": "idle"})

@flask_app.route("/update-kipas", methods=["POST"])
def update_kipas():
    status = request.json
    with open(KIPAS_FILE, "w") as f:
        json.dump(status, f)
    print("🌀 Kipas diperbarui:", status)
    return jsonify({"status": "updated", "new_status": status})

# ================================
# 🚀 JALANKAN FLASK DI THREAD TERPISAH
# ================================
def run_flask():
    flask_app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask, daemon=True).start()

# ================================
# 🎛️ FUNGSI BANTUAN
# ================================
def get_latest_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"temperature": None, "humidity": None, "gas": None, "distance": None}


def set_servo_status(aktif=True):
    with open(SERVO_FILE, "w") as f:
        json.dump({"status": "aktif" if aktif else "idle"}, f)

# ================================
# 🌐 STREAMLIT DASHBOARD
# ================================
st.set_page_config(page_title="AIoT BioBin", layout="wide")
st.markdown("""<meta http-equiv="refresh" content="30">""", unsafe_allow_html=True)
st.title("AIoT BioBin")

# Load atau inisialisasi file ambang batas
setting_file = "ambang_batas.json"
if os.path.exists(setting_file):
    with open(setting_file, "r") as f:
        ambang = json.load(f)
else:
    ambang = {
        "suhu_min": 35,
        "suhu_max": 55,
        "kelembaban_min": 40,
        "kelembaban_max": 55,
        "gas_max": 3000
    }

# Toggle pengaturan
if st.button("⚙️ Pengaturan Ambang Batas"):
    st.session_state.show_settings = True

# Reset tampilan setiap reload (agar pengaturan tidak langsung muncul)
if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

# Panel Pengaturan
if st.session_state.show_settings:
    with st.expander("🔧 Panel Pengaturan", expanded=True):
        with st.form("form_ambang_main"):
            st.markdown("**Suhu (°C)**")
            suhu_min = st.number_input("Minimum Suhu", value=ambang["suhu_min"])
            suhu_max = st.number_input("Maksimum Suhu", value=ambang["suhu_max"])

            st.markdown("**Kelembaban (%)**")
            hum_min = st.number_input("Minimum Kelembaban", value=ambang["kelembaban_min"])
            hum_max = st.number_input("Maksimum Kelembaban", value=ambang["kelembaban_max"])

            st.markdown("**Gas (ADC)**")
            gas_max = st.number_input("Gas maksimum aman", value=ambang["gas_max"])

            submit = st.form_submit_button("💾 Simpan Ambang")

            if submit:
                ambang = {
                    "suhu_min": suhu_min,
                    "suhu_max": suhu_max,
                    "kelembaban_min": hum_min,
                    "kelembaban_max": hum_max,
                    "gas_max": gas_max
                }
                with open(setting_file, "w") as f:
                    json.dump(ambang, f)
                st.success("✅ Ambang batas disimpan!")

        # Tombol sembunyikan panel
        if st.button("❌ Tutup Pengaturan"):
            st.session_state.show_settings = False




st.markdown("**Monitoring kondisi ruang pengomposan berbasis AI.**")
st.divider()

latest = get_latest_data()
if all(latest.get(k) is not None for k in ["temperature", "humidity", "gas"]):
        # Hitung persentase jarak (0cm = 100%, 14cm = 0%)
    distance_cm = latest.get("distance", 0)
    distance_percent = max(0, min(100, round((1 - (distance_cm / 14)) * 100)))

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("🌡️ Suhu (°C)", f"{latest['temperature']:.2f}")
    col2.metric("💧 Kelembaban (%)", f"{latest['humidity']:.2f}")

    gas = latest["gas"]
    gas_status = (
        "🟢 Aman" if gas < 2200 else
        "🟡 Waspada" if gas < 3000 else
        "🔴 Tinggi" if gas < 4000 else
        "🚨 Berbahaya!"
    )
    col3.metric("🧪 Kadar Gas", f"{gas} ADC", gas_status)

    # ⬇️ Tambahan kolom Jarak
    col4.metric("🗑️ Tingkat Kepenuhan", f"{distance_percent}%", f"Dari {distance_cm:.2f} cm")




    st.divider()

    with st.spinner("🤖 AI sedang menganalisis..."):
        hasil = analisa_ai(latest["temperature"], latest["humidity"], gas)

        if gas < 2200:
            hasil["aktifkan_servo"] = False
            hasil["aktifkan_buzzer"] = False
            hasil["rekomendasi"] += " | Override: Gas < 2200, aman."

        st.subheader("📊 Hasil Analisis AI")
        st.code(json.dumps(hasil, indent=2), language="json")
        st.success(f"🧠 Analisis: {hasil['analisis']}")
        st.info(f"💡 Rekomendasi: {hasil['rekomendasi']}")

        if hasil.get("aktifkan_servo"):
            set_servo_status(True)
            st.warning("⚙️ Servo AKTIF!")
        else:
            set_servo_status(False)
            st.success("✅ Servo tidak diaktifkan.")

        if hasil.get("aktifkan_buzzer"):
            with open(BUZZER_FILE, "w") as f:
                json.dump({"status": "aktif"}, f)
            st.error("🚨 Buzzer AKTIF! Kondisi bahaya.")
        else:
            with open(BUZZER_FILE, "w") as f:
                json.dump({"status": "idle"}, f)
            st.info("🔕 Buzzer tidak aktif.")
        if hasil.get("aktifkan_pompa"):
            with open("pompa_status.json", "w") as f:
                json.dump({"status": "aktif"}, f)
            st.warning("💧 Pompa AKTIF!")
        else:
            with open("pompa_status.json", "w") as f:
                json.dump({"status": "idle"}, f)
            st.info("Pompa tidak aktif.")
            
        if hasil.get("aktifkan_kipas"):
            with open("kipas_status.json", "w") as f:
                json.dump({"status": "aktif"}, f)
        else:
            with open("kipas_status.json", "w") as f:
                json.dump({"status": "idle"}, f)
            st.info("Kipas tidak aktif.")


else:
    st.warning("❗ Belum ada data lengkap dari ESP32.")

st.divider()

# ===========================
# 🔍 STATUS AKTUATOR
# ===========================
col4, col5 = st.columns(2)

# Load status dari file JSON
servo_now = json.load(open(SERVO_FILE)).get("status", "unknown") if os.path.exists(SERVO_FILE) else "unknown"
buzzer_now = json.load(open(BUZZER_FILE)).get("status", "unknown") if os.path.exists(BUZZER_FILE) else "unknown"
pompa_now = json.load(open(POMPA_FILE)).get("status", "unknown") if os.path.exists(POMPA_FILE) else "unknown"
kipas_now = json.load(open(KIPAS_FILE)).get("status", "unknown") if os.path.exists(KIPAS_FILE) else "unknown"

with col4:
    if servo_now == "aktif":
        st.markdown("### 🛠️ Servo: ✅ `AKTIF`")
        st.success("Servo sedang berjalan.")
    else:
        st.markdown("### 🛠️ Servo: ⛔ `IDLE`")
        st.info("Servo non-aktif.")

    if pompa_now == "aktif":
        st.markdown("### 💧 Pompa: ✅ `AKTIF`")
        st.warning("Pompa sedang menyiram cairan.")
    else:
        st.markdown("### 💧 Pompa: ⛔ `IDLE`")
        st.info("Pompa tidak aktif.")

with col5:
    if buzzer_now == "aktif":
        st.markdown("### 🔔 Buzzer: 🚨 `AKTIF`")
        st.error("Bahaya! Buzzer menyala.")
    else:
        st.markdown("### 🔔 Buzzer: ✅ `IDLE`")
        st.success("Buzzer mati. Aman.")

    if kipas_now == "aktif":
        st.markdown("### 🌀 Kipas: ✅ `AKTIF`")
        st.warning("Kipas menyala untuk sirkulasi udara.")
    else:
        st.markdown("### 🌀 Kipas: ⛔ `IDLE`")
        st.info("Kipas dalam keadaan mati.")

# ===========================
# 🎛️ KONTROL MANUAL
# ===========================
st.subheader("🎛️ Kontrol Manual")

mode = st.radio("Mode Operasi", ["Otomatis", "Manual"])

if mode == "Manual":
    col_manual1, col_manual2 = st.columns(2)

    with col_manual1:
        if st.button("🔄 Aktifkan Servo Manual"):
            set_servo_status(True)
            st.success("Servo diaktifkan secara manual.")

        if st.button("⛔ Matikan Servo Manual"):
            set_servo_status(False)
            st.info("Servo dimatikan secara manual.")

        if st.button("💧 Aktifkan Pompa Manual"):
            with open(POMPA_FILE, "w") as f:
                json.dump({"status": "aktif"}, f)
            st.success("Pompa dinyalakan secara manual.")

        if st.button("🚫 Matikan Pompa Manual"):
            with open(POMPA_FILE, "w") as f:
                json.dump({"status": "idle"}, f)
            st.info("Pompa dimatikan secara manual.")

    with col_manual2:
        if st.button("🔔 Aktifkan Buzzer Manual"):
            with open(BUZZER_FILE, "w") as f:
                json.dump({"status": "aktif"}, f)
            st.warning("Buzzer dinyalakan secara manual.")

        if st.button("🔕 Matikan Buzzer Manual"):
            with open(BUZZER_FILE, "w") as f:
                json.dump({"status": "idle"}, f)
            st.success("Buzzer dimatikan secara manual.")

        if st.button("🌀 Aktifkan Kipas Manual"):
            with open(KIPAS_FILE, "w") as f:
                json.dump({"status": "aktif"}, f)
            st.success("Kipas dinyalakan secara manual.")

        if st.button("💨 Matikan Kipas Manual"):
            with open(KIPAS_FILE, "w") as f:
                json.dump({"status": "idle"}, f)
            st.info("Kipas dimatikan secara manual.")


# ================================
# 📈 GRAFIK DATA HISTORIS
# ================================
st.subheader("📈 Riwayat Data Sensor Lengkap")

# Ambil semua data
conn = sqlite3.connect("data.db")
df_all = pd.read_sql_query("SELECT * FROM kompos_data", conn)
conn.close()

if not df_all.empty:
    df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])

    # Filter tanggal
    start_date = st.date_input("Dari tanggal", df_all["timestamp"].min().date())
    end_date = st.date_input("Sampai tanggal", df_all["timestamp"].max().date())

    df_filtered = df_all[
        (df_all["timestamp"].dt.date >= start_date) &
        (df_all["timestamp"].dt.date <= end_date)
    ]

    if not df_filtered.empty:
        df_filtered.set_index("timestamp", inplace=True)

        st.markdown("### 🌡️💧 Suhu & Kelembaban")
        st.line_chart(df_filtered[["temperature", "humidity"]])

        st.markdown("### 🧪 Kadar Gas")
        st.line_chart(df_filtered[["gas"]])

        # Ekspor CSV
        csv = df_filtered.reset_index().to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Data CSV", csv, "kompos_data.csv", "text/csv")
    else:
        st.warning("Tidak ada data di rentang tanggal tersebut.")
else:
    st.info("⏳ Belum ada data historis.")

st.subheader("📊 Analisis Progres Pengomposan")

if not df_all.empty:
    rata2_suhu = df_all["temperature"].mean()
    rata2_kelembaban = df_all["humidity"].mean()
    rata2_gas = df_all["gas"].mean()

    st.write(f"🌡️ Suhu Rata-rata: **{rata2_suhu:.2f}°C**")
    st.write(f"💧 Kelembaban Rata-rata: **{rata2_kelembaban:.2f}%**")
    st.write(f"🧪 Gas Rata-rata: **{rata2_gas:.0f}**")

    # Estimasi progres (contoh logika)
    if rata2_gas < 2500 and rata2_suhu > 35:
        st.success("👍 Kompos berjalan baik. Estimasi matang < 1 minggu lagi.")
    elif rata2_gas > 3000:
        st.warning("⚠️ Pembusukan terlalu cepat. Periksa aerasi atau bahan kompos.")
    else:
        st.info("ℹ️ Kompos dalam progres. Pantau terus suhu dan gas.")

else:
    st.info("Data belum cukup untuk dianalisis.")
    

st.subheader("🟢 Status Pengomposan")

status_file = "status_pengomposan.json"

# Load status awal
if os.path.exists(status_file):
    with open(status_file, "r") as f:
        status_pengomposan = json.load(f)
else:
    status_pengomposan = {"status": "idle"}  # idle, aktif, jeda, selesai

# === Fungsi reset database
def reset_database():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS kompos_data")
    conn.commit()
    conn.close()
    init_db()  # Buat tabel baru kosong

# === TOMBOL-TOMBOL KONTROL ===
if status_pengomposan["status"] == "idle":
    if st.button("🚀 Mulai Pengomposan"):
        reset_database()
        status_pengomposan["status"] = "aktif"
        with open(status_file, "w") as f:
            json.dump(status_pengomposan, f)
        st.experimental_rerun()  # Refresh halaman otomatis

        st.success("Pengomposan dimulai. Database di-reset.")
elif status_pengomposan["status"] == "aktif":
    st.success("Status: Pengomposan AKTIF 🟢")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏸️ Jeda Pengomposan"):
            status_pengomposan["status"] = "jeda"
            with open(status_file, "w") as f:
                json.dump(status_pengomposan, f)
            st.info("Pengomposan dijeda.")
    with col2:
        if st.button("🛑 Akhiri Pengomposan"):
            status_pengomposan["status"] = "selesai"
            with open(status_file, "w") as f:
                json.dump(status_pengomposan, f)
            st.warning("Pengomposan diakhiri.")

elif status_pengomposan["status"] == "jeda":
    st.warning("Status: Pengomposan DIJEDA ⏸️")
    if st.button("▶️ Lanjutkan Pengomposan"):
        status_pengomposan["status"] = "aktif"
        with open(status_file, "w") as f:
            json.dump(status_pengomposan, f)
        st.success("Pengomposan dilanjutkan.")

elif status_pengomposan["status"] == "selesai":
    st.error("Status: Pengomposan SELESAI 🛑")
    if st.button("🔄 Mulai Lagi"):
        reset_database()
        status_pengomposan["status"] = "aktif"
        with open(status_file, "w") as f:
            json.dump(status_pengomposan, f)
        st.success("Pengomposan dimulai kembali.")


st.divider()
st.caption("© 2025 CompoSmart | ESP32 x Streamlit x Gemini AI")
