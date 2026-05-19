"""
Master Resume Template Extractor
=================================
Analyzes master resume to extract formatting/styling config.
Stores in MongoDB for use during role resume generation.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path


class MasterTemplateExtractor:
    """Extracts and stores formatting from master resume"""
    
    DEFAULT_TEMPLATE = {
        "font_family": "Calibri",
        "font_size_name": 24,
        "font_size_role": 14,
        "font_size_contact": 10,
        "font_size_section": 13,
        "font_size_body": 11,
        "line_height": 1.25,
        "alignment": "center",  # header alignment
        "margin_top": 0.20,
        "margin_bottom": 0.20,
        "margin_left": 0.5,
        "margin_right": 0.5,
        "section_border": "1.5px solid #111",
        "spacing_after_section": 6,
        "spacing_after_paragraph": 8,
        "spacing_after_bullet": 4,
        "bullet_indent": 18,
    }
    
    @staticmethod
    def analyze_document(local_path: str) -> Dict[str, Any]:
        """
        Analyze a resume document (PDF/DOCX) to extract formatting.
        Returns template config dict.
        """
        path = Path(local_path)
        ext = path.suffix.lower()
        
        template = MasterTemplateExtractor.DEFAULT_TEMPLATE.copy()
        
        if ext == '.pdf':
            template = MasterTemplateExtractor._analyze_pdf(path, template)
        elif ext in ['.docx', '.doc']:
            template = MasterTemplateExtractor._analyze_docx(path, template)
        
        template['source_file'] = str(path)
        template['extracted'] = True
        
        return template
    
    @staticmethod
    def _analyze_pdf(path: Path, template: Dict) -> Dict:
        """Extract deep formatting from PDF using pdfminer"""
        try:
            from pdfminer.high_level import extract_pages
            from pdfminer.layout import LTTextContainer, LTChar, LTLine
            import statistics
            
            template['format'] = 'pdf'
            
            font_sizes = []
            font_names = []
            alignments = []
            
            # Analyze first 2 pages for performance
            pages = list(extract_pages(path))[:2]
            
            for page_layout in pages:
                width = page_layout.width
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        # Simple alignment detection
                        # x0 is left, x1 is right
                        center_x = (element.x0 + element.x1) / 2
                        if abs(center_x - width/2) < width * 0.1:
                            alignments.append('center')
                        else:
                            alignments.append('left')
                            
                        for text_line in element:
                            if not hasattr(text_line, '__iter__'):
                                characters = [text_line]
                            else:
                                characters = text_line
                                
                            for character in characters:
                                if isinstance(character, LTChar):
                                    font_sizes.append(round(character.size, 1))
                                    # Clean font name (e.g. ABCDE+Calibi-Bold -> Calibri)
                                    name = character.fontname
                                    if '+' in name: name = name.split('+')[1]
                                    if '-' in name: name = name.split('-')[0]
                                    font_names.append(name)
            
            if font_sizes:
                # Body font is usually the most frequent size
                try:
                    common_size = statistics.mode(font_sizes)
                    template['font_size_body'] = common_size
                    
                    # Section size is usually slightly larger than body
                    larger_sizes = [s for s in font_sizes if s > common_size]
                    if larger_sizes:
                        template['font_size_section'] = statistics.median(larger_sizes)
                    
                    # Name size is usually the largest
                    template['font_size_name'] = max(font_sizes)
                except:
                    pass
            
            if font_names:
                try:
                    template['font_family'] = statistics.mode(font_names)
                except:
                    pass
                    
            if alignments:
                # If many elements are centered, assume centered header
                center_count = alignments.count('center')
                if center_count > len(alignments) * 0.3:
                    template['alignment'] = 'center'
                else:
                    template['alignment'] = 'left'

            # Bullet detection from text
            from pdfminer.high_level import extract_text
            text = extract_text(path)
            if '•' in text or '·' in text or '○' in text:
                template['bullet_style'] = 'bullet'
            elif '\n-' in text or '\n –' in text:
                template['bullet_style'] = 'dash'
                
            return template
            
        except Exception as e:
            print(f"[WARN] PDF analysis failed: {e}")
            return template
    
    @staticmethod
    def _analyze_docx(path: Path, template: Dict) -> Dict:
        """Extract deep formatting from DOCX using python-docx"""
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            import statistics
            
            doc = Document(str(path))
            template['format'] = 'docx'
            
            sizes = []
            fonts = []
            alignments = []
            
            for para in doc.paragraphs:
                if not para.text.strip():
                    continue
                
                # Capture alignment
                if para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
                    alignments.append('center')
                elif para.alignment == WD_ALIGN_PARAGRAPH.LEFT:
                    alignments.append('left')
                
                for run in para.runs:
                    if run.font.size:
                        sizes.append(run.font.size.pt)
                    if run.font.name:
                        fonts.append(run.font.name)
            
            if sizes:
                common_size = statistics.mode(sizes)
                template['font_size_body'] = round(common_size)
                template['font_size_name'] = round(max(sizes))
                
                sections = [s for s in sizes if common_size < s < max(sizes)]
                if sections:
                    template['font_size_section'] = round(statistics.median(sections))
            
            if fonts:
                template['font_family'] = statistics.mode(fonts)
                
            if alignments:
                if alignments.count('center') > 2: # More than just name
                    template['alignment'] = 'center'
                else:
                    template['alignment'] = 'left'
            
            return template
            
        except Exception as e:
            print(f"[WARN] DOCX analysis failed: {e}")
            return template
    
    @staticmethod
    def generate_html_from_template(template: Dict, content: str, data: Dict) -> str:
        """Generate HTML using extracted template config"""
        
        alignment = template.get('alignment', 'center')
        font_family = template.get('font_family', 'Calibri')
        font_size_name = template.get('font_size_name', 24)
        font_size_role = template.get('font_size_role', 14)
        font_size_contact = template.get('font_size_contact', 10)
        font_size_section = template.get('font_size_section', 13)
        font_size_body = template.get('font_size_body', 11)
        line_height = template.get('line_height', 1.25)
        margin_top = template.get('margin_top', 0.20)
        margin_bottom = template.get('margin_bottom', 0.20)
        margin_left = template.get('margin_left', 0.5)
        margin_right = template.get('margin_right', 0.5)
        
        header_alignment = 'center' if alignment == 'center' else 'left'
        text_align = 'center' if alignment == 'center' else 'left'
        
        contact_val = data.get('contact', '')
        if isinstance(contact_val, dict):
            contact_str = " | ".join([str(v) for v in contact_val.values() if v])
        elif isinstance(contact_val, list):
            contact_str = " | ".join([str(v) for v in contact_val if v])
        else:
            contact_str = str(contact_val)
        
        parts = [p.strip() for p in contact_str.split('|')]
        email = next((p for p in parts if "@" in p), "")
        phone = next((p for p in parts if any(c.isdigit() for c in p) and "@" not in p), "")
        city = data.get('location', 'Hyderabad, India')
        
        links = data.get('links', [])
        linkedin_link = next((l for l in links if "linkedin.com" in l.lower()), None)
        github_link = next((l for l in links if "github.com" in l.lower()), None)
        
        social_parts = []
        if linkedin_link: social_parts.append(f'<a href="{linkedin_link}">LinkedIn</a>')
        if github_link: social_parts.append(f'<a href="{github_link}">GitHub</a>')
        
        row_items = list(filter(None, [email, phone, city]))
        social_row_str = " | ".join(social_parts)
        
        final_contact_line = " | ".join(row_items)
        if social_row_str:
            final_contact_line += f" | {social_row_str}"
        
        header_html = f"""
        <div style="text-align: {header_alignment}; margin-bottom: 5px;">
            <h1 style="margin: 0; font-size: {font_size_name}pt; text-transform: uppercase; font-family: '{font_family}', sans-serif;">{data.get('full_name', '')}</h1>
            <div style="margin-top: 2px; font-size: {font_size_role}pt; font-weight: bold; color: #333;">{data.get('role_title', '')}</div>
            <div style="margin-top: 4px; font-size: {font_size_contact}pt; color: #555;">{final_contact_line}</div>
            <hr style="border: 0; border-top: 1.5px solid #111; margin: 10px 0 12px 0;">
        </div>
        """
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: '{font_family}', 'Arial', sans-serif;
    font-size: {font_size_body}pt;
    line-height: {line_height};
    color: #111111;
    margin: 0;
    padding: {margin_top}in {margin_right}in {margin_bottom}in {margin_left}in;
    max-width: 8.27in;
  }}
  h1, h2, h3, p, ul, li, strong, a {{
    font-family: '{font_family}', sans-serif;
    color: #111111;
    text-decoration: none;
    display: block;
    width: 100%;
    clear: both;
  }}
  a {{ color: #111111; display: inline-block; width: auto; clear: none; }}
  strong {{ display: inline; width: auto; clear: none; }}
  li {{ display: list-item; width: auto; clear: none; }}
  h1 {{ font-weight: 700; }}
  h2 {{
    margin: 15px 0 6px 0;
    font-size: {font_size_section}pt;
    font-weight: 700;
    text-transform: uppercase;
    border-bottom: 1.5px solid #111111;
    padding-bottom: 2px;
  }}
  h3 {{
    margin: 10px 0 2px 0;
    font-size: 11pt;
    font-weight: 700;
  }}
  p {{
    margin: 0 0 8px 0;
    text-align: justify;
  }}
  ul {{
    margin: 0 0 10px 18px;
    padding: 0;
    display: block;
    width: 100%;
  }}
  li {{
    margin: 0 0 4px 0;
    text-align: justify;
  }}
</style>
</head>
<body>
    {header_html}
    {content}
</body>
</html>"""


def extract_master_template(student_id: str, resume_local_path: str) -> Dict[str, Any]:
    """
    Main entry point: Extract template from master resume.
    Returns template config dict.
    """
    return MasterTemplateExtractor.analyze_document(resume_local_path)