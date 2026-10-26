"""Execute the plain-Python notebook cells and preserve real printed outputs.

No kernel or notebook package is required. This notebook contains no magics.
"""
from pathlib import Path
import contextlib
import io
import json
import os

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'notebooks/CampusCompass_Demonstration.ipynb'
nb=json.loads(path.read_text(encoding='utf-8'))
scope={'__name__':'__main__'}
os.chdir(ROOT)
count=0
for cell in nb['cells']:
    if cell['cell_type']!='code':continue
    count+=1;output=io.StringIO()
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
        exec(compile(''.join(cell['source']),f'notebook-cell-{count}','exec'),scope)
    cell['execution_count']=count
    cell['outputs']=[{'output_type':'stream','name':'stdout','text':output.getvalue().splitlines(True)}] if output.getvalue() else []
path.write_text(json.dumps(nb,indent=2,ensure_ascii=False),encoding='utf-8')
print(f'Executed {count} code cells without errors: {path}')
