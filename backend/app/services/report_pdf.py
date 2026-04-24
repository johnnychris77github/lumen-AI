from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from datetime import datetime

def render_inspection_pdf(doc: dict) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "LumenAI Inspection Report")

    c.setFont("Helvetica", 10)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    c.drawRightString(width - 1*inch, height - 1*inch, f"Generated: {now}")

    y = height - 1.5*inch
    c.setFont("Helvetica-Bold", 12); c.drawString(1*inch, y, "Instrument Details"); y -= 0.25*inch
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, y, f"Instrument: {doc.get('instrument_name','')}"); y -= 0.2*inch
    c.drawString(1*inch, y, f"Inspection ID: {doc.get('id','')}"); y -= 0.2*inch
    c.drawString(1*inch, y, f"Timestamp: {doc.get('timestamp','')}"); y -= 0.5*inch

    c.setFont("Helvetica-Bold", 12); c.drawString(1*inch, y, "AI Findings"); y -= 0.25*inch
    res = doc.get("results", {}) or {}
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, y, f"Material Type: {res.get('material_type','')}"); y -= 0.2*inch
    c.drawString(1*inch, y, f"Stain Detected: {'Yes' if res.get('stain_detected') else 'No'}"); y -= 0.2*inch
    c.drawString(1*inch, y, f"Confidence: {res.get('confidence','')}"); y -= 0.5*inch

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(1*inch, 0.75*inch, "© LumenAI — Automated Lumen Inspection • For clinical QA reference only")

    c.showPage(); c.save()
    pdf = buf.getvalue(); buf.close()
    return pdf
