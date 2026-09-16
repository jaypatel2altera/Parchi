from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table

BRAND_GREEN = colors.HexColor("#1c6135")
BRAND_GREEN_LIGHT = colors.HexColor("#2f9650")
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
RULE_COLOR = colors.HexColor("#cbd5e1")

PAGE_WIDTH = 100 * mm
MARGIN = 7 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

# Core PDF fonts can't render the ₹ rupee glyph without embedding a
# custom TTF, so bills use the universally-understood "Rs." prefix instead.
CURRENCY = "Rs."


def _rupees(value):
    return f"{CURRENCY} {value}"


def _styles():
    return {
        "shop_name": ParagraphStyle(
            "shop_name", fontName="Helvetica-Bold", fontSize=14, alignment=TA_CENTER,
            textColor=colors.white, leading=17,
        ),
        "contact": ParagraphStyle(
            "contact", fontName="Helvetica", fontSize=7.5, alignment=TA_CENTER,
            textColor=MUTED, leading=10,
        ),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8, textColor=MUTED, leading=11),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8, textColor=INK, leading=10),
        "cell_right": ParagraphStyle(
            "cell_right", fontName="Helvetica", fontSize=8, textColor=INK, leading=10, alignment=2
        ),
        "head_right": ParagraphStyle(
            "head_right", fontName="Helvetica-Bold", fontSize=8, textColor=BRAND_GREEN, leading=10, alignment=2
        ),
        "head_left": ParagraphStyle(
            "head_left", fontName="Helvetica-Bold", fontSize=8, textColor=BRAND_GREEN, leading=10
        ),
        "total_label": ParagraphStyle("total_label", fontName="Helvetica-Bold", fontSize=12, textColor=INK),
        "total_value": ParagraphStyle(
            "total_value", fontName="Helvetica-Bold", fontSize=12, textColor=INK, alignment=2
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica-Oblique", fontSize=7.5, alignment=TA_CENTER,
            textColor=MUTED, leading=10,
        ),
    }


def _dashed_rule():
    return HRFlowable(width="100%", thickness=0.75, color=RULE_COLOR, dash=(2, 2), spaceBefore=4, spaceAfter=4)


def render_bill_pdf(bill) -> bytes:
    styles = _styles()
    items = list(bill.line_items.all())

    # SimpleDocTemplate needs a fixed page size upfront; a receipt has no
    # fixed length, so size the page to the actual content instead of
    # always using a half-empty A5 sheet.
    page_height = max(260 + len(items) * 20, 320)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(PAGE_WIDTH, page_height),
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )

    elements = []

    header_cell = [Paragraph(bill.business.name.upper(), styles["shop_name"])]
    header = Table([header_cell], colWidths=[CONTENT_WIDTH])
    header.setStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_GREEN),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    elements.append(header)
    elements.append(Spacer(1, 10))

    contact_bits = [b for b in (bill.business.phone, bill.business.email) if b]
    if contact_bits:
        elements.append(Paragraph(" • ".join(contact_bits), styles["contact"]))
    if bill.business.address:
        elements.append(Paragraph(bill.business.address, styles["contact"]))

    elements.append(Spacer(1, 6))
    elements.append(_dashed_rule())

    short_id = str(bill.public_id).split("-")[0].upper()
    elements.append(Paragraph(f"Bill #{short_id} &nbsp;&nbsp;|&nbsp;&nbsp; {bill.created_at:%d %b %Y, %I:%M %p}", styles["meta"]))
    if bill.customer_name:
        elements.append(Paragraph(f"Customer: {bill.customer_name}", styles["meta"]))

    elements.append(_dashed_rule())
    elements.append(Spacer(1, 4))

    data = [
        [
            Paragraph("ITEM", styles["head_left"]),
            Paragraph("QTY", styles["head_right"]),
            Paragraph("RATE", styles["head_right"]),
            Paragraph("AMOUNT", styles["head_right"]),
        ]
    ]
    for item in items:
        data.append(
            [
                Paragraph(item.product_name_snapshot, styles["cell"]),
                Paragraph(f"{item.quantity} {item.unit_snapshot}", styles["cell_right"]),
                Paragraph(_rupees(item.unit_price), styles["cell_right"]),
                Paragraph(_rupees(item.line_total), styles["cell_right"]),
            ]
        )

    table = Table(data, colWidths=[28 * mm, 14 * mm, 18 * mm, 26 * mm])
    table.setStyle(
        [
            ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_GREEN_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )
    elements.append(table)

    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.25, color=BRAND_GREEN, spaceAfter=6))

    total_table = Table(
        [[Paragraph("TOTAL", styles["total_label"]), Paragraph(_rupees(bill.total_amount), styles["total_value"])]],
        colWidths=[CONTENT_WIDTH - 26 * mm, 26 * mm],
    )
    total_table.setStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])
    elements.append(total_table)

    elements.append(Spacer(1, 14))
    elements.append(_dashed_rule())
    elements.append(Paragraph("Thank you for shopping with us!", styles["footer"]))
    elements.append(Paragraph("This is a temporary bill, not a tax invoice.", styles["footer"]))

    doc.build(elements)
    return buf.getvalue()
