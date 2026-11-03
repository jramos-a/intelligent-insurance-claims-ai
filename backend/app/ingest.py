"""Text extraction per format. Images/scanned PDFs need OCR: NOT implemented (raises TypeError)."""
import io, csv
def extract_text(name: str, data: bytes) -> str:
    n = name.lower()
    if n.endswith((".txt", ".md")): return data.decode("utf-8", "replace")
    if n.endswith(".csv"): return "\n".join(" ".join(r) for r in csv.reader(io.StringIO(data.decode("utf-8", "replace"))))
    if n.endswith(".pdf"):
        import fitz
        with fitz.open(stream=data, filetype="pdf") as d: text = "\n".join(p.get_text() for p in d)
        if not text.strip(): raise TypeError("PDF has no text layer (scanned); OCR not implemented")
        return text
    if n.endswith(".docx"):
        import docx
        return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    if n.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        return "\n".join(" ".join(str(c) for c in row if c is not None) for ws in wb for row in ws.iter_rows(values_only=True))
    raise TypeError(f"unsupported format: {name}")
