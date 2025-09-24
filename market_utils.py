# 1) Weekly High/Low
def weekly_high_low(ticker: str, days: int = 7) -> Dict[str, float]:
    tk = _normalize_ticker(ticker)
    # pakai period + buffer supaya tidak empty karena weekend/libur
    buf_days = max(days + 3, 10)
    df = yf.download(tickers=tk, period=f"{buf_days}d", interval="1d", progress=False, threads=False)
    if df.empty:
        raise ValueError(f"Tidak ada data {days} hari untuk {ticker}")
    # kolom bisa multiindex saat multiple tickers; normalkan
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs("Close", axis=1, level=0, drop_level=False).join(
             df.xs("High", axis=1, level=0, drop_level=False)).join(
             df.xs("Low",  axis=1, level=0, drop_level=False))
        df.columns = [c[-1] if isinstance(c, tuple) else c for c in df.columns]
    # ambil hanya 'days' terakhir yang punya data
    df = df.tail(days)
    return {
        "highest": float(df["High"].max()),
        "lowest":  float(df["Low"].min()),
        "start":   df.index.min().date().isoformat(),
        "end":     df.index.max().date().isoformat(),
    }

# 2) Moving Average (daily/weekly)
def moving_average(ticker: str, window: int = 50, frame: str = "weekly", period: str = "2y") -> Tuple[float, float]:
    tk = _normalize_ticker(ticker)
    interval = "1wk" if frame.lower().startswith("week") else "1d"
    df = yf.download(tickers=tk, period=period, interval=interval, progress=False, threads=False)
    if df.empty:
        raise ValueError(f"Data kosong untuk {ticker}")
    if "Close" not in df.columns:
        # handle multiindex
        if isinstance(df.columns, pd.MultiIndex):
            df = df["Close"]
    df["MA"] = df["Close"].rolling(window=window, min_periods=window).mean()
    last = df.iloc[-1]
    if pd.isna(last["MA"]):
        need = window - df["Close"].count()
        raise ValueError(f"Data belum cukup untuk MA{window} {frame} (kurang ~{need} bar).")
    return float(last["Close"]), float(last["MA"])

# 3) Pivot Points
def pivot_points(ticker: str, source: str = "weekly") -> Dict[str, float]:
    tk = _normalize_ticker(ticker)
    if source == "weekly":
        df = yf.download(tickers=tk, period="1y", interval="1wk", progress=False, threads=False)
        if len(df) < 2:
            raise ValueError("Data mingguan belum cukup.")
        ref = df.iloc[-2]  # minggu sebelumnya
    else:
        df = yf.download(tickers=tk, period="3mo", interval="1d", progress=False, threads=False)
        if df.empty:
            raise ValueError("Data harian belum cukup.")
        ref = df.iloc[-1]  # hari terakhir (diasumsikan sudah close)
    H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
    P = (H + L + C) / 3.0
    return {"P": P, "R1": 2*P - L, "S1": 2*P - H, "R2": P + (H - L), "S2": P - (H - L)}
