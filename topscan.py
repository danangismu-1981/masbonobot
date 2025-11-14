#!/usr/bin/env python3
import os
import re
import json
import csv
import sys

# ---------------------------------------
# Helper: path ke sector.json & symbols.txt
# ---------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECTOR_FILE = os.path.join(BASE_DIR, "sector.json")
SYMBOLS_FILE = os.path.join(BASE_DIR, "symbols.txt")

# Default tahun untuk CAGR kalau user tidak sebut tahun
DEFAULT_CAGR_YEAR = 2025


def load_sector_map(path=SECTOR_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_sector_code(query_text, sector_map):
    """
    Cari kode sektor (misal 'A12. Coal') dari query,
    berdasarkan daftar sinonim di sector.json.
    """
    q = query_text.lower()
    for code, synonyms in sector_map.items():
        for syn in synonyms:
            if syn.lower() in q:
                return code
    return None


def to_int_or_zero(s):
    try:
        return int(s)
    except Exception:
        return 0


def to_float_or_zero(s):
    try:
        return float(s)
    except Exception:
        return 0.0


def load_symbols_for_sector(symbols_file, sector_code):
    """
    Baca symbols.txt, ambil emiten yang SUBSECTOR code-nya = sector_code
    (contoh: 'A12. Coal').
    """
    results = []
    with open(symbols_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            # Expect >= 10 kolom:
            # 0: ticker
            # 1: nama
            # 2: main sector
            # 3: sector code (A1. Oil, Gas & Coal)
            # 4: sub sector code (A12. Coal)
            # 5: board
            # 6: lastDevidenNominal:...
            # 7: lastDevidenYield:...
            # 8: fiveyearavgDevidenYield:...
            # 9: MarketCap:...
            # 10+: CAGR2022:..., CAGR2023:..., dst.
            if len(row) < 10:
                continue

            subsector = row[4].strip()
            if subsector != sector_code:
                continue

            data = {
                "symbol": row[0].strip(),
                "name": row[1].strip(),
                "main_sector": row[2].strip(),
                "sector_code": row[3].strip(),
                "subsector_code": subsector,
                "board": row[5].strip(),
            }

            # parse key:value di kolom 6–dst
            for field in row[6:]:
                if ":" in field:
                    k, v = field.split(":", 1)
                    data[k.strip()] = v.strip()

            results.append(data)

    return results


def parse_query_text(args):
    """
    Gabung semua argumen CLI jadi satu string query.
    Contoh pemanggilan:
        python topscan.py Top 10 Batubara
        python topscan.py "Top 10 Batubara deviden"
        python topscan.py "Top 5 coal CAGR 2022"
    """
    if not args:
        print('Pemakaian: python topscan.py "Top x [sektor] [deviden|CAGR [tahun]]"')
        sys.exit(1)
    return " ".join(args)


def extract_top_n(query_text, default_n=5):
    """
    Dari teks 'Top x ...' ambil angka x (jika ada),
    kalau tidak ada, pakai default_n.
    """
    m = re.search(r"top\s*(\d+)", query_text.lower())
    if m:
        return int(m.group(1))
    return default_n


def is_dividend_mode(query_text):
    """
    Cek apakah query minta diurutkan berdasarkan dividen:
    kata kunci: 'deviden' atau 'dividen'.
    """
    q = query_text.lower()
    return ("deviden" in q) or ("dividen" in q)


def is_cagr_mode(query_text):
    """
    Cek apakah query minta diurutkan berdasarkan CAGR / Growth.
    Kata kunci: 'cagr' atau 'growth'.
    """
    q = query_text.lower()
    return ("cagr" in q) or ("growth" in q)


def extract_cagr_year(query_text, default_year=DEFAULT_CAGR_YEAR):
    """
    Cari tahun setelah kata CAGR / Growth, misal:
    'top 5 coal CAGR 2022'  -> 2022
    'top 5 coal growth 2023' -> 2023
    Kalau tidak ketemu -> default_year.
    """
    q = query_text.lower()
    m = re.search(r"(?:cagr|growth)\s*(\d{4})", q)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return default_year



def main():
    # 1. Ambil query dari argumen
    query_text = parse_query_text(sys.argv[1:])

    # 2. Tentukan N (Top N)
    top_n = extract_top_n(query_text, default_n=5)

    # 3. Mode dividen & mode CAGR
    cagr_mode = is_cagr_mode(query_text)
    dividend_mode = is_dividend_mode(query_text) if not cagr_mode else False

    # 4. Kalau mode CAGR, tentukan tahun
    cagr_year = extract_cagr_year(query_text) if cagr_mode else None
    cagr_field = f"CAGR{cagr_year}" if cagr_mode else None

    # 5. Load sector map dan deteksi sektor dari query
    sector_map = load_sector_map(SECTOR_FILE)
    sector_code = detect_sector_code(query_text, sector_map)

    if not sector_code:
        print("❌ Tidak bisa menemukan sektor dari query. "
              "Pastikan kata sektor (misal 'batubara', 'coal', 'bank') ada di sector.json.")
        sys.exit(1)

    # 6. Ambil daftar emiten untuk sektor tersebut dari symbols.txt
    companies = load_symbols_for_sector(SYMBOLS_FILE, sector_code)

    if not companies:
        print(f"❌ Tidak ada emiten dengan subsektor '{sector_code}' di symbols.txt")
        sys.exit(1)

    # 7. Sorting sesuai mode
    if cagr_mode:
        # Urut berdasarkan CAGR tahun tertentu (desc)
        companies.sort(
            key=lambda d: to_float_or_zero(d.get(cagr_field, "")),
            reverse=True,
        )
    elif dividend_mode:
        # Urut berdasarkan lastDevidenYield (desc)
        companies.sort(
            key=lambda d: to_float_or_zero(d.get("lastDevidenYield", "")),
            reverse=True,
        )
    else:
        # Urut berdasarkan MarketCap (desc)
        companies.sort(
            key=lambda d: to_int_or_zero(d.get("MarketCap", "")),
            reverse=True,
        )

    # 8. Ambil Top N
    top_list = companies[:top_n]

    # 9. Print hasil
    if cagr_mode:
        mode_label = cagr_field
    else:
        mode_label = "lastDevidenYield" if dividend_mode else "MarketCap"

    print(f"Query      : {query_text}")
    print(f"Sektor     : {sector_code}")
    print(f"Mode urut  : {mode_label}")
    print(f"Top {len(top_list)} emiten:\n")

    for i, c in enumerate(top_list, start=1):
        mc = c.get("MarketCap", "")
        dy = c.get("lastDevidenYield", "")
        cagr_val = c.get(cagr_field, "") if cagr_mode else ""

        print(f"{i}. {c['symbol']} - {c['name']}")
        print(f"   Board          : {c['board']}")
        print(f"   Subsector      : {c['subsector_code']}")
        print(f"   MarketCap      : {mc}")
        print(f"   lastDevidenYield: {dy}")
        if cagr_mode:
            print(f"   {cagr_field}       : {cagr_val}")
        print()

if __name__ == "__main__":
    main()
