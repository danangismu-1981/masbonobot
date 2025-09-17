import os
import shutil

def move_md_files(root_dir=".", target_folder="Data"):
    """
    Memindahkan semua file .MD atau .md dari root_dir (folder root project)
    ke dalam folder target_folder (default 'Data').
    """
    root_dir = os.path.abspath(root_dir)
    target_dir = os.path.join(root_dir, target_folder)

    # Pastikan target folder ada
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"Folder {target_dir} dibuat.")

    moved = []
    for f in os.listdir(root_dir):
        if f.lower().endswith(".md"):  # cocokkan .md maupun .MD
            src = os.path.join(root_dir, f)
            dst = os.path.join(target_dir, f.upper().replace(".MD", ".md"))  # rapikan jadi uppercase.md
            shutil.move(src, dst)
            moved.append(dst)

    if moved:
        print("File .md berhasil dipindahkan ke folder Data:")
        for m in moved:
            print(" -", m)
    else:
        print("Tidak ada file .md di root.")

if __name__ == "__main__":
    move_md_files()
