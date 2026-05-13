from pathlib import Path

from pypdf import PdfReader, PdfWriter


FOLDER = Path(r"C:\Users\diego\Downloads")


def ask_positive_int(prompt):
    while True:
        value = input(prompt).strip()
        try:
            number = int(value)
        except ValueError:
            print("Please enter a whole number.")
            continue

        if number < 0:
            print("Please enter 0 or a positive number.")
            continue

        return number


side = input("Delete pages from (1=start, 2=end): ").strip().lower()
pages_to_delete = ask_positive_int("How many pages to delete: ")

if side not in ("1", "start", "beginning", "2", "end"):
    raise ValueError("Invalid option. Use 1 for start or 2 for end.")

pdf_paths = sorted(path for path in FOLDER.glob("Fintual*.pdf") if path.is_file())

if not pdf_paths:
    raise FileNotFoundError(f"No Fintual*.pdf files found in {FOLDER}")

for pdf_path in pdf_paths:
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    if pages_to_delete > total_pages:
        print(f"Skipped {pdf_path.name}: only has {total_pages} pages.")
        continue

    if side in ("1", "start", "beginning"):
        pages_to_keep = range(pages_to_delete, total_pages)
    else:
        pages_to_keep = range(0, total_pages - pages_to_delete)

    writer = PdfWriter()
    for page_index in pages_to_keep:
        writer.add_page(reader.pages[page_index])

    output_path = pdf_path.with_name(f"{pdf_path.stem}_cut{pdf_path.suffix}")

    with output_path.open("wb") as output_file:
        writer.write(output_file)

    print(f"Saved: {output_path}")
