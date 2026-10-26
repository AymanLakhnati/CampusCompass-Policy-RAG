"""Build the editable report from its reviewed Markdown source.

Use the Codex bundled Python for document authoring. PDF export is performed
by export_report.ps1 using native Microsoft Word where available.
"""
from pathlib import Path
import json
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables'

def inline(p, text):
    for i, part in enumerate(re.split(r'(\*\*.*?\*\*|\*[^*]+\*|`[^`]+`)', text)):
        r = p.add_run(part.strip('*`') if part.startswith(('*','`')) else part)
        if part.startswith('**'): r.bold = True
        elif part.startswith('*'): r.italic = True
        if part.startswith('`'): r.font.name='Consolas'; r.font.size=Pt(9)

def build():
    OUT.mkdir(exist_ok=True)
    source=(ROOT/'docs/report.md').read_text(encoding='utf-8')
    doc=Document()
    sec=doc.sections[0]
    sec.page_height=Inches(11.7); sec.page_width=Inches(8.3)
    sec.top_margin=Inches(.75); sec.bottom_margin=Inches(.7)
    sec.left_margin=sec.right_margin=Inches(.85)
    normal=doc.styles['Normal']
    normal.font.name='Calibri'; normal.font.size=Pt(11)
    normal.paragraph_format.space_after=Pt(7)
    normal.paragraph_format.line_spacing=1.12
    for name,size,color in [('Title',32,'000000'),('Heading 1',18,'173E52'),('Heading 2',13,'087E8B'),('Heading 3',11,'173E52')]:
        st=doc.styles[name]; st.font.name='Calibri';st.font.size=Pt(size);st.font.color.rgb=RGBColor.from_string(color)
        st.paragraph_format.space_before=Pt(15); st.paragraph_format.space_after=Pt(7)
    doc.core_properties.title='CampusCompass University Policy Support with Retrieval Augmented Generation'
    doc.core_properties.author='Ayman Lakhnati'
    # Title and metadata are kept separate from the assessed main-body count.
    doc.add_paragraph('CampusCompass', 'Title')
    p=doc.add_paragraph('University policy support with retrieval augmented generation')
    p.runs[0].font.size=Pt(18)
    p=doc.add_paragraph('Ayman Lakhnati\nMAAI902 Natural Language Processing and LLMs\nAssessment Task 2  NLP Solution Design\n26 October 2026')
    p.paragraph_format.space_after=Pt(18)
    # Source metadata is retained in Markdown; the designed title block above
    # supplies it once in the Word report.
    main=re.search(r'^## Abstract\s*$',source,re.M)
    lines=source[main.start():].splitlines() if main else source.splitlines(); i=0
    while i<len(lines):
        line=lines[i].strip();i+=1
        if not line:continue
        if line.startswith('# '):continue
        if line.startswith('|') and i<len(lines) and re.match(r'^\|[\s:|\-]+\|$',lines[i].strip()):
            rows=[[x.strip() for x in line.strip('|').split('|')]];i+=1
            while i<len(lines) and lines[i].strip().startswith('|'):
                rows.append([x.strip() for x in lines[i].strip().strip('|').split('|')]);i+=1
            t=doc.add_table(rows=0,cols=len(rows[0]));t.style='Light Shading Accent 1'
            for j,row in enumerate(rows):
                cells=t.add_row().cells
                for c,txt in zip(cells,row):inline(c.paragraphs[0],txt)
                if j==0:
                    trPr=t.rows[j]._tr.get_or_add_trPr(); repeat=OxmlElement('w:tblHeader');trPr.append(repeat)
                    for c in cells:
                        for r in c.paragraphs[0].runs:r.bold=True
            continue
        if line.startswith('### '):doc.add_paragraph(re.sub(r'[^\w\s]','',line[4:]),'Heading 2');continue
        if line.startswith('## '):
            heading=re.sub(r'[^\w\s]','',line[3:])
            if heading.lower().startswith('references'):doc.add_page_break()
            doc.add_paragraph(heading,'Heading 1');continue
        if line.startswith('!['):
            m=re.match(r'!\[(.*?)\]\((.*?)\)',line)
            if m:
                path=ROOT/m.group(2)
                if path.exists():doc.add_picture(str(path),width=Inches(6.4));doc.add_paragraph(m.group(1),'Caption')
            continue
        p=doc.add_paragraph(style='List Bullet' if line.startswith('- ') else 'Normal')
        inline(p,line[2:] if line.startswith('- ') else line)
    footer=sec.footer.paragraphs[0];footer.alignment=2
    r=footer.add_run('CampusCompass   ');r.font.size=Pt(9);r.font.color.rgb=RGBColor.from_string('607180')
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)
    path=OUT/'CampusCompass_Technical_Report.docx';doc.save(path)
    body=re.split(r'^##\s+References',source[main.start():] if main else source,flags=re.M|re.I)[0]
    count=len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b",body))
    receipt={'body_word_count_including_headings':count,'source':'docs/report.md','output':path.name,'count_method':'whitespace-normalized alphanumeric word regex; excludes References onward'}
    (ROOT/'build/report_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':build()
