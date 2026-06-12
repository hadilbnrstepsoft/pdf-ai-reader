import fitz

def extract_pdf_text(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")

    text = []
    for page in doc:
        t = page.get_text()
        if t.strip():
            text.append(t)

    return text