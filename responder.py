#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Responder untuk WA bot Mas Bono.

Fitur utama:
- HELP/HI
- LIST (daftar Data/*.MD — default uppercase .MD)
- COMPARE <T1>,<T2> (via compare_md_cli.py)
- NEWS <QUERY> [N] (via news_indo_whatsapp)
- HIGHLOW/MA/PIVOT (via market_utils)
- <TICKER> DETAIL  -> tampilkan isi ./Data/<TICKER>.MD
- Default satu kata (asumsi <TICKER>):
    1) Jalankan quick_scan.py --folder ./quick --ticker <TICKER>
    2) Jika quick tidak menemukan file (pesan spesifik) / gagal -> fallback baca ./Data/<TICKER>.MD

Catatan:
- Ekstensi file diasumsikan .MD (huruf besar), mengikuti struktur yang digunakan Mas.
- market_utils sudah auto-append .JK untuk ticker IDX bila perlu.
"""

from __future__ import annotations

import os
import re
import sys
import glob
import textwrap
import subprocess
from typing import Optional, List, Tuple

# ====== Optional dependencies ======
_TECH_ENABLED = True
_TECH_IMPORT_ERR = ""
try:
    from market_utils import weekly_high_low, moving_average, pivot_points
except Exception as e:
    _TECH_ENABLED = False
    _TECH_IMPORT_ERR = f"{type(e).__name__}: {e}"

_NEWS_ENABLED = True
_NEWS_IMPORT_ERR = ""
try:
    # Ekspektasi: news_indo_whatsapp.py punya fungsi handle_news_command(text:str) -> List[str] atau str
    from news_indo_whatsapp import handle_news_command as _news_handle
except Exception as e:
    _NEWS_ENABLED = False
    _NEWS_IMPORT_ERR = f"{type(e).__name__}: {e}"


# ====== Utilities umum ======
_TICKER_PATTERN = r"[A-Z0-9\.\-]{2,10}"

def _which_python() -> Optional[str]:
    """
    Kembalikan jalur interpreter Python yang valid.
    """
    candidates = [sys.executable] if sys.executable else []
    candidates += ["python", "python3", "py"]
    for c in candidates:
        try:
            proc = subprocess.run([c, "--version"], capture_output=True, text=True)
            if proc.returncode == 0:
                return c
        except Exception:
            pass
    return None


def _find_compare_cli() -> Optional[str]:
    """
    Cari compare_md_cli.py di folder file ini atau current working directory.
    """
    names = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_md_cli.py"),
        os.path.join(os.getcwd(), "compare_md_cli.py"),
    ]
    for p in names:
        if os.path.exists(p):
            return p
    return None


def _run_compare(tickers: List[str], compare_dir: Optional[str], timeout: int = 90) -> str:
    """
    Jalankan compare_md_cli.py --input T1,T2 --compare_dir <dir> --format whatsapp
    """
    if len(tickers) != 2:
        return "Perintah COMPARE harus berisi tepat 2 ticker. Contoh: COMPARE ANTM,INCO"

    # Validasi ticker
    val = re.compile(_TICKER_PATTERN + r"$")
    tt = []
    for t in tickers:
        t = t.strip().upper()
        if not val.match(t):
            return f"Ticker tidak valid: {t}. Gunakan huruf/angka/titik/dash, panjang 2-10."
        tt.append(t)

    cli = _find_compare_cli()
    if not cli:
        return "compare_md_cli.py tidak ditemukan. Pastikan file berada di direktori kerja."

    py = _which_python()
    if not py:
        return "Python executable tidak ditemukan."

    cmd = [py, cli, "--input", ",".join(tt), "--format", "whatsapp"]
    if compare_dir:
        cmd += ["--compare_dir", compare_dir]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0:
            return (proc.stdout or "").strip() or "Perbandingan selesai (tanpa output)."
        else:
            err = (proc.stderr or "").strip()
            out = (proc.stdout or "").strip()
            return f"Gagal menjalankan compare.\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    except subprocess.TimeoutExpired:
        return f"Compare timeout (> {timeout}s)."
    except Exception as e:
        return f"Compare error: {type(e).__name__}: {e}"


def _run_quick_scan(ticker: str, folder: str = "./quick", timeout: int = 60):
    """
    Jalankan quick_scan.py --folder ./quick --ticker <ticker>
    Deteksi pesan 'Tidak menemukan file di ./quick untuk '<ticker>'.'
    """
    py = _which_python()
    if not py:
        return {"ok": False, "stdout": "", "stderr": "Python executable tidak ditemukan.", "not_found": False}

    cli = os.path.join(os.getcwd(), "quick_scan.py")
    if not os.path.exists(cli):
        # Tetap kembalikan ok=False supaya fallback jalan
        return {"ok": False, "stdout": "", "stderr": "quick_scan.py tidak ditemukan di working dir.", "not_found": False}

    cmd = [py, cli, "--folder", folder, "--ticker", ticker]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        not_found_phrase = f"Tidak menemukan file di ./quick untuk '{ticker}'."
        not_found = not_found_phrase in stdout
        return {
            "ok": proc.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "not_found": not_found,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"quick_scan timeout > {timeout}s", "not_found": False}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": f"quick_scan error: {e}", "not_found": False}


def get_file_content(folder_path: str, filename_wo_ext: str) -> Optional[str]:
    """
    Baca file <folder>/<FILENAME>.MD (ekstensi .MD uppercase).
    """
    path = os.path.join(folder_path, f"{filename_wo_ext}.MD")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Gagal membaca file {path}: {type(e).__name__}: {e}"
    return None


def _help_text() -> str:
    return (
        "Hi! Nama saya Mas Bono, saya bisa bantu cari info saham.\n"
        "Ketik:\n"
        "- LIST — lihat daftar saham\n"
        "- [KODE EMITEN] — info cepat (contoh: ANTM)\n"
        "- [KODE EMITEN] DETAIL — info lengkap dari Data/<KODE>.MD (contoh: ANTM DETAIL)\n"
        "- COMPARE KODE1,KODE2 — bandingkan dua emiten (contoh: COMPARE AALI,ADMR)\n"
        "- NEWS <KODE/QUERY> [N] — cari berita terbaru (contoh: NEWS BBCA 5)\n"
        "\n🔧 Perintah Teknis:\n"
        "- HIGHLOW <TICKER> [DAYS]        (contoh: HIGHLOW PTBA 7)\n"
        "- MA <TICKER> <WINDOW> [DAILY|WEEKLY]   (contoh: MA BBCA 50 WEEKLY)\n"
        "- PIVOT <TICKER> [DAILY|WEEKLY]  (contoh: PIVOT BBRI WEEKLY)\n"
        "\nℹ️ Default satu kata akan mencoba Quick terlebih dulu via quick_scan,\n"
        "   jika tidak ada akan menampilkan Data/<KODE>.MD.\n"
        "   Ticker IDX otomatis .JK (BBRI -> BBRI.JK) ditangani oleh market_utils.\n"
    )


def _list_md(base_folder: str) -> str:
    """
    Tampilkan daftar file .MD (uppercase) di base_folder (tanpa ekstensi), urut alfabet.
    """
    pattern = os.path.join(base_folder, "*.MD")
    files = sorted(glob.glob(pattern))
    if not files:
        return f"Tidak ada file .MD di folder {base_folder}."
    items = [os.path.splitext(os.path.basename(p))[0] for p in files]
    return "Daftar ticker:\n" + "\n".join(f"- {it}" for it in items)


def _parse_compare_args(msg_raw: str) -> Optional[List[str]]:
    """
    Ambil dua ticker dari 'COMPARE ...' (delimiter bisa koma/spasi/;/|/).
    """
    # Ambil teks setelah kata COMPARE
    m = re.search(r"(?i)\bCOMPARE\b(.*)", msg_raw)
    if not m:
        return None
    tail = m.group(1)
    # split dengan berbagai delimiter
    parts = re.split(r"[\s,;|/]+", tail.strip())
    parts = [p for p in parts if p]
    if not parts:
        return None

    # Ambil maksimal 2 ticker valid
    out: List[str] = []
    val = re.compile("^" + _TICKER_PATTERN + r"$")
    for p in parts:
        up = p.upper()
        if val.match(up):
            out.append(up)
        if len(out) == 2:
            break
    if len(out) != 2:
        return None
    return out


# ====== Dispatcher utama ======
def handle_message(message_text: str, base_folder: str = "Data", compare_dir: Optional[str] = None) -> str:
    """
    Router pesan utama.
    """
    msg_raw = (message_text or "").strip()
    msg = msg_raw.upper()

    # --- HELP / HI ---
    if re.fullmatch(r"(HI|HELP)", msg):
        return _help_text()

    # --- LIST ---
    if msg == "LIST":
        return _list_md(base_folder)

    # --- KATEGORI KHUSUS ---
    m_cat = re.fullmatch(r"(FINANCIAL|BALANCE|OPERATIONAL|VALUATION)\s+(" + _TICKER_PATTERN + r")", msg)
    if m_cat:
        category = m_cat.group(1)
        ticker = m_cat.group(2)
        path = os.path.join(base_folder, category, f"{ticker}.MD")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return f"File untuk {category} {ticker} tidak ditemukan di folder {base_folder}/{category}."

    # --- COMPARE ---
    if msg.startswith("COMPARE"):
        tickers = _parse_compare_args(msg_raw)
        if not tickers:
            return "Format COMPARE tidak valid. Contoh: COMPARE ANTM, INCO"
        return _run_compare(tickers, compare_dir=compare_dir, timeout=90)

    # --- NEWS ---
    if msg.startswith("NEWS"):
        if not _NEWS_ENABLED:
            return f"Fitur NEWS belum aktif: {_NEWS_IMPORT_ERR}"
        try:
            res = _news_handle(msg_raw)  # serahkan parsing argumen ke modul
            if isinstance(res, (list, tuple)):
                return "\n\n".join([str(r) for r in res])
            return str(res)
        except Exception as e:
            return f"Gagal mengambil berita: {type(e).__name__}: {e}"

    # --- TEKNIKAL: HIGHLOW / MA / PIVOT ---
    if msg.startswith("HIGHLOW") or msg.startswith("MA ") or msg.startswith("PIVOT"):
        if not _TECH_ENABLED:
            return f"Fitur teknikal belum aktif: {_TECH_IMPORT_ERR}"

        try:
            if msg.startswith("HIGHLOW"):
                # HIGHLOW <TICKER> [DAYS]
                m = re.fullmatch(r"HIGHLOW\s+(" + _TICKER_PATTERN + r")(?:\s+(\d+))?", msg)
                if not m:
                    return "Format HIGHLOW salah. Contoh: HIGHLOW ANTM 7"
                ticker = m.group(1)
                days = int(m.group(2)) if m.group(2) else 7
                data = weekly_high_low(ticker, days=days)
                return (
                    f"High/Low {ticker} ({days} hari)\n"
                    f"- High: {data.get('highest')}\n"
                    f"- Low:  {data.get('lowest')}\n"
                    f"- Periode: {data.get('start')} → {data.get('end')}"
                )

            if msg.startswith("MA "):
                # MA <TICKER> <WINDOW> [DAILY|WEEKLY]
                m = re.fullmatch(r"MA\s+(" + _TICKER_PATTERN + r")\s+(\d+)(?:\s+(DAILY|WEEKLY))?", msg)
                if not m:
                    return "Format MA salah. Contoh: MA BBCA 50 WEEKLY"
                ticker = m.group(1)
                window = int(m.group(2))
                frame = (m.group(3) or "WEEKLY").upper()
                close, ma = moving_average(ticker, window=window, frame=frame)
                bias = "Bullish ⬆️" if close > ma else "Bearish ⬇️"
                return (
                    f"MA {ticker} ({window}, {frame})\n"
                    f"- Close: {close}\n"
                    f"- MA:    {ma}\n"
                    f"- Sinyal: {bias}"
                )

            if msg.startswith("PIVOT"):
                # PIVOT <TICKER> [DAILY|WEEKLY]
                m = re.fullmatch(r"PIVOT\s+(" + _TICKER_PATTERN + r")(?:\s+(DAILY|WEEKLY))?", msg)
                if not m:
                    return "Format PIVOT salah. Contoh: PIVOT BBRI WEEKLY"
                ticker = m.group(1)
                source = (m.group(2) or "DAILY").upper()
                p = pivot_points(ticker, source=source)
                return (
                    f"Pivot {ticker} ({source})\n"
                    f"- P: {p.get('P')}\n- R1: {p.get('R1')}  R2: {p.get('R2')}\n"
                    f"- S1: {p.get('S1')}  S2: {p.get('S2')}"
                )
        except Exception as e:
            return f"Error teknikal: {type(e).__name__}: {e}"

    # --- <TICKER> DETAIL ---
    parts = msg.split()
    if len(parts) == 2 and re.fullmatch(_TICKER_PATTERN, parts[0]) and parts[1] == "DETAIL":
        ticker = parts[0]
        content = get_file_content(base_folder, ticker)
        if content:
            return content
        return f"Data detail untuk **{ticker}** belum ditemukan di folder *{base_folder}*."

    # --- DEFAULT: asumsikan user kirim satu kata = TICKER ---
    if len(parts) == 1 and re.fullmatch(_TICKER_PATTERN, parts[0]):
        ticker = parts[0]  # sudah uppercase
        # 1) Coba quick_scan.py terlebih dahulu
        quick_res = _run_quick_scan(ticker=ticker, folder="./quick", timeout=60)

        if quick_res["ok"] and not quick_res["not_found"] and quick_res["stdout"]:
            # quick menghasilkan output; langsung tampilkan
            return quick_res["stdout"]

        # 2) Fallback: baca Data/<TICKER>.MD
        content = get_file_content(base_folder, ticker)
        if content:
            return content

        # 3) Tetap tidak ada
        quick_status = (
            "tidak menemukan file" if quick_res.get("not_found")
            else ("gagal" if not quick_res.get("ok") else "tidak ada output")
        )
        return (
            f"Kode saham **{ticker}** belum ditemukan.\n"
            f"- Quick Scan: {quick_status}\n"
            f"- Folder Data: file .MD tidak ditemukan.\n\n"
            f"Silakan cek dengan perintah **LIST** untuk melihat ticker yang tersedia.\n\n"
            f"{_help_text()}"
        )

    # --- Jika tak cocok apa pun, tampilkan HELP ---
    return _help_text()


# ====== Entry manual test kecil ======
if __name__ == "__main__":
    # Contoh manual: python responder.py "ADMF"
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "HELP"
    print(handle_message(q))
