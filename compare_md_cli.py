#!/usr/bin/env python3
"""
compare_md_cli.py

Usage:
  python compare_md_cli.py --input AALI,ADMR --compare_dir compare --format whatsapp

Membaca file COMPARE .MD di --compare_dir dan menampilkan
perbandingan lintas industri, skor ringkas, dan kesimpulan.
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Optional

# ---------- pola field yang dibaca dari COMPARE .MD ----------
FIELD_PATTERNS = {
    "Ticker": r"Ticker\s*:\s*([A-Z0-9\.\-]+)",
    "Company": r"Company\s*:\s*([^\n]+)",
    "Sector": r"Sector\s*:\s*([^\n]+)",
    "Industry": r"Industry\s*:\s*([^\n]+)",
    "AsOf": r"AsOf\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",

    "Market Cap": r"Market\s*Cap\s*:\s*([^\n]+)",
    "Price": r"Price\s*:\s*([^\n]+)",
    "PER": r"\bPER\s*:\s*([0-9]+(?:\.[0-9]+)?)x",
    "PBV": r"\bPBV\s*:\s*([0-9]+(?:\.[0-9]+)?)x",
    "Dividend Yield": r"Dividend\s*Yield\s*:\s*([+\-]?[0-9]+(?:\.[0-9]+)?)\s*%",

    "Revenue Growth YoY": r"Revenue\s*Growth\s*YoY\s*:\s*([+\-]?[0-9]+(?:\.[0-9]+)?)\s*%",
    "Net Profit Growth YoY": r"Net\s*Profit\s*Growth\s*YoY\s*:\s*([+\-]?[0-9]+(?:\.[0-9]+)?)\s*%",
    "Net Margin": r"Net\s*Margin\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*%",
    "ROE": r"\bROE\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*%",
    "ROA": r"\bROA\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*%",

    "DER": r"\bDER\s*:\s*([0-9]+(?:\.[0-9]+)?)x",
    "FCF": r"\bFCF\s*:\s*([^\n]+)",

    "ValuationScore": r"ValuationScore\s*:\s*([0-5](?:\.5)?)",
    "ProfitabilityScore": r"ProfitabilityScore\s*:\s*([0-5](?:\.5)?)",
    "BalanceScore": r"BalanceScore\s*:\s*([0-5](?:\.5)?)",
    "IncomeScore": r"IncomeScore\s*:\s*([0-5](?:\.5)?)",
    "TotalScore": r"TotalScore\s*:\s*([0-9]+(?:\.[0-9]+)?)",

    "Highlights": r"Highlights:\s*((?:\n-\s*[^\n]+)+)",
    "Risks": r"Risks:\s*((?:\n-\s*[^\n]+)+)",

    "Source": r"Source\s*:\s*([^\n]+)",
    "Period": r"Period\s*:\s*([^\n]+)",
    "LastUpdate": r"LastUpdate\s*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
}

# ---------- parser & util ----------
def parse_md(path: str) -> Dict[str, object]:
    txt = open(path, "r", encoding="utf-8", errors="ignore").read()
    out: Dict[str, object] = {}
    for k, pat in FIELD_PATTERNS.items():
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if k in ("Highlights", "Risks"):
                items = [ln.strip()[2:].strip() for ln in val.splitlines() if ln.strip().startswith("-")]
                out[k] = items
            else:
                out[k] = val

    # konversi angka untuk skor
    for k in ["ValuationScore","ProfitabilityScore","BalanceScore","IncomeScore"]:
        if isinstance(out.get(k), str):
            try: out[k] = float(out[k])
            except: pass

    # hitung TotalScore jika tidak ada
    if "TotalScore" not in out:
        try:
            s = sum(float(out[k]) for k in ["ValuationScore","ProfitabilityScore","BalanceScore","IncomeScore"]
                    if k in out and isinstance(out[k], (int,float)))
            out["TotalScore"] = round(s, 1)
        except:
            pass

    # konversi angka lain (opsional)
    for pct_key in ["Revenue Growth YoY","Net Profit Growth YoY","Net Margin","ROE","ROA","Dividend Yield"]:
        if pct_key in out:
            try: out[pct_key] = float(out[pct_key])
            except: pass
    for mult_key in ["PER","PBV","DER"]:
        if mult_key in out:
            try: out[mult_key] = float(out[mult_key])
            except: pass

    return out

def stars(total: float) -> str:
    if total is None: return "☆☆☆☆☆"
    v = max(1, min(5, int(round(1 + (float(total)/20.0)*4))))  # 0..20 -> 1..5
    return "★"*v + "☆"*(5-v)

def list_available_tickers(compare_dir: str):
    """Scan folder compare untuk *_COMPARE.MD (case apa pun)."""
    try:
        names = os.listdir(compare_dir)
    except FileNotFoundError:
        return []
    tickers = set()
    for fn in names:
        low = fn.lower()
        if low.endswith(".md"):
            m = re.match(r"^([A-Za-z0-9.\-]+)_compare\.md$", low, flags=re.IGNORECASE)
            if m:
                tickers.add(m.group(1).upper())
            else:
                base = os.path.splitext(fn)[0]
                tickers.add(base.upper())
    return sorted(tickers)

def friendly_not_found(ticker: str, compare_dir: str) -> str:
    avail = list_available_tickers(compare_dir)
    msg = [f"[DATA TIDAK DITEMUKAN] File untuk ticker '{ticker}' tidak ditemukan di folder '{compare_dir}'.",
           "➤ Penamaan yang diharapkan: <TICKER>_COMPARE.MD (UPPERCASE). Contoh: AALI_COMPARE.MD"]
    if avail:
        show = ", ".join(avail[:20]) + (" ..." if len(avail) > 20 else "")
        msg.append(f"➤ Ticker yang tersedia saat ini ({len(avail)}): {show}")
        import difflib
        cand = difflib.get_close_matches(ticker.upper(), avail, n=6, cutoff=0.5)
        if cand:
            msg.append("➤ Mungkin maksud Anda: " + ", ".join(cand))
    else:
        msg.append("➤ Folder tampaknya kosong atau tidak berisi file .MD.")
    return "\n".join(msg)

def find_md(compare_dir: str, ticker: str) -> str:
    """
    Prioritas pencarian:
    1) EXACT uppercase "<TICKER>_COMPARE.MD"
    2) File .MD (uppercase extension) yang diawali <TICKER>
    3) Fallback: file .md (lowercase) yang diawali <ticker>
    """
    expected_upper = f"{ticker.upper()}_COMPARE.MD"
    exact_path = os.path.join(compare_dir, expected_upper)
    if os.path.exists(exact_path):
        return exact_path

    try:
        names = os.listdir(compare_dir)
    except FileNotFoundError:
        raise FileNotFoundError(f"Folder compare tidak ditemukan: {compare_dir}")

    md_upper = [fn for fn in names if fn.upper().startswith(ticker.upper()) and fn.upper().endswith(".MD")]
    if md_upper:
        md_upper.sort()
        return os.path.join(compare_dir, md_upper[0])

    md_any = [fn for fn in names if fn.lower().startswith(ticker.lower()) and fn.lower().endswith(".md")]
    if md_any:
        md_any.sort()
        return os.path.join(compare_dir, md_any[0])

    raise FileNotFoundError(f"Tidak menemukan file .MD untuk {ticker} di {compare_dir}")

# ---------- render & logika kesimpulan ----------
def render_company(d: Dict[str, object]) -> str:
    head = f"{d.get('Ticker','?')} – {d.get('Sector','-')} ({d.get('Industry','-')}) • As of {d.get('AsOf','-')}"
    val = []
    if d.get("Market Cap"): val.append(f"- Market Cap: {d['Market Cap']}")
    if d.get("PER") not in (None, '-', ''): val.append(f"- PER: {d['PER']}x" if not str(d['PER']).endswith("x") else f"- PER: {d['PER']}")
    if d.get("PBV") not in (None, '-', ''): val.append(f"- PBV: {d['PBV']}x" if not str(d['PBV']).endswith("x") else f"- PBV: {d['PBV']}")
    if d.get("Dividend Yield") not in (None, '-', ''): val.append(f"- Dividend Yield: {d['Dividend Yield']}%")

    prof = []
    for k, lbl in [("Revenue Growth YoY","Revenue Growth YoY"),
                   ("Net Profit Growth YoY","Net Profit Growth YoY"),
                   ("Net Margin","Net Margin"),
                   ("ROE","ROE"), ("ROA","ROA")]:
        if d.get(k) not in (None, '-', ''):
            prof.append(f"- {lbl}: {d[k] if isinstance(d[k], str) else f'{d[k]}%'}" if isinstance(d[k], str) else f"- {lbl}: {d[k]}%")

    bal = []
    if d.get("DER") not in (None, '-', ''): bal.append(f"- DER: {d['DER']}x" if not str(d['DER']).endswith("x") else f"- DER: {d['DER']}")
    if d.get("FCF") not in (None, '-', ''): bal.append(f"- FCF: {d['FCF']}")

    score = f"{d.get('ValuationScore','-')}/{d.get('ProfitabilityScore','-')}/{d.get('BalanceScore','-')}/{d.get('IncomeScore','-')}  →  {stars(float(d.get('TotalScore',0) or 0.0))} (Total {d.get('TotalScore','-')})"

    blocks = [head]
    if val: blocks += ["Valuasi:", *val]
    if prof: blocks += ["Profitabilitas:", *prof]
    if bal: blocks += ["Balance & Cash:", *bal]
    blocks += ["Skor (Val/Prof/Balance/Income):", score]

    if d.get("Highlights"):
        hl = "\n".join([f"  • {x}" for x in d["Highlights"]])
        blocks += ["Highlights:", hl]
    if d.get("Risks"):
        rk = "\n".join([f"  • {x}" for x in d["Risks"]])
        blocks += ["Risks:", rk]
    return "\n".join(blocks)

def pick_winner(a: Dict[str, object], b: Dict[str, object]) -> str:
    """Menentukan pemenang: TotalScore, tie-breaker Profitability > Valuation > Income > Balance."""
    def s(d, k):
        v = d.get(k)
        try: return float(v)
        except: return None
    keys = ["TotalScore", "ProfitabilityScore", "ValuationScore", "IncomeScore", "BalanceScore"]
    for k in keys:
        av, bv = s(a, k), s(b, k)
        if av is not None and bv is not None and av != bv:
            return a.get("Ticker","A") if av > bv else b.get("Ticker","B")
    return "Imbang"

def narration(a: Dict[str, object], b: Dict[str, object]) -> List[str]:
    """Buat kalimat narasi perbandingan inti (tanpa emoji)."""
    out: List[str] = []
    # Premium vs murah (PER)
    try:
        pa, pb = float(a.get("PER")), float(b.get("PER"))
        if pa and pb:
            if pa > pb*1.3:
                out.append(f"{a['Ticker']} terlihat premium (PER {pa}x vs {pb}x).")
            elif pb > pa*1.3:
                out.append(f"{b['Ticker']} terlihat premium (PER {pb}x vs {pa}x).")
    except: pass
    # Dividend yield
    try:
        ya, yb = float(a.get("Dividend Yield")), float(b.get("Dividend Yield"))
        if ya and yb:
            diff = abs(ya - yb)
            if ya > yb*1.5: out.append(f"Dividend yield {a['Ticker']} jauh lebih tinggi ({ya:.1f}% vs {yb:.1f}%).")
            elif yb > ya*1.5: out.append(f"Dividend yield {b['Ticker']} jauh lebih tinggi ({yb:.1f}% vs {ya:.1f}%).")
            elif diff >= 0.8: out.append(f"Perbedaan dividend yield moderat ({a['Ticker']} {ya:.1f}% vs {b['Ticker']} {yb:.1f}%).")
    except: pass
    # Net Profit Growth YoY
    try:
        ga, gb = float(a.get("Net Profit Growth YoY")), float(b.get("Net Profit Growth YoY"))
        if (ga is not None) and (gb is not None):
            if ga*gb < 0:
                # kontras tanda
                ticker_better = a['Ticker'] if ga > gb else b['Ticker']
                out.append(f"Pertumbuhan laba kontras; {ticker_better} lebih baik saat ini.")
            else:
                ticker_faster = a['Ticker'] if ga > gb else b['Ticker']
                out.append(f"Keduanya searah; {ticker_faster} tumbuh lebih cepat.")
    except: pass
    return out

def add_emojis_to_notes(notes: List[str]) -> List[str]:
    """Tambahkan emoji berdasarkan kata kunci pada setiap poin kesimpulan."""
    decorated = []
    for n in notes:
        lower = n.lower()
        emoji = ""
        if "dividend" in lower or "yield" in lower:
            emoji = "💰 "
        elif "premium" in lower or "per " in lower:
            emoji = "💎 "
        elif "laba" in lower or "growth" in lower or "tumbuh" in lower:
            # bedakan naik/turun sederhana
            if "lebih cepat" in lower or "lebih baik" in lower:
                emoji = "📈 "
            elif "-" in lower:
                emoji = "📉 "
            else:
                emoji = "📈 "
        elif "risiko" in lower or "risk" in lower or "warning" in lower:
            emoji = "⚠️ "
        else:
            emoji = "🔎 "
        decorated.append(f"- {emoji}{n}")
    return decorated

def winner_line(winner: str) -> str:
    if winner == "Imbang":
        return "- 🤝 Hasil total imbang berdasarkan skor ringkas."
    return f"- 🏆 {winner} tampak **lebih baik** berdasarkan TotalScore dan tie-breakers."

def separator_line(fmt: str) -> str:
    # untuk whatsapp/markdown sama saja supaya aman di dua format
    return "───────────────────────────────"

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Comma-separated tickers (max 2), e.g., AALI,ADMR")
    ap.add_argument("--compare_dir", default="compare", help="Folder tempat file *_COMPARE.MD berada")
    ap.add_argument("--format", choices=["whatsapp","markdown"], default="whatsapp")
    args = ap.parse_args()

    # validasi folder compare
    if not os.path.isdir(args.compare_dir):
        print(f"[ERROR] Folder compare tidak ditemukan: {args.compare_dir}")
        avail = list_available_tickers(args.compare_dir)
        if avail:
            print("Ticker yang terdeteksi:", ", ".join(avail))
        sys.exit(2)

    tickers = [t.strip().upper() for t in args.input.split(",") if t.strip()]
    if not 1 < len(tickers) <= 2:
        print("Harap masukkan 2 ticker, mis. --input AALI,ADMR")
        sys.exit(2)

    paths = []
    for t in tickers:
        try:
            paths.append(find_md(args.compare_dir, t))
        except FileNotFoundError:
            print(friendly_not_found(t, args.compare_dir))
            sys.exit(2)

    a, b = [parse_md(p) for p in paths]

    # Header
    print(f"📊 COMPARISON: {a.get('Ticker','?')} vs {b.get('Ticker','?')}\n")

    # Kesimpulan di atas
    winner = pick_winner(a, b)
    notes_core = narration(a, b)
    notes_with_emoji = add_emojis_to_notes(notes_core)

    print("🏁 Kesimpulan")
    print(winner_line(winner))
    if notes_with_emoji:
        for ln in notes_with_emoji:
            print(ln)
    print()
    print(separator_line(args.format))
    print()

    # Detail per perusahaan
    print(render_company(a)); print()
    print(render_company(b)); print()

if __name__ == "__main__":
    main()
