#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from datetime import datetime, timedelta
import glob
import re
from typing import Optional, Tuple

import numpy as np
import numpy as np
import pandas as pd
import yfinance as yf

def find_md_files(folder: str, pattern: Optional[str], ticker_filter: Optional[str]) -> list[str]:
    def apply_filter(paths: list[str]) -> list[str]:
        if not ticker_filter:
            return paths
        t = ticker_filter.lower()
        return [p for p in paths if t in os.path.basename(p).lower()]

    if pattern:
        return apply_filter(sorted(glob.glob(os.path.join(folder, pattern))))

    candidates = sorted(glob.glob(os.path.join(folder, "*.MD")))

    def accept(name: str) -> bool:
        base = os.path.basename(name).lower()
        return base.startswith("ticker_") or base.endswith("_quick.md")

    files = [p for p in candidates if accept(p)]
    return apply_filter(files) if files else apply_filter(candidates)


def try_download(t: str) -> pd.DataFrame:
    df = yf.download(t, period="max", auto_adjust=False, progress=False)
    if isinstance(df, pd.Series):
        df = df.to_frame()
    if df is None:
        df = pd.DataFrame()
    return df

def resolve_ticker_force_jk(raw: str) -> Tuple[str, pd.DataFrame]:
    r = raw.strip().upper()
    if "." in r:
        # If user already provided an exchange, use as-is
        df = try_download(r)
        return r, df
    # Force .JK (IDX)
    t = f"{r}.JK"
    df = try_download(t)
    return t, df

def extract_close_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for col in ["Adj Close", "Close", "adjclose", "close"]:
        if col in df.columns:
            s = df[col]
            if isinstance(s, pd.DataFrame):
                s = s.squeeze()
            s = s.dropna()
            # Ensure tz-naive index
            if hasattr(s.index, "tz") and s.index.tz is not None:
                s.index = s.index.tz_localize(None)
            return s
    if df.shape[1] == 1:
        s = df.iloc[:, 0].dropna()
        if hasattr(s.index, "tz") and s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        return s
    return pd.Series(dtype=float)

def latest_price(close: pd.Series):
    if close is None or close.empty:
        return None
    val = close.iloc[-1]
    # pastikan scalar
    if hasattr(val, "item"):
        val = val.item()
    return float(val)


def first_close_on_or_after(close: pd.Series, start_date: datetime):
    if close is None or close.empty:
        return (None, None)
    sub = close.loc[close.index >= pd.Timestamp(start_date)]
    if sub.empty:
        return (None, None)
    v = sub.iloc[0]
    if hasattr(v, "item"):
        v = v.item()
    return (pd.Timestamp(sub.index[0]).to_pydatetime(), float(v))


def cagr_since(close: pd.Series, start_date: datetime, today: Optional[datetime] = None):
    if close is None or close.empty:
        return None
    if today is None:
        today = datetime.now().replace(tzinfo=None)
    s_date, s_price = first_close_on_or_after(close, start_date)
    if s_date is None or s_price is None or s_price <= 0:
        return None
    e_price = latest_price(close)
    if e_price is None or e_price <= 0:
        return None
    years = max((today - s_date).days / 365.25, 1e-9)
    try:
        return (e_price / s_price) ** (1.0 / years) - 1.0
    except Exception:
        return None
def get_first_price_of_year_yf(ticker: str, year: int):
    """Ambil harga pada hari bursa pertama di awal tahun (Jan)
    dengan cara yang sama seperti gethistoricalprice.py:
    - Ambil data 1 Jan s/d 1 Feb
    - Pilih harga penutupan pertama yang tersedia.
    """
    start = f"{year}-01-01"
    end = f"{year}-02-01"
    try:
        data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    except Exception:
        return None, None

    if data is None or data.empty:
        return None, None

    col = "Adj Close" if "Adj Close" in data.columns else "Close"
    if col not in data.columns:
        return None, None

    series = data[col]
    # bisa jadi DataFrame 1 kolom → squeeze dulu
    if isinstance(series, pd.DataFrame):
        series = series.squeeze()
    series = series.dropna()
    if series.empty:
        return None, None

    first_date = series.index[0].date()
    v = series.iloc[0]
    if hasattr(v, "item"):
        v = v.item()
    first_price = float(v)
    return first_date, first_price



