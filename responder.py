import os

def get_file_content(folder_path, filename):
    """
    Membaca file <filename>.md dari folder_path (UTF-8).
    """
    try:
        file_path = os.path.join(folder_path, f"{filename}.md")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return None
    except Exception as e:
        return f"Error membaca file: {str(e)}"

def handle_message(message_text, base_folder="Data"):
    msg = (message_text or "").strip().upper()

    if msg == "HI":
        return (
            "Hi! Nama saya Mas Bono, saya bisa bantu cari info saham.\n"
            "Ketik:\n"
            "- [LIST] untuk lihat daftar saham\n"
            "- [KODE EMITEN], untuk mendapatkan strategic summary dan rekomendasi. Contoh: ANTM\n"            
        )

    elif msg == "LIST":
        try:
            files = os.listdir(base_folder)
            md_files = [f.replace(".md", "") for f in files if f.endswith(".md")]
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
        return result if result else "Data saham belum tersedia."
