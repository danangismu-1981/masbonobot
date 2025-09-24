import datetime as dt
import pandas as pd
import yfinance as yf
from typing import Dict, Tuple, Optional

# --- Helpers ---
IDX_SUFFIX = ".JK"

def _normalize_ticker(t: str) -> str:
    """
    Normalisasi ticker. Tambahkan .JK jika belum ada.
    """
    t = t.strip().upper()
    return t if t.endswith(".JK") else f"{t}{IDX_SUFFIX}"


# --- 1) Weekly High/Low ---
def weekly_high_low(ticker: str, days: int = 7) -> Dict[str, float]:
    """
    Ambil harga tertinggi & terendah dalam X hari terakhir.
    Pakai yf.download dengan buffer supaya tidak kosong karena weekend/libur.
    """
    tk = _normalize_ticker(ticker)
    buf_days = max(days + 3, 10)  # buffer 3 hari, min 10 hari
    df = yf.download(
        tickers=tk,
        period=f"{buf_days}d",
        interval="1d",
        progress=False,
        threads=False,
    )

    if df.empty:
        raise ValueError(f"Tidak ada data {days} hari untuk {ticker}")

    # Normalisasi kolom kalau MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(0, axis=1)

    # Ambil hanya 'days' terakhir yang ada datanya
    df = df.tail(days)

    return {
        "highest": float(df["High"].max()),
        "lowest": float(df["Low"].min()),
        "start": df.index.min().date().isoformat(),
        "end": df.index.max().date().isoformat(),
    }


# --- 2) Moving Average ---
def moving_average(
    ticker: str,
    window: int = 50,
    frame: str = "weekly",   # "daily" | "weekly"
    period: str = "2y"
) -> Tuple[float, float]:
    """
    Hitung MA berdasarkan Close.
    frame="weekly" -> interval=1wk, frame="daily" -> interval=1d
    """
    tk = _normalize_ticker(ticker)
    interval = "1wk" if frame.lower().startswith("week") else "1d"
    df = yf.download(
        tickers=tk,
        period=period,
        interval=interval,
        progress=False,
        threads=False,
    )

    if df.empty:
        raise ValueError(f"Data kosong untuk {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(0, axis=1)

    df["MA"] = df["Close"].rolling(window=window, min_periods=window).mean()
    last = df.iloc[-1]

    if pd.isna(last["MA"]):
        need = window - df["Close"].count()
        raise ValueError(
            f"Data belum cukup untuk MA{window} {frame} (kurang ~{need} bar)."
        )

    return float(last["Close"]), float(last["MA"])


# --- 3) Pivot Points ---
def pivot_points(ticker: str, source: str = "weekly") -> Dict[str, float]:
    """
    Hitung Pivot Points klasik.
    - weekly: pakai candle minggu sebelumnya
    - daily : pakai candle harian terakhir
    """
    tk = _normalize_ticker(ticker)

    if source.lower().startswith("week"):
        df = yf.download(
            tickers=tk,
            period="1y",
            interval="1wk",
            progress=False,
            threads=False,
        )
        if len(df) < 2:
            raise ValueError("Data mingguan belum cukup.")
        ref = df.iloc[-2]  # minggu sebelumnya
    else:
        df = yf.download(
            tickers=tk,
            period="3mo",
            interval="1d",
            progress=False,
            threads=False,
        )
        if df.empty:
            raise ValueError("Data harian belum cukup.")
        ref = df.iloc[-1]  # hari terakhir (asumsikan sudah close)

    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(0, axis=1)
        ref = df.iloc[-1]

    H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
    P = (H + L + C) / 3.0
