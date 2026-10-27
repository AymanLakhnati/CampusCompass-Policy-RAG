"""Build and verify the submission from a clean, committed source tree.

Large model caches, local credentials, Git internals and QA intermediates are
excluded by the tracked-file manifest. Every ZIP member is checked after writing.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def pack(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            archive.write(source, 'CampusCompass/' + source.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC verification failed.')
        for source in files:
            name = 'CampusCompass/' + source.relative_to(ROOT).as_posix()
            if hashlib.sha256(archive.read(name)).hexdigest() != sha(source):
                raise ValueError('ZIP content hash mismatch: ' + name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-stem', default='CampusCompass_Final_Report')
    parser.add_argument('--presentation', default='CampusCompass_Final_Presentation.pptx')
    parser.add_argument('--receipt', type=Path, default=ROOT / 'build/final_report_receipt.json')
    parser.add_argument('--allow-dirty', action='store_true', help='Preview only; final packages should use a committed source tree.')
    args = parser.parse_args()
    git = lambda *cmd: subprocess.check_output(['git', *cmd], cwd=ROOT)
    dirty = bool(git('status', '--porcelain').strip())
    if dirty and not args.allow_dirty:
        raise SystemExit('Commit the reviewed source before building the final package, or use --allow-dirty for a preview.')
    files = [ROOT / p for p in git('ls-files', '-z').decode().split('\0') if p]
    out = ROOT / 'deliverables'
    artifacts = [out / (args.report_stem + ext) for ext in ('.docx', '.pdf')]
    artifacts.append(out / args.presentation)
    for path in artifacts:
        if not path.is_file():
            raise SystemExit('Missing deliverable: ' + str(path))
    with zipfile.ZipFile(artifacts[2]) as deck:
        xml = ET.fromstring(deck.read('ppt/presentation.xml'))
        ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
        slide_count = len(xml.findall('p:sldIdLst/p:sldId', ns))
    source = out / 'CampusCompass_Final_Source.zip'
    pack(source, files)
    artifacts.append(source)
    receipt = json.loads(args.receipt.read_text(encoding='utf-8')) if args.receipt.exists() else {}
    manifest = {
        'project': 'CampusCompass final revision',
        'repository': 'https://github.com/AymanLakhnati/CampusCompass-Policy-RAG',
        'source_revision': git('rev-parse', 'HEAD').decode().strip(),
        'source_tree_clean': not dirty,
        'presentation_slides': slide_count,
        'report_receipt': receipt,
        'source_files': {p.relative_to(ROOT).as_posix(): sha(p) for p in files},
        'deliverables': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in artifacts},
        'evidence_versions': ['Original V1 results retained', 'V2 regression and frozen audit results stored separately'],
        'notes': ['Fictional policies only; no real student records.', 'Pretrained model weights and private runtime files are excluded.'],
    }
    mp = out / 'FINAL_SUBMISSION_MANIFEST.json'
    mp.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    final = out / 'CampusCompass_Final_Submission.zip'
    pack(final, files + artifacts + [mp])
    print(json.dumps({'package': str(final), 'bytes': final.stat().st_size, 'source_files': len(files), 'verified': True}, indent=2))

if __name__ == '__main__':
    main()
