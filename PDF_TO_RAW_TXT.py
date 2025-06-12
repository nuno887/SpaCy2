import os
import pdfplumber

def extract_text_from_pdf(input_dir: str, output_dir: str) -> None:
    """
    Extracts raw text from all PDF files in the input_dir and saves them
    as .txt files in the output_dir — skipping files that already exist.
    
    Parameters:
        input_dir (str): Directory containing PDF files.
        output_dir (str): Directory to save extracted raw text files.
    """
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    files = os.listdir(input_dir)
    if not files:
        print(f"⚠️ No PDF files found in '{input_dir}'")
        return

    for filename in files:
        if not filename.lower().endswith(".pdf"):
            print(f"⏭️ Skipping non-PDF file: {filename}")
            continue

        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(output_dir, f"{base_name}.txt")

        if os.path.exists(output_path):
            print(f"✅ Skipping existing file: {output_path}")
            continue

        print(f"📄 Processing: {filename}")
        with pdfplumber.open(os.path.join(input_dir, filename)) as pdf:
            raw_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(raw_text)

        print(f"✅ Saved to: {output_path}")

extract_text_from_pdf("PDF_INPUT", "RAW_TXT" )