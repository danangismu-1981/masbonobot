
import os
import re
import sys
import subprocess

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

def handle_message(message_text, base_folder="Data"):
    msg_raw = (message_text or "").strip()
    msg = msg_raw.upper()

    # COMPARE: e.g., "COMPARE AALI,ADMR" or "COMPARE ADMF AALI"
    if msg.startswith("COMPARE"):
        # ambil substring setelah 'COMPARE'
        rest = msg_raw.strip()[len("COMPARE"):].strip()
        # izinkan pemisah: koma / spasi / titik-koma / slash
        tickers = re.split(r"[,\s/;]+", rest)
        tickers = [t for t in tickers if t]  # drop empty
        # batasi ke 2 ticker saja
        if len(tickers) > 2:
            tickers = tickers[:2]
        return _run_compare(tickers, compare_dir=COMPARE_DIR_DEFAULT)

    if msg == "HI":
        return (
            "Hi! Nama saya Mas Bono, saya bisa bantu cari info saham.\n"
            "Ketik:\n"
            "- [LIST] untuk lihat daftar saham\n"
            "- [KODE EMITEN], untuk mendapatkan strategic summary dan rekomendasi. Contoh: ANTM\n"
            "- COMPARE KODE1,KODE2 untuk membandingkan dua emiten lintas industri (contoh: COMPARE AALI,ADMR)"
        )

    elif msg == "LIST":
        try:
            files = os.listdir(base_folder)
            md_files = sorted([f.replace('.MD', '') for f in files if f.endswith('.MD')])
            return "Daftar saham tersedia:\n" + ("\n".join(md_files) if md_files else "(kosong)")
        except Exception as e:
            return f"Error membaca folder: {str(e)}"

    elif any(msg.startswith(prefix) for prefix in ["FINANCIAL", "BALANCE", "OPERATIONAL", "VALUATION"]):
        parts = msg.split()
        if len(parts) == 2:
            category, kode = parts
            folder_path = os.path.join(base_folder, category)
            result = get_file_content(folder_path, kode)  # baca <KODE>.md
            return result if result else f"Data {category} untuk {kode} belum tersedia."
        else:
            return "Format salah. Contoh: FINANCIAL ANTM"

    else:  # Anggap kode emiten biasa di root Data/
        result = get_file_content(base_folder, msg)  # baca <KODE>.md
        return result if result else (
            "Hi! Nama saya Mas Bono, saya bisa bantu cari info saham.\n"
            "Kode saham yang kamu cari belum tersedia.\n"
            "Ketik:\n"
            "- [LIST] untuk lihat daftar saham\n"
            "- [KODE EMITEN], untuk mendapatkan strategic summary dan rekomendasi. Contoh: ANTM\n"
            "- COMPARE KODE1,KODE2 untuk membandingkan dua emiten lintas industri (contoh: COMPARE AALI,ADMR)"
        )
