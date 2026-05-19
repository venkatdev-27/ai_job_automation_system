import sys
import fitz


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python extract_pdf.py <pdf_path>")

    pdf_path = sys.argv[1]
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()

    print("\n".join(pages))


if __name__ == "__main__":
    main()
