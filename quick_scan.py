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
    return float(close.iloc[-1])

def first_close_on_or_after(close: pd.Series, start_date: datetime):
    if close is None or close.empty:
        return (None, None)
    sub = close.loc[close.index >= pd.Timestamp(start_date)]
    if sub.empty:
        return (None, None)
    return (pd.Timestamp(sub.index[0]).to_pydatetime(), float(sub.iloc[0]))

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

def moving_average_latest(close: pd.Series, window: int, prefer_weekly: bool = True):
    if close is None or close.empty:
        return ("Daily", None)
    if prefer_weekly:
        wk = close.resample("W-FRI").last().dropna()
        if len(wk) >= window:
            return ("Weekly", float(wk.rolling(window).mean().iloc[-1]))
    dl = close.dropna()
    if len(dl) >= window:
        return ("Daily", float(dl.rolling(window).mean().iloc[-1]))
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
    last_amt = float(dv.iloc[-1])
    cutoff = pd.Timestamp(datetime.now().date() - timedelta(days=365))
    ttm = float(dv.loc[dv.index >= cutoff].sum())
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
        px = latest_price(close)

        today = _dt.datetime.now().replace(tzinfo=None)
        cagr_2021 = cagr_since(close, _dt.datetime(2021,1,1), today)
        cagr_2022 = cagr_since(close, _dt.datetime(2022,1,1), today)
        cagr_2023 = cagr_since(close, _dt.datetime(2023,1,1), today)
        cagr_2024 = cagr_since(close, _dt.datetime(2024,1,1), today)
        cagr_2025 = cagr_since(close, _dt.datetime(2025,1,1), today)

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
        print(f"  MA50 {ma50_basis}: {num_fmt(ma50_val)}")
        print(f"  MA200 {ma200_basis}: {num_fmt(ma200_val)}")
        if dv_last_date is not None:
            print(f"  Dividend: TTM {num_fmt(dv_ttm)} ; Last: {dv_last_date.date()} (amt {num_fmt(dv_last_amt)}, yield {pct_fmt(dv_yield_last, 2)})")
        else:
            print(f"  Dividend: TTM {num_fmt(dv_ttm)} ; Last: n/a")
        print("=" * 45)
        print(f"Jika ingin data lebih detail ketik: {raw_ticker.upper()} Detail")
        print()

        print()

if __name__ == "__main__":
    main()
