"""Render each final PDF page for human visual inspection."""
from pathlib import Path
import pypdfium2 as pdfium
root=Path(__file__).resolve().parents[1]
out=root/'build/report_pages';out.mkdir(parents=True,exist_ok=True)
pdf=pdfium.PdfDocument(root/'deliverables/CampusCompass_Technical_Report.pdf')
for i in range(len(pdf)):
    page=pdf[i]; bitmap=page.render(scale=1.35)
    bitmap.to_pil().save(out/f'page-{i+1:02}.png')
    bitmap.close();page.close()
print(f'Rendered {len(pdf)} pages to {out}')
pdf.close()