def get_latest_price_yf(ticker: str):
    """Ambil harga terakhir (latest close) dengan jendela 5 hari terakhir,
    sama seperti di gethistoricalprice.py.
    """
    try:
        data = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=False)
    except Exception:
        return None, None

    if data is None or data.empty:
        return None, None

    col = "Adj Close" if "Adj Close" in data.columns else "Close"
    if col not in data.columns:
        return None, None

    series = data[col]
    if isinstance(series, pd.DataFrame):
        series = series.squeeze()
    series = series.dropna()
    if series.empty:
        return None, None

    last_date = series.index[-1].date()
    v = series.iloc[-1]
    if hasattr(v, "item"):
        v = v.item()
    last_price = float(v)
    return last_date, last_price


 
def cagr_since_year_yf(ticker: str, year: int, today: Optional[datetime] = None):
    """Hitung CAGR sejak awal tahun tertentu menggunakan metode harga
    yang sama dengan gethistoricalprice.py.
    """
    if today is None:
        today = datetime.now().replace(tzinfo=None)

    start_date, start_price = get_first_price_of_year_yf(ticker, year)
    if start_date is None or start_price is None or start_price <= 0:
        return None

    _, latest_price_val = get_latest_price_yf(ticker)
    if latest_price_val is None or latest_price_val <= 0:
        return None

    years = max((today.date() - start_date).days / 365.25, 1e-9)
    try:
        return (latest_price_val / start_price) ** (1.0 / years) - 1.0
    except Exception:
        return None


def moving_average_latest(close: pd.Series, window: int, prefer_weekly: bool = True):
    if close is None or close.empty:
        return ("Daily", None)

    if prefer_weekly:
        wk = close.resample("W-FRI").last().dropna()
        if len(wk) >= window:
            ma_w = wk.rolling(window).mean().iloc[-1]
            if hasattr(ma_w, "item"):
                ma_w = ma_w.item()
            return ("Weekly", float(ma_w))

    dl = close.dropna()
    if len(dl) >= window:
        ma_d = dl.rolling(window).mean().iloc[-1]
        if hasattr(ma_d, "item"):
            ma_d = ma_d.item()
        return ("Daily", float(ma_d))

    return ("Daily", None)


def dividends_info(ticker: str):
    try:
        dv = yf.Ticker(ticker).dividends
    except Exception:
        return (None, None, None)

    if dv is None or dv.empty:
        return (0.0, None, None)

    dv = dv.sort_index()
    if hasattr(dv.index, "tz") and dv.index.tz is not None:
        dv.index = dv.index.tz_localize(None)

    last_date = pd.Timestamp(dv.index[-1]).to_pydatetime()

    v_last = dv.iloc[-1]
    if hasattr(v_last, "item"):
        v_last = v_last.item()
    last_amt = float(v_last)

    cutoff = last_date - timedelta(days=365)
    v_ttm = dv.loc[dv.index >= cutoff].sum()
    if hasattr(v_ttm, "item"):
        v_ttm = v_ttm.item()
    ttm = float(v_ttm)

    return (ttm, last_date, last_amt)


def pct_fmt(x, digits=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x*100:.{digits}f}%"

