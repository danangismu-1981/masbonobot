import os
import re
import sys
import subprocess

# === Tambahan: impor util teknikal (yfinance) ===
# Pastikan market_utils.py ada di folder yang sama.
try:
    from market_utils import weekly_high_low, moving_average, pivot_points
    _TECH_ENABLED = True
except Exception as _e:
    _TECH_ENABLED = False
    _TECH_ERR = str(_e)

COMPARE_DIR_DEFAULT = "compare"

def _which_python():
    # use current interpreter if possible
    return sys.executable or "python"

def _find_compare_cli():
    """
    Try to find compare_md_cli.py relative to this file or CWD.
    Returns absolute path or None.
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "compare_md_cli.py"),
        os.path.join(os.getcwd(), "compare_md_cli.py"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _run_compare(tickers, compare_dir=COMPARE_DIR_DEFAULT, timeout=90):
    """
    Call compare_md_cli.py to produce comparison text for 2 tickers.
    Returns stdout on success, or error string on failure.
    """
    cli = _find_compare_cli()
    if not cli:
        return ("[ERROR] compare_md tidak ditemukan.\n"
                "Pastikan file tersebut ada di folder yang sama dengan Root "
                "atau di working directory aplikasi.")

    # Ensure only first two tickers and sanitize
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    if len(tickers) != 2:
        return "Format salah. Gunakan: COMPARE <TICKER1>,<TICKER2>. Contoh: COMPARE AALI,ADMR"

    safe = []
    for t in tickers:
        m = re.match(r"^[A-Z0-9\.\-]{2,10}$", t)
        if not m:
            return f"Ticker tidak valid: {t}"
        safe.append(t)

    cmd = [_which_python(), cli, "--input", ",".join(safe), "--compare_dir", compare_dir, "--format", "whatsapp"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return f"[ERROR] Gagal menjalankan compare_md: {e}"

    if proc.returncode != 0:
        # bubble up stderr for debugging
        err = (proc.stderr or "").strip()
        return f"[ERROR] Compare gagal (code {proc.returncode}). {err}"

    out = (proc.stdout or "").strip()
    return out if out else "[INFO] Tidak ada output dari compare_md"

def get_file_content(folder_path, filename):
    """
    Membaca file <filename>.md dari folder_path (UTF-8).
    """
    try:
        file_path = os.path.join(folder_path, f"{filename}.MD")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return None
    except Exception as e:
        return f"Error membaca file: {str(e)}"

def _help_text():
    return (
        "Hi! Nama saya Mas Bono, saya bisa bantu cari info saham.\n"
        "Ketik:\n"
        "- [LIST] untuk lihat daftar saham\n"
        "- [KODE EMITEN], untuk mendapatkan strategic summary. Contoh: ANTM\n"
        "- COMPARE KODE1,KODE2 untuk membandingkan dua emiten (contoh: COMPARE AALI,ADMR)\n"
        "\n🔧 *Perintah Teknis:*\n"
        "- HIGHLOW <TICKER> [DAYS]\n"
        "  Contoh: HIGHLOW PTBA 7\n"
        "- MA <TICKER> <WINDOW> [DAILY|WEEKLY]\n"
        "  Contoh: MA BBCA 50 WEEKLY\n"
        "- PIVOT <TICKER> [DAILY|WEEKLY]\n"
        "  Contoh: PIVOT BBRI WEEKLY\n"
        "Catatan: Ticker IDX otomatis .JK (BBRI -> BBRI.JK)."
    )

def handle_message(message_text, base_folder="Data"):
    msg_raw = (message_text or "").strip()
    msg = msg_raw.upper()

    # === Perintah Teknis (butuh market_utils / yfinance) ===
    # Format:
    # - HIGHLOW <TICKER> [DAYS]
    # - MA <TICKER> <WINDOW> [DAILY|WEEKLY]
    # - PIVOT <TICKER> [DAILY|WEEKLY]
    if msg.startswith("HIGHLOW") or msg.startswith("MA ") or msg.startswith("PIVOT"):
        if not _TECH_ENABLED:
            return (
                "⚠️ Fitur teknikal belum aktif (market_utils tidak tersedia).\n"
                f"Detail: {_TECH_ERR if '_TECH_ERR' in globals() else 'unknown error'}"
            )

        parts = msg.strip().split()
        cmd = parts[0]

        try:
            if cmd == "HIGHLOW":
                if len(parts) < 2:
                    return "Format: HIGHLOW <TICKER> [DAYS]. Contoh: HIGHLOW PTBA 7"
                ticker = parts[1]
                days = int(parts[2]) if len(parts) >= 3 else 7
                res = weekly_high_low(ticker, days=days)
                return (
                    f"📈 *Weekly High/Low* {ticker.upper()}\n"
                    f"Periode: {res['start']} → {res['end']}\n"
                    f"- High: {res['highest']:.2f}\n"
                    f"- Low : {res['lowest']:.2f}"
                )

            elif cmd == "MA":
                if len(parts) < 3:
                    return "Format: MA <TICKER> <WINDOW> [DAILY|WEEKLY]. Contoh: MA BBCA 50 WEEKLY"
                ticker = parts[1]
                window = int(parts[2])
                frame = parts[3] if len(parts) >= 4 else "WEEKLY"
                last_close, last_ma = moving_average(ticker, window=window, frame=frame)
                signal = "BULLISH (Close > MA)" if last_close > last_ma else "BEARISH (Close < MA)"
                return (
                    f"📊 *MA{window} {frame.title()}* {ticker.upper()}\n"
                    f"- Close terakhir: {last_close:.2f}\n"
                    f"- MA{window}: {last_ma:.2f}\n"
                    f"- Sinyal: {signal}"
                )

            elif cmd == "PIVOT":
                if len(parts) < 2:
                    return "Format: PIVOT <TICKER> [DAILY|WEEKLY]. Contoh: PIVOT BBRI WEEKLY"
                ticker = parts[1]
                src = parts[2] if len(parts) >= 3 else "WEEKLY"
                piv = pivot_points(ticker, source=src.lower())
                return (
                    f"🧭 *Pivot ({src.title()})* {ticker.upper()}\n"
                    f"P : {piv['P']:.2f}\n"
                    f"R1: {piv['R1']:.2f} | R2: {piv['R2']:.2f}\n"
                    f"S1: {piv['S1']:.2f} | S2: {piv['S2']:.2f}"
                )

        except Exception as e:
            # error yang ramah user
            return f"⚠️ Error teknikal: {str(e)}"

    # === COMPARE: e.g., "COMPARE AALI,ADMR" atau "COMPARE ADMF AALI"
    if msg.startswith("COMPARE"):
        rest = msg_raw.strip()[len("COMPARE"):].strip()
        tickers = re.split(r"[,\s/;]+", rest)  # izinkan pemisah beragam
        tickers = [t for t in tickers if t]
        if len(tickers) > 2:
            tickers = tickers[:2]
        return _run_compare(tickers, compare_dir=COMPARE_DIR_DEFAULT)

    # === HI & HELP ===
    if msg in ("HI", "HELP"):
        return _help_text()

    # === LIST ===
    elif msg == "LIST":
        try:
            files = os.listdir(base_folder)
            md_files = sorted([f.replace('.MD', '') for f in files if f.endswith('.MD')])
            return "Daftar saham tersedia:\n" + ("\n".join(md_files) if md_files else "(kosong)")
        except Exception as e:
            return f"Error membaca folder: {str(e)}"

    # === Kategori: FINANCIAL / BALANCE / OPERATIONAL / VALUATION ===
    elif any(msg.startswith(prefix) for prefix in ["FINANCIAL", "BALANCE", "OPERATIONAL", "VALUATION"]):
        parts = msg.split()
        if len(parts) == 2:
            category, kode = parts
            folder_path = os.path.join(base_folder, category)
            result = get_file_content(folder_path, kode)  # baca <KODE>.MD
            return result if result else f"Data {category} untuk {kode} belum tersedia."
        else:
            return "Format salah. Contoh: FINANCIAL ANTM"

    # === Default: anggap kode emiten (root Data/) ===
    else:
        result = get_file_content(base_folder, msg)  # baca <KODE>.MD
        return result if result else (
            _help_text() + "\n\n"
            "Kode saham yang kamu cari belum tersedia."
        )
