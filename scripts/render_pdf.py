"""Render each final PDF page for human visual inspection."""
from pathlib import Path
import json
import pypdfium2 as pdfium
root=Path(__file__).resolve().parents[1]
out=root/'build/final_report_pages';out.mkdir(parents=True,exist_ok=True)
for stale in out.glob('page-*.png'): stale.unlink()
pdf=pdfium.PdfDocument(root/'deliverables/CampusCompass_Final_Report.pdf')
for i in range(len(pdf)):
    page=pdf[i]; bitmap=page.render(scale=1.35)
    bitmap.to_pil().save(out/f'page-{i+1:02}.png')
    bitmap.close();page.close()
print(f'Rendered {len(pdf)} pages to {out}')
(root/'build/final_render_receipt.json').write_text(json.dumps({'pdf':'deliverables/CampusCompass_Final_Report.pdf','renderer':'Native Microsoft Word ExportAsFixedFormat followed by bundled pypdfium2','pages':len(pdf),'page_images':'build/final_report_pages','image_scale':1.35,'note':'Native Word fallback used after packaged LibreOffice was confirmed absent on this Windows runtime.'},indent=2),encoding='utf-8')
pdf.close()
