# market_utils.py
import datetime as dt
from typing import Dict, Optional, Tuple
import pandas as pd
import yfinance as yf

# --- Helpers ---
IDX_SUFFIX = ".JK"

def _normalize_ticker(t: str) -> str:
    t = t.strip().upper()
    # Jika user sudah tulis .JK biarkan, kalau tidak tambahkan
    return t if t.endswith(".JK") else f"{t}{IDX_SUFFIX}"

def _history(ticker: str, period: str="6mo", interval: str="1d") -> pd.DataFrame:
    tk = yf.Ticker(_normalize_ticker(ticker))
    df = tk.history(period=period, interval=interval, auto_adjust=False)
    if df.empty:
        raise ValueError(f"Data kosong untuk {ticker}")
    # Pastikan kolom standar ada
    for col in ["Open","High","Low","Close","Volume"]:
        if col not in df.columns:
            raise ValueError(f"Kolom {col} tidak tersedia untuk {ticker}")
    return df

# --- 1) Weekly High/Low (default 1 minggu terakhir kalender) ---
def weekly_high_low(ticker: str, days: int = 7) -> Dict[str, float]:
    end_dt = dt.datetime.utcnow()
    start_dt = end_dt - dt.timedelta(days=days)
    df = yf.Ticker(_normalize_ticker(ticker)).history(start=start_dt, end=end_dt, interval="1d")
    if df.empty:
        raise ValueError(f"Tidak ada data 7 hari untuk {ticker}")
    return {
        "highest": float(df["High"].max()),
        "lowest": float(df["Low"].min()),
        "start": df.index.min().date().isoformat(),
        "end": df.index.max().date().isoformat(),
    }

# --- 2) Moving Average (daily / weekly) ---
def moving_average(
    ticker: str,
    window: int = 50,
    frame: str = "weekly",   # "daily" | "weekly"
    period: str = "2y"
) -> Tuple[float, float]:
    """
    Return (last_close, last_ma).
    frame="weekly" -> interval=1wk; "daily" -> 1d
    """
    interval = "1wk" if frame.lower().startswith("week") else "1d"
    df = _history(ticker, period=period, interval=interval)
    df["MA"] = df["Close"].rolling(window=window, min_periods=window).mean()
    last_row = df.iloc[-1]
    last_ma = float(last_row["MA"]) if pd.notna(last_row["MA"]) else None
    if last_ma is None:
        need = window - df["Close"].count()
        raise ValueError(f"Data belum cukup untuk MA{window} {frame} (butuh {window} bar). Kurang ~{need} bar.")
    return float(last_row["Close"]), last_ma

# --- 3) Pivot Points (Classic) dari bar minggu lalu / hari terakhir ---
def pivot_points(
    ticker: str,
    source: str = "weekly"  # "weekly" | "daily"
) -> Dict[str, float]:
    """
    Classic floor pivots.
    Jika weekly -> ambil candle minggu sebelumnya (interval=1wk, bar -2)
    Jika daily  -> ambil candle harian terakhir lengkap (bar -1)
    """
    if source == "weekly":
        df = _history(ticker, period="1y", interval="1wk")
        # butuh minimal 2 bar (karena pakai minggu sebelumnya)
        if len(df) < 2:
            raise ValueError("Data mingguan belum cukup.")
        ref = df.iloc[-2]  # minggu sebelumnya
    else:
        df = _history(ticker, period="3mo", interval="1d")
        if len(df) < 1:
            raise ValueError("Data harian belum cukup.")
        ref = df.iloc[-1]  # hari terakhir (asumsikan sudah close)

    H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
    P = (H + L + C) / 3.0
    R1 = 2*P - L
    S1 = 2*P - H
    R2 = P + (H - L)
    S2 = P - (H - L)
    return {"P": P, "R1": R1, "S1": S1, "R2": R2, "S2": S2}
