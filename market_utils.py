import time
import datetime as dt
from typing import Dict, Tuple, Optional
import pandas as pd
import yfinance as yf

IDX_SUFFIX = ".JK"

def _normalize_ticker(t: str) -> str:
    """Tambahkan .JK untuk ticker IDX kalau belum ada"""
    t = t.strip().upper()
    return t if t.endswith(".JK") else f"{t}{IDX_SUFFIX}"

# --- REPLACE these helpers in market_utils.py ---

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Pastikan kolom OHLC standar."""
    # kalau MultiIndex (jarang untuk history single-ticker), ratakan
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.droplevel(0, axis=1)
        except Exception:
            df.columns = [str(c[-1]) if isinstance(c, tuple) else str(c) for c in df.columns]

    # rename variasi nama ke Title Case standar
    mapping = {
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
        "adjclose": "Adj Close", "adj close": "Adj Close", "adj_close": "Adj Close",
        "volume": "Volume",
    }
    newcols = {}
    for c in df.columns:
        key = str(c).lower().replace(" ", "").replace("_", "")
        if key in mapping:
            newcols[c] = mapping[key]
    if newcols:
        df = df.rename(columns=newcols)

    return df

def _safe_download(tk: str, *, period: str, interval: str) -> pd.DataFrame:
    """
    Wrapper stabil pakai Ticker().history (bukan yf.download),
    auto_adjust=False, retry 3x + backoff.
    """
    last_exc: Optional[Exception] = None
    t = yf.Ticker(tk)
    for i in range(3):
        try:
            df = t.history(period=period, interval=interval, auto_adjust=False)
            if isinstance(df, pd.DataFrame) and not df.empty:
                df = _normalize_columns(df)
                # validasi minimal
                if "Close" in df.columns:
                    return df
                else:
                    last_exc = RuntimeError(f"Kolom tidak lengkap: {list(df.columns)}")
            else:
                last_exc = RuntimeError("Empty dataframe from Yahoo")
        except Exception as e:
            last_exc = e
        time.sleep(1.5 * (i + 1))  # backoff
    raise RuntimeError(f"Gagal download {tk}: {last_exc}")


# --- 1) Weekly High/Low ---
def weekly_high_low(ticker: str, days: int = 7) -> Dict[str, float]:
    tk = _normalize_ticker(ticker)
    buf_days = max(days + 3, 10)  # buffer untuk weekend/libur
    df = _safe_download(tk, period=f"{buf_days}d", interval="1d")
    if not {"High", "Low"}.issubset(df.columns):
        raise KeyError("Kolom High/Low tidak tersedia dari Yahoo.")
    df = df.tail(days)
    return {
        "highest": float(df["High"].max()),
        "lowest":  float(df["Low"].min()),
        "start":   df.index.min().date().isoformat(),
        "end":     df.index.max().date().isoformat(),
    }

# --- 2) Moving Average ---
def moving_average(
    ticker: str,
    window: int = 50,
    frame: str = "weekly",   # "daily" | "weekly"
    period: str = "2y",
) -> Tuple[float, float]:
    tk = _normalize_ticker(ticker)
    interval = "1wk" if frame.lower().startswith("week") else "1d"
    df = _safe_download(tk, period=period, interval=interval)
    if "Close" not in df.columns:
        raise KeyError("Kolom Close tidak tersedia dari Yahoo.")
    df["MA"] = df["Close"].rolling(window=window, min_periods=window).mean()
    last = df.iloc[-1]
    if pd.isna(last["MA"]):
        need = window - df["Close"].count()
        raise ValueError(f"Data belum cukup untuk MA{window} {frame} (kurang ~{need} bar).")
    return float(last["Close"]), float(last["MA"])

# --- 3) Pivot Points (Classic) ---
def pivot_points(ticker: str, source: str = "weekly") -> Dict[str, float]:
    tk = _normalize_ticker(ticker)
    if source.lower().startswith("week"):
        df = _safe_download(tk, period="1y", interval="1wk")
        if len(df) < 2:
            raise ValueError("Data mingguan belum cukup.")
        ref = df.iloc[-2]  # minggu sebelumnya
    else:
        df = _safe_download(tk, period="3mo", interval="1d")
        if df.empty:
            raise ValueError("Data harian belum cukup.")
        ref = df.iloc[-1]

    # ✅ perbaikan: cek langsung ke df.columns, jangan gabung df.index
    if not {"High", "Low", "Close"}.issubset(df.columns):
        raise KeyError(f"Kolom OHLC tidak lengkap: {list(df.columns)}")

    H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
    P = (H + L + C) / 3.0
    return {
        "P": P,
        "R1": 2*P - L,
        "S1": 2*P - H,
        "R2": P + (H - L),
        "S2": P - (H - L),
    }

