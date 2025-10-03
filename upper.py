import os

def capitalize_md_files(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".md"):
                old_path = os.path.join(root, file)

                # baca isi file
                with open(old_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # ubah isi jadi kapital
                content_upper = content.upper()

                # buat nama file baru dengan ekstensi .MD kapital
                base_name = os.path.splitext(file)[0].upper()
                new_file = base_name + ".MD"
                new_path = os.path.join(root, new_file)

                # simpan isi baru
                with open(new_path, "w", encoding="utf-8") as f:
                    f.write(content_upper)

                # hapus file lama jika nama berbeda
                if old_path != new_path:
                    os.remove(old_path)

                print(f"✔ {file} -> {new_file}")

if __name__ == "__main__":
    folder = "./"  # ganti ke path folder yg mau diproses
    capitalize_md_files(folder)
