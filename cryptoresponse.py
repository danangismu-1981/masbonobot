#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
cryptoresponse.py

Versi minimal untuk menangani pertanyaan crypto di Mas Bono Bot.
"""

import sys
import io

# ============================================
# FIX: Paksa stdout pakai UTF-8 (supaya emoji tidak error di Windows)
# ============================================
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def generate_crypto_response(user_message: str = "") -> str:
    """
    Generate jawaban standar untuk semua pertanyaan crypto.
    Parameter user_message disiapkan untuk pengembangan ke depan.
    """
    header = "🚧 Fitur Crypto Mas Bono Bot\n"
    body = (
        "Saat ini Mas Bono Bot baru *ditraining khusus* untuk saham-saham "
        "Indonesia di Bursa Efek Indonesia (BEI).\n\n"
        "Permintaan kamu terdeteksi berkaitan dengan *aset crypto* "
        "(seperti BTC, ETH, SOL, XRP, dll).\n\n"
        "Namun fitur analisa crypto **belum diaktifkan** untuk publik.\n"
    )
    footer = (
        "\nSementara ini Mas Bono bisa bantu:\n"
        "• Ringkasan fundamental & valuasi saham Indonesia\n"
        "• Bandingkan beberapa saham (COMPARE)\n"
        "• Cek sektor / subsektor saham berdasarkan kode emiten\n\n"
        "Kalau mau, coba saja kirim:\n"
        "• `BBCA` atau `BBRI` → untuk analisa cepat\n"
        "• `COMPARE BBCA,BBRI` → untuk perbandingan dua saham\n"
        "• `LIST` → untuk lihat daftar perintah yang tersedia\n"
    )

    return header + body + footer


def main() -> None:
    """
    Entry point ketika file ini dijalankan sebagai script.
    Dipanggil dari responder.py:
        python cryptoresponse.py "<pesan user>"
    """
    user_message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    response = generate_crypto_response(user_message)
    sys.stdout.write(response)


if __name__ == "__main__":
    main()
