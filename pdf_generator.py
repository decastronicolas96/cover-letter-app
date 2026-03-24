"""
pdf_generator.py

Generates the cover letter PDF using reportlab according to strict CBS formatting guidelines.
"""

from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
import pypdf

def generate_pdf(cover_letter_text: str, company_name: str) -> tuple[bytes, str]:
    """
    Returns PDF as bytes for Streamlit download button, along with any length warnings.
    """
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*72, # 0.75 inches
        leftMargin=0.75*72,
        topMargin=0.75*72,
        bottomMargin=0.75*72
    )

    body_style = ParagraphStyle(
        'BodyText',
        fontName='Times-Roman',
        fontSize=12,
        leading=15,
        spaceAfter=8,
        alignment=TA_JUSTIFY
    )
    
    header_style = ParagraphStyle(
        'HeaderText',
        fontName='Times-Roman',
        fontSize=12,
        leading=15,
        spaceAfter=2,
        alignment=TA_LEFT
    )

    story = []

    # Clean empty lines
    lines = [line.strip() for line in cover_letter_text.split('\n') if line.strip()]
    
    # Separate header, closing sign-off, and body paragraphs properly
    header_lines_extracted = []
    closing_lines = []
    body_lines = []
    
    in_header = True
    in_closing = False
    
    for line in lines:
        if in_header:
            header_lines_extracted.append(line)
            if line.startswith("Dear"):
                in_header = False
        else:
            if line.startswith("Best") or (line == "Nicolas De Castro" and not in_header):
                in_closing = True
                
            if in_closing:
                closing_lines.append(line)
            else:
                body_lines.append(line)
                
    # Add top header block tightly packed
    for h in header_lines_extracted:
        story.append(Paragraph(h, header_style))
        if h.startswith("Dear"):
            story.append(Spacer(1, 10)) # Give breathing room after salutation before body text

    # Add body paragraphs
    for p in body_lines:
        story.append(Paragraph(p, body_style))
        
    # Add closing
    closing_block = [Spacer(1, 15)]
    if not closing_lines:
        closing_lines = ["Best,", "Nicolas De Castro"]
        
    for c in closing_lines:
        closing_block.append(Paragraph(c, header_style))
        
    story.append(KeepTogether(closing_block))

    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    
    # Check page count to ensure it perfectly fits on 1 page
    warning_msg = ""
    try:
        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        if len(reader.pages) > 1:
            warning_msg = f"Warning: PDF exceeds 1 page (generated {len(reader.pages)} pages). Need aggressive word cuts."
    except Exception as e:
        warning_msg = f"Warning: Could not verify page length. {str(e)}"
        
    return pdf_bytes, warning_msg
