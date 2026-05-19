import PyPDF2
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extracts all text content from a PDF file using PyPDF2.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return ""

    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
        return ""

    return text.strip()

if __name__ == "__main__":
    # Quick test if run directly
    import sys
    if len(sys.argv) > 1:
        extracted = extract_text_from_pdf(sys.argv[1])
        print(f"Extracted {len(extracted)} characters.")
        print("-" * 20)
        print(extracted[:500] + "...")
