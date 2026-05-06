from pathlib import Path

from pypdf import PdfWriter


FOLDER = Path(r"C:\Users\diego\Downloads")

folder_input = input(f"Folder with PDFs (Enter = {FOLDER}): ").strip().strip('"')
folder = Path(folder_input or FOLDER).expanduser()

if not folder.is_dir():
    raise NotADirectoryError(f"Folder not found: {folder}")

output_input = input("Output PDF name (Enter = merged.pdf): ").strip().strip('"')
output_path = folder / (output_input or "merged.pdf")

pdf_paths = sorted(
    path
    for path in folder.glob("*.pdf")
    if path.is_file() and path.resolve() != output_path.resolve()
)

if not pdf_paths:
    raise FileNotFoundError(f"No PDFs found in {folder}")

writer = PdfWriter()

for pdf_path in pdf_paths:
    print(f"Adding: {pdf_path.name}")
    writer.append(str(pdf_path))

with output_path.open("wb") as output_file:
    writer.write(output_file)

print(f"Saved: {output_path}")