def num_fmt(x, digits=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    # If x is an int like 136, render 136.00 with digits=2
    return f"{x:.{digits}f}"
def format_large_number(num):
    if num is None or (isinstance(num, float) and np.isnan(num)):
        return "n/a"
    if abs(num) >= 1_000_000_000_000:
        return f"{num/1_000_000_000_000:.2f} T"
    elif abs(num) >= 1_000_000_000:
        return f"{num/1_000_000_000:.2f} B"
    elif abs(num) >= 1_000_000:
        return f"{num/1_000_000:.2f} M"
    else:
        return f"{num:,.0f}"

def infer_ticker_from_filename(path: str) -> str:
    base = os.path.basename(path)
    name = os.path.splitext(base)[0]
    m = re.match(r'(?i)^ticker_([A-Z0-9\.\-]+)', name)
    if m:
        return m.group(1).upper()
    m = re.match(r'(?i)^([A-Z0-9\.\-]+)_quick$', name)
    if m:
        return m.group(1).upper()
    return name.split("_")[0].upper()

def main():
    import datetime as _dt
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="./quick")
    ap.add_argument("--pattern", default=None)
    ap.add_argument("--ticker", default=None, help="Filter dan preferensi ticker (contoh ADMF).")
    args = ap.parse_args()

    files = find_md_files(args.folder, args.pattern, args.ticker)
    if not files:
        print(f"Tidak menemukan file di {args.folder}" + (f" untuk '{args.ticker}'" if args.ticker else "") + ".")
        return

    for fp in files:
        print("=" * 45)
        print("-" * 60)
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            print(f.read().strip())
        print("-" * 60)

        raw_ticker = (args.ticker or infer_ticker_from_filename(fp)).upper()
        chosen_ticker, df = resolve_ticker_force_jk(raw_ticker)
        close = extract_close_series(df)

        # Harga latest & CAGR pakai metode yang sama dengan gethistoricalprice.py
        today = _dt.datetime.now().replace(tzinfo=None)
        latest_date, px = get_latest_price_yf(chosen_ticker)
        # fallback: kalau gagal ambil dari YF style baru, pakai data historis yang sudah di-download
        if (px is None) and (close is not None and not close.empty):
            px = latest_price(close)

        cagr_2021 = cagr_since_year_yf(chosen_ticker, 2021, today)
        cagr_2022 = cagr_since_year_yf(chosen_ticker, 2022, today)
        cagr_2023 = cagr_since_year_yf(chosen_ticker, 2023, today)
        cagr_2024 = cagr_since_year_yf(chosen_ticker, 2024, today)
        cagr_2025 = cagr_since_year_yf(chosen_ticker, 2025, today)
        cagr_2026 = cagr_since_year_yf(chosen_ticker, 2026, today)

        ma50_basis, ma50_val = moving_average_latest(close, 50, True)

        ma200_basis, ma200_val = moving_average_latest(close, 200, True)

        dv_ttm, dv_last_date, dv_last_amt = dividends_info(chosen_ticker)
        # Dividend yield for the most recent dividend (last payout only), as a fraction
        dv_yield_last = (dv_last_amt / px) if (dv_last_amt is not None and px and px > 0) else None

        print("Market Data:")
        print(f"  Ticker (YF): {chosen_ticker}")
        print(f"  Price (latest): {num_fmt(px)}")
        print(f"  CAGR 2021: {pct_fmt(cagr_2021)}")
        print(f"  CAGR 2022: {pct_fmt(cagr_2022)}")
        print(f"  CAGR 2023: {pct_fmt(cagr_2023)}")
        print(f"  CAGR 2024: {pct_fmt(cagr_2024)}")
        print(f"  CAGR 2025: {pct_fmt(cagr_2025)}")
        print(f"  CAGR 2026: {pct_fmt(cagr_2026)}")
        print(f"  MA50 {ma50_basis}: {num_fmt(ma50_val)}")
        print(f"  MA200 {ma200_basis}: {num_fmt(ma200_val)}")
        if dv_last_date is not None:
            print(f"  Dividend: TTM {num_fmt(dv_ttm)} ; Last: {dv_last_date.date().strftime("%d-%m-%Y")} (amt {num_fmt(dv_last_amt)}, yield {pct_fmt(dv_yield_last, 2)})")
        else:
            print(f"  Dividend: TTM {num_fmt(dv_ttm)} ; Last: n/a")
        
        # === Yahoo Finance Fundamental Data ===
        try:
            info = yf.Ticker(chosen_ticker).info
        except Exception:
            info = {}

        pe = info.get("trailingPE")
        pbv = info.get("priceToBook")
        roe = info.get("returnOnEquity")
        ebitda = info.get("ebitda")

        today_str = datetime.now().strftime("%d-%m-%Y")
        print(f"\nValuation & Profitability (Yahoo Finance) {today_str}")
        print(f"  PER (TTM) : {num_fmt(pe)}x" if pe else "  PER (TTM) : n/a")
        print(f"  PBV       : {num_fmt(pbv)}x" if pbv else "  PBV       : n/a")
        print(f"  ROE       : {pct_fmt(roe, 2)}" if roe else "  ROE       : n/a")
        print(f"  EBITDA    : {format_large_number(ebitda)}")
        
        
        print("=" * 45)
        print(f"Jika ingin data lebih detail ketik: {raw_ticker.upper()} Detail")
        print()

        print()

if __name__ == "__main__":
    main()
