"""Invoice PDF via ReportLab — generated on demand, never stored."""

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .integrations import CustomerView
from .models import Invoice


def render_invoice_pdf(invoice: Invoice, customer: CustomerView | None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    x = 20 * mm
    y = height - 25 * mm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(x, y, "Brightloop Software")
    c.setFont("Helvetica", 11)
    y -= 10 * mm
    c.drawString(x, y, f"Invoice {invoice.invoice_number}")
    y -= 7 * mm
    c.drawString(x, y, f"Status: {invoice.status.upper()}")
    y -= 7 * mm
    c.drawString(x, y, f"Issued: {invoice.issue_date.isoformat()}   Due: {invoice.due_date.isoformat()}")
    y -= 7 * mm
    c.drawString(x, y, f"Period: {invoice.period_start.isoformat()} — {invoice.period_end.isoformat()}")
    y -= 12 * mm

    if customer is not None:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, "Billed to")
        c.setFont("Helvetica", 11)
        y -= 6 * mm
        c.drawString(x, y, customer.name)
        y -= 6 * mm
        c.drawString(x, y, customer.email)
        if customer.billing_address:
            y -= 6 * mm
            c.drawString(x, y, customer.billing_address)
        y -= 6 * mm

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "Description")
    c.drawRightString(x + 90 * mm, y, "Qty")
    c.drawRightString(x + 120 * mm, y, "Unit price")
    c.drawRightString(x + 150 * mm, y, "Tax")
    c.drawRightString(x + 170 * mm, y, "Total")
    y -= 2 * mm
    c.line(x, y, x + 170 * mm, y)
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    for line in invoice.lines:
        if y < 40 * mm:
            c.showPage()
            y = height - 25 * mm
            c.setFont("Helvetica", 10)
        c.drawString(x, y, line.description[:60])
        c.drawRightString(x + 90 * mm, y, str(line.quantity.normalize()))
        c.drawRightString(x + 120 * mm, y, f"{line.unit_price:.2f}")
        c.drawRightString(x + 150 * mm, y, f"{line.tax_amount:.2f}")
        c.drawRightString(x + 170 * mm, y, f"{line.line_total:.2f}")
        y -= 6 * mm

    y -= 4 * mm
    c.line(x + 100 * mm, y, x + 170 * mm, y)
    y -= 6 * mm
    for label, value in [
        ("Subtotal", invoice.subtotal),
        ("Tax", invoice.tax_total),
        ("Discount", -invoice.discount_total),
    ]:
        c.drawString(x + 120 * mm, y, label)
        c.drawRightString(x + 170 * mm, y, f"{value:.2f}")
        y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 120 * mm, y, f"Total ({invoice.currency})")
    c.drawRightString(x + 170 * mm, y, f"{invoice.total_amount:.2f}")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x + 120 * mm, y, "Paid")
    c.drawRightString(x + 170 * mm, y, f"{invoice.amount_paid:.2f}")
    y -= 6 * mm
    c.drawString(x + 120 * mm, y, "Outstanding")
    c.drawRightString(x + 170 * mm, y, f"{invoice.outstanding:.2f}")

    c.save()
    return buf.getvalue()
