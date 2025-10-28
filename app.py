import streamlit as st
import pandas as pd
import numpy as np
import datetime
import time
import telebot
import ccxt
from ta.momentum import RSIIndicator

# ==========================================================
# ⚙️ KONFIGURASI DASAR
# ==========================================================
st.set_page_config(page_title="⚡ Binance Futures Screener", layout="wide")

st.title("⚡ Binance Futures Volatility Screener")
st.caption("Deteksi pair ekstrem (StochRSI 0/100) & notifikasi Telegram otomatis")

# ------------------- Telegram Config -------------------
with st.expander("⚙️ Pengaturan Telegram Bot"):
    TELEGRAM_TOKEN = st.text_input("Masukkan Telegram Bot Token:", type="password")
    TELEGRAM_CHAT_ID = st.text_input("Masukkan Telegram Chat ID:")
    test_button = st.button("Tes Kirim Pesan Telegram")

# ------------------- Interval & Auto Refresh -------------------
col1, col2 = st.columns(2)
with col1:
    interval = st.selectbox("Pilih Interval Data:", ["5m", "15m", "1h", "4h", "1d"], index=2)
with col2:
    auto_refresh = st.toggle("🔁 Auto Refresh", value=True)

refresh_interval = st.slider("⏱ Interval Auto Refresh (detik):", 60, 600, 180)

# ==========================================================
# 🔗 KONEKSI API BINANCE FUTURES
# ==========================================================
exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "future"}
})

def get_all_symbols():
    markets = exchange.load_markets()
    return [m for m in markets if "/USDT" in m and "BUSD" not in m]

def get_ohlcv(symbol, timeframe="1h", limit=100):
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["close"] = df["close"].astype(float)
        return df
    except Exception:
        return None

# ==========================================================
# 📈 PERHITUNGAN STOCHRSI
# ==========================================================
def calc_stochrsi(df, period=14, smooth_k=3, smooth_d=3):
    if df is None or len(df) < period * 2:
        return None, None
    rsi = RSIIndicator(df["close"], window=period).rsi()
    stochrsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() - rsi.rolling(period).min()) * 100
    k = stochrsi.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k.iloc[-1], d.iloc[-1]

def send_telegram_message(token, chat_id, msg):
    if not token or not chat_id:
        st.warning("⚠️ Telegram Token atau Chat ID belum diisi.")
        return
    try:
        bot = telebot.TeleBot(token)
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        st.success("✅ Pesan Telegram berhasil dikirim!")
    except Exception as e:
        st.error(f"Gagal kirim Telegram: {e}")

# ==========================================================
# 🔍 FUNGSI SCREENER
# ==========================================================
def run_screener():
    st.info(f"Mengambil data dari Binance Futures ({interval}) ...")
    symbols = get_all_symbols()
    results = []

    for sym in symbols:
        df = get_ohlcv(sym, timeframe=interval)
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
        msg = "🔥 *Binance Futures Screener Alert!*\n\n"
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
    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, "✅ Tes pesan dari *Binance Screener* berhasil!")

if st.button("🔎 Jalankan Screener Sekarang"):
    with st.spinner("Menganalisis semua pair..."):
        df, oversold, overbought = run_screener()
        st.success(f"✅ Data diperbarui: {datetime.datetime.now().strftime('%H:%M:%S')}")

        st.subheader("📊 Semua Data StochRSI")
        st.dataframe(df.sort_values("StochRSI"), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🟢 Oversold Pairs")
            st.dataframe(oversold)
        with col2:
            st.subheader("🔴 Overbought Pairs")
            st.dataframe(overbought)

# ==========================================================
# ♻️ AUTO REFRESH
# ==========================================================
if auto_refresh:
    st.toast(f"⏳ Auto-refresh aktif setiap {refresh_interval} detik.")
    time.sleep(refresh_interval)
    st.rerun()
