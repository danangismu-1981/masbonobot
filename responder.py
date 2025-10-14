#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Responder untuk WA bot Mas Bono.

Fitur utama (dipertahankan & dirapikan):
- HELP/HI
- LIST (daftar Data/*.MD — default uppercase .MD)
- COMPARE <T1>,<T2> (via compare_md_cli.py)
- NEWS <QUERY> [N] (via news_indo_whatsapp)
- HIGHLOW/MA/PIVOT (via market_utils)
- <TICKER> DETAIL  -> tampilkan isi ./Data/<TICKER>.MD
- Default satu kata (asumsi <TICKER>):
    1) Jalankan quick_scan.py --folder ./quick --ticker <TICKER>
    2) Jika quick tidak menemukan file / gagal -> fallback baca ./Data/<TICKER>.MD

Tambahan baru (sesuai permintaan):
- Deteksi TICKER di kalimat natural menggunakan symbols.txt (selevel responder.py).
  Contoh: "mas, minta tolong analisa untuk BMRI dong" -> diproses sama seperti "BMRI".
- Jika pesan mengandung >=2 ticker dan ada indikasi 'compare intent' (atau/koma/vs/banding/...),
  bot langsung menjalankan COMPARE dua ticker pertama yang ditemukan.
"""

import os
import re
import sys
import glob
import textwrap
import subprocess
from typing import Optional, List, Tuple
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

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


# ====== Helper: greeting berbasis waktu & nama (NEW) ======
def _period_id_hour(hour: int) -> str:
    """
    Mapping jam → periode salam Bahasa Indonesia.
    04–10: pagi, 10–15: siang, 15–18: sore, lainnya: malam
    """
    if 4 <= hour < 10:
        return "pagi"
    if 10 <= hour < 15:
        return "siang"
    if 15 <= hour < 18:
        return "sore"
    return "malam"


def _time_based_greeting(name: Optional[str] = None, tz: str = "Asia/Jakarta") -> str:
    """Bangun kalimat salam lengkap; nama diambil dari argumen, env WA_SENDER_NAME, atau 'kawan'. """
    try:
        if 'ZoneInfo' in globals() and ZoneInfo is not None:
            now = datetime.now(ZoneInfo(tz))
        else:
            now = datetime.now()
    except Exception:
        now = datetime.now()
    phase = _period_id_hour(now.hour)
    display_name = (name or os.environ.get("WA_SENDER_NAME") or "kawan").strip()
    return f"Hi, selamat {phase} {display_name}! 👋\nApa ada saham yang ingin dianalisa hari ini?"


# Deteksi salam natural (hi/halo/hello/selamat pagi/siang/sore/malam)
_GREETING_PAT = re.compile(
    r"\b(hi|halo|hello|pagi|siang|sore|malam|selamat\s+pagi|selamat\s+siang|selamat\s+sore|selamat\s+malam)\b",
    flags=re.IGNORECASE
)


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


def _run_compare(tickers: List[str], timeout: int = 60) -> str:
    """
    Jalankan compare_md_cli.py --input <T1,T2> --compare_dir compare --format whatsapp
    """
    py = _which_python()
    if not py:
        return "Python executable tidak ditemukan."

    cli = _find_compare_cli()
    if not cli:
        return "compare_md_cli.py tidak ditemukan."

    if len(tickers) != 2:
        return "Butuh tepat 2 ticker untuk COMPARE."

    # Gunakan format baru dengan flag --input
    cmd = [py, cli, "--input", f"{tickers[0]},{tickers[1]}", "--compare_dir", "compare", "--format", "whatsapp"]

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
        ok = proc.returncode == 0

        not_found = False
        nf_msg = f"Tidak menemukan file di {folder} untuk '{ticker}'"
        if nf_msg.lower() in stdout.lower() or nf_msg.lower() in stderr.lower():
            not_found = True

        return {"ok": ok, "stdout": stdout, "stderr": stderr, "not_found": not_found}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"timeout (> {timeout}s).", "not_found": False}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": f"{type(e).__name__}: {e}", "not_found": False}


def get_file_content(base_folder: str, ticker: str) -> Optional[str]:
    """
    Baca isi file ./Data/<TICKER>.MD (uppercase) — fallback jika quick gagal.
    """
    t = (ticker or "").upper()
    filename = os.path.join(base_folder, f"{t}.MD")
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Gagal membaca {filename}: {type(e).__name__}: {e}"
    return None


def _help_text() -> str:
    return textwrap.dedent(
        """
        **Mas Bono Bot – Bantuan Singkat**

        • Ketik **LIST** → daftar ticker yang tersedia di folder Data.
        • Ketik **BMRI** → analisa cepat (Quick) untuk BMRI, fallback ke Data/BMRI.MD kalau Quick belum ada.
        • Ketik **BMRI DETAIL** → tampilkan isi Data/BMRI.MD.
        • Ketik **COMPARE BMRI,BBCA** → bandingkan dua ticker.
        • Ketik **NEWS BMRI 5** → 5 berita terbaru terkait BMRI (butuh modul news_indo_whatsapp).
        • Ketik **HIGHLOW BMRI 30** | **MA BMRI 200** | **PIVOT BMRI** → analisa teknikal (butuh market_utils).

        Tips: Kamu juga bisa tulis kalimat natural, misalnya **"minta tolong analisa BMRI"**, dan aku akan otomatis mengenali tickernya.
        """
    ).strip()


def _list_md(base_folder: str = "./Data") -> str:
    """
    Tampilkan daftar file .MD (uppercase) di folder Data.
    """
    pattern = os.path.join(base_folder, "*.MD")
    files = sorted(glob.glob(pattern))
    if not files:
        return "Tidak ada file .MD di folder Data."
    items = [os.path.splitext(os.path.basename(x))[0] for x in files]
    return "**Daftar ticker (Data):**\n" + ", ".join(items)


def _parse_compare_args(msg_raw: str) -> Optional[Tuple[str, str]]:
    """
    Ekstrak 2 ticker untuk perintah COMPARE.
    Terima format:
      - COMPARE T1,T2
      - COMPARE T1 T2
      - COMPARE: T1 vs T2 (longgar)
    """
    s = (msg_raw or "").strip()
    s_up = s.upper()

    # Ambil setelah kata COMPARE
    m = re.search(r"\bCOMPARE\b(.*)$", s_up)
    if not m:
        return None
    tail = m.group(1)

    # Coba pisah dengan koma dulu
    parts = re.split(r"[,\s]+", tail)
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

    return (out[0], out[1])


# ====== Natural-language ticker detection (NEW, sesuai symbols.txt) ======
def _is_compare_intent(text: str) -> bool:
    """
    Deteksi niat 'bandingkan' secara longgar.
    Menangkap kata/konteks: 'compare', 'banding', 'vs', 'atau', 'bagus mana', 'lebih baik',
    atau penggunaan koma di antara dua ticker (heuristik longgar).
    """
    t = (text or "").upper()
    keywords = ["COMPARE", "BANDING", " VS ", " ATAU ", " BAGUS MANA", " LEBIH BAIK", " PILIH "]
    if any(k in t for k in keywords):
        return True
    if "," in t:
        return True
    return False


def _symbols_path(default_name: str = "symbols.txt") -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), default_name)


def _load_symbols(symbols_path: Optional[str] = None) -> set:
    if not symbols_path:
        symbols_path = _symbols_path()
    syms = set()
    try:
        with open(symbols_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip().upper()
                if s:
                    syms.add(s)
    except Exception:
        pass
    return syms


def _find_tickers_in_text(message_text: str, symbols: set) -> List[str]:
    """
    Ambil semua token yang *bentuknya* ticker lalu filter yang ada di symbols.txt.
    Urutan kemunculan dipertahankan.
    """
    tokens = re.findall(_TICKER_PATTERN, (message_text or "").upper())
    seen, tickers = set(), []
    for t in tokens:
        if t in symbols and t not in seen:
            tickers.append(t)
            seen.add(t)
    return tickers


def _handle_single_ticker_request(ticker: str, base_folder: str) -> str:
    """
    Jalankan alur default untuk satu ticker:
      1) Coba quick_scan.py
      2) Fallback baca Data/<TICKER>.MD
      3) Jika gagal semua -> pesan bantuan
    """
    # 1) Quick terlebih dulu
    quick_res = _run_quick_scan(ticker=ticker, folder="./quick", timeout=60)

    if quick_res["ok"] and not quick_res["not_found"] and quick_res["stdout"]:
        return quick_res["stdout"]

    # 2) Fallback baca Data/<TICKER>.MD
    content = get_file_content(base_folder, ticker)
    if content:
        return content

    # 3) Tidak ada dua-duanya
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


# ====== Dispatcher utama ======
def handle_message(msg_raw: str, base_folder: str = "./Data") -> str:
    """
    Fungsi utama yang akan dipanggil WA bot.
    Tidak mengubah signature/kontrak dasar.
    """
    msg_raw = (msg_raw or "").strip()
    if not msg_raw:
        return _help_text()

    msg_up = msg_raw.upper()

    # --- Salam/Help ---
# 1) Salam natural → balas greeting berbasis waktu + ringkasan bantuan
if _GREETING_PAT.search(msg_raw):
    greet = _time_based_greeting()
    return f"{greet}\n\n{_help_text()}"

# 2) HELP/menu eksplisit → tampilkan bantuan
if msg_up in ("HELP", "MENU"):
    return _help_text()

    # --- LIST ---
    if msg_up.startswith("LIST"):
        return _list_md(base_folder)

    # --- COMPARE ---
    if msg_up.startswith("COMPARE"):
        pair = _parse_compare_args(msg_raw)
        if pair:
            return _run_compare([pair[0], pair[1]], timeout=90)
        else:
            return (
                "Format COMPARE tidak dikenali. Contoh yang benar:\n"
                "- COMPARE BMRI,BBCA\n- COMPARE BMRI BBCA"
            )

    # --- NEWS ---
    if msg_up.startswith("NEWS"):
        if not _NEWS_ENABLED:
            return f"Fitur NEWS belum aktif: {_NEWS_IMPORT_ERR}"
        # Kirim seluruh pesan ke handler news agar kompatibel dengan format lama (NEWS <QUERY> [N])
        try:
            result = _news_handle(msg_raw)
            if isinstance(result, list):
                return "\n\n".join(result)
            return str(result)
        except Exception as e:
            return f"Gagal memproses NEWS: {type(e).__name__}: {e}"

    # --- ANALISA TEKNIKAL (opsional) ---
        # --- ANALISA TEKNIKAL (opsional) ---
    if msg_up.startswith("HIGHLOW") or msg_up.startswith("MA ") or msg_up.startswith("PIVOT"):
        if not _TECH_ENABLED:
            return f"Fitur teknikal belum aktif: {_TECH_IMPORT_ERR}"
        try:
            parts = msg_up.split()

            if msg_up.startswith("HIGHLOW"):
                # HIGHLOW <TICKER> <N>
                if len(parts) < 3:
                    return "Format: HIGHLOW <TICKER> <N_HARI>"
                tick, n = parts[1], int(parts[2])
                res = weekly_high_low(tick, n)  # <-- dict: highest/lowest/start/end
                return (
                    f"HIGH/LOW {tick} {n} hari "
                    f"({res.get('start','?')} → {res.get('end','?')}):\n"
                    f"- High: {res.get('highest','?')}\n"
                    f"- Low : {res.get('lowest','?')}"
                )

            if msg_up.startswith("MA "):
                # MA <TICKER> <PERIOD> [DAILY|WEEKLY]
                if len(parts) < 3:
                    return "Format: MA <TICKER> <PERIOD> [DAILY|WEEKLY]"
                tick = parts[1]
                window = int(parts[2])
                frame = parts[3].lower() if len(parts) >= 4 else "weekly"
                last_close, last_ma = moving_average(tick, window=window, frame=frame)  # <-- tuple
                return (
                    f"MA {tick} ({window}, {frame}):\n"
                    f"- Close terakhir: {last_close}\n"
                    f"- MA{window}: {last_ma}"
                )

            if msg_up.startswith("PIVOT"):
                # PIVOT <TICKER> [DAILY|WEEKLY]
                if len(parts) < 2:
                    return "Format: PIVOT <TICKER> [DAILY|WEEKLY]"
                tick = parts[1]
                src = parts[2].lower() if len(parts) >= 3 else "weekly"
                res = pivot_points(tick, source=src)  # <-- dict: P/R1/S1/R2/S2
                return (
                    f"PIVOT {tick} ({src}):\n"
                    f"- Pivot: {res.get('P','?')}\n"
                    f"- R1   : {res.get('R1','?')}\n"
                    f"- R2   : {res.get('R2','?')}\n"
                    f"- S1   : {res.get('S1','?')}\n"
                    f"- S2   : {res.get('S2','?')}"
                )
        except Exception as e:
            return f"Gagal menghitung analisa teknikal: {type(e).__name__}: {e}"


    # --- <TICKER> DETAIL ---
    m_detail = re.match(rf"^\s*({_TICKER_PATTERN})\s+DETAIL\s*$", msg_up)
    if m_detail:
        ticker = m_detail.group(1)
        content = get_file_content(base_folder, ticker)
        return content or f"File Data/{ticker}.MD tidak ditemukan."

    # --- NATURAL LANGUAGE: deteksi ticker dari symbols.txt ---
    # Misal: "minta analisa BMRI dong", "tolong info BBCA", "bagus mana BMRI atau BBRI", dsb.
    symbols = _load_symbols()
    if symbols:
        found = _find_tickers_in_text(msg_raw, symbols)
        if len(found) == 1:
            return _handle_single_ticker_request(found[0], base_folder)
        elif len(found) >= 2:
            # Jika ada sinyal 'compare intent' atau ada koma, langsung jalankan COMPARE dua pertama
            if _is_compare_intent(msg_raw):
                return _run_compare([found[0], found[1]], timeout=90)
            # Jika tidak yakin, beri panduan COMPARE agar tidak salah maksud
            t1, t2 = found[0], found[1]
            return (
                "Terdeteksi lebih dari satu ticker dalam pesan.\n"
                f"Coba perintah: **COMPARE {t1},{t2}**\n\n"
                f"{_help_text()}"
            )

    # --- DEFAULT: satu kata yang terlihat seperti ticker ---
    parts = msg_up.split()
    if len(parts) == 1 and re.fullmatch(_TICKER_PATTERN, parts[0]):
        ticker = parts[0]
        return _handle_single_ticker_request(ticker, base_folder)

    # --- Fallback: bantuan ---
    return _help_text()


# ====== CLI mode sederhana (opsional untuk testing cepat) ======
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Responder WA Bot Mas Bono")
    parser.add_argument("message", type=str, nargs="*", help="Pesan user")
    parser.add_argument("--data", type=str, default="./Data", help="Folder Data (default: ./Data)")
    args = parser.parse_args()

    msg = " ".join(args.message)
    print(handle_message(msg, base_folder=args.data))
