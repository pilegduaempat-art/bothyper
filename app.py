import streamlit as st
import pandas as pd
import numpy as np
import asyncio
import time
import datetime
import telebot
from hyperliquid.info import Info
from ta.momentum import RSIIndicator

# ==========================================================
# 📦 CONFIG DAN INISIALISASI
# ==========================================================
st.set_page_config(page_title="⚡ Hyperliquid Futures Screener", layout="wide")

st.title("⚡ Hyperliquid Futures Screener")
st.caption("Deteksi pair ekstrem (StochRSI 0/100) & kirim notifikasi Telegram otomatis")

# ------------------- Input Telegram Config -------------------
with st.expander("⚙️ Pengaturan Telegram Bot"):
    TELEGRAM_TOKEN = st.text_input("Masukkan Telegram Bot Token:", type="password")
    TELEGRAM_CHAT_ID = st.text_input("Masukkan Telegram Chat ID:")
    test_button = st.button("Tes Kirim Pesan Telegram")

# ------------------- Input Interval dan Auto Refresh -------------------
col1, col2 = st.columns(2)
with col1:
    interval = st.selectbox("Pilih Interval Data:", ["5m", "15m", "1h", "4h", "1d"], index=2)
with col2:
    auto_refresh = st.toggle("🔁 Auto Refresh", value=True)
refresh_interval = st.slider("Interval Refresh (detik):", 30, 600, 180)

# ==========================================================
# 🔗 KONEKSI API Hyperliquid
# ==========================================================
info = Info("https://api.hyperliquid.xyz")

async def get_all_symbols():
    meta = info.meta()
    return [x["name"] for x in meta["universe"]]

async def get_ohlcv(symbol, interval="1h", limit=100):
    candles = info.candles(symbol, interval, limit)
    if not candles:
        return None
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["close"] = df["close"].astype(float)
    return df

# ==========================================================
# 📊 PERHITUNGAN STOCHRSI
# ==========================================================
def calc_stochrsi(df, period=14, smooth_k=3, smooth_d=3):
    if len(df) < period * 2:
        return None, None

    rsi = RSIIndicator(df["close"], window=period).rsi()
    stochrsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() - rsi.rolling(period).min()) * 100
    k = stochrsi.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k.iloc[-1], d.iloc[-1]

def send_telegram_message(token, chat_id, msg):
    if not token or not chat_id:
        return
    try:
        bot = telebot.TeleBot(token)
        bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        st.error(f"Gagal kirim Telegram: {e}")

# ==========================================================
# 🧠 SCREENER
# ==========================================================
async def run_screener():
    st.info("Mengambil data dari Hyperliquid API...")
    symbols = await get_all_symbols()
    results = []

    for sym in symbols:
        df = await get_ohlcv(sym, interval=interval)
        if df is None:
            continue

        stoch_k, stoch_d = calc_stochrsi(df)
        if stoch_k is None:
            continue

        results.append({
            "Pair": sym,
            "StochRSI": round(stoch_k, 2),
            "MA_StochRSI": round(stoch_d, 2)
        })

    df = pd.DataFrame(results)
    oversold = df[(df["StochRSI"] <= 0.10) & (df["MA_StochRSI"] <= 0.00)]
    overbought = df[(df["StochRSI"] >= 99.90) & (df["MA_StochRSI"] >= 100.00)]

    if not oversold.empty or not overbought.empty:
        msg = "🔥 *Hyperliquid Futures Alert!*\n\n"
        if not oversold.empty:
            msg += "🟢 *OVERSOLD:*\n" + "\n".join(oversold["Pair"]) + "\n"
        if not overbought.empty:
            msg += "🔴 *OVERBOUGHT:*\n" + "\n".join(overbought["Pair"]) + "\n"
        send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    return df, oversold, overbought

# ==========================================================
# 🖥️ STREAMLIT UI
# ==========================================================
if test_button:
    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, "✅ Tes pesan dari *Hyperliquid Screener* berhasil!")

if st.button("🔎 Jalankan Screener Sekarang"):
    with st.spinner("Menganalisis semua pair..."):
        df, oversold, overbought = asyncio.run(run_screener())
        st.success(f"✅ Data diperbarui: {datetime.datetime.now().strftime('%H:%M:%S')}")
        st.dataframe(df.sort_values("StochRSI", ascending=True), use_container_width=True)
        st.subheader("🟢 Oversold Pairs")
        st.dataframe(oversold)
        st.subheader("🔴 Overbought Pairs")
        st.dataframe(overbought)

# Auto refresh loop
if auto_refresh:
    st.toast(f"⏳ Auto-refresh aktif setiap {refresh_interval} detik.")
    time.sleep(refresh_interval)
    st.rerun()
