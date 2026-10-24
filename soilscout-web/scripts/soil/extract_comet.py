"""Extract public COMET-Planner CA records without loading the 2 GB XML workbook.
Usage: python scripts/soil/extract_comet.py /path/to/US_COMETPlanner_data.xlsx
Source URL is recorded in the output. Missing cells are mapped by column reference.
"""
import sys, zipfile, xml.etree.ElementTree as E, re, json, hashlib
from pathlib import Path

source = Path(sys.argv[1])
z = zipfile.ZipFile(source)
ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ss = [''.join(e.itertext()) for e in E.fromstring(z.read('xl/sharedStrings.xml'))]
ca = ss.index('CA')
headers = {}
records = []
with z.open('xl/worksheets/sheet3.xml') as f:
    buf = b''
    while True:
        chunk = f.read(1024 * 1024)
        if not chunk: break
        buf += chunk
        rows = buf.split(b'</row>')
        buf = rows.pop()
        for fragment in rows:
            start = fragment.find(b'<row ')
            if start < 0: continue
            raw = fragment[start:] + b'</row>'
            if headers and not re.search(rb'<c r="A\d+" t="s"><v>' + str(ca).encode() + rb'</v>', raw): continue
            row = E.fromstring(re.sub(rb' x14ac:[^=]+="[^"]*"', b'', raw))
            cells = {}
            for c in row:
                col = re.sub(r'\d', '', c.attrib['r'])
                v = c.find('v')
                text = v.text if v is not None else None
                cells[col] = ss[int(text)] if c.attrib.get('t') == 's' and text is not None else float(text) if text is not None else None
            if not headers: headers = cells; continue
            rec = {name: cells.get(col) for col, name in headers.items()}
            if rec['state'] == 'CA' and rec['cpsnum'] in [340, 345, 329, 336]:
                rec['source_row'] = int(row.attrib['r'])
                # -999 means not estimated, never a physical rate.
                records.append({k: None if v == -999 else v for k, v in rec.items()})
out = {'version': '4.0 Build 2', 'updated': '2025-10-22', 'retrieved': '2026-10-24',
       'url': 'https://storage.googleapis.com/comet-pln-dom-pub/US_COMETPlanner_data.xlsx',
       'sha256': hashlib.file_digest(source.open('rb'), 'sha256').hexdigest(),
       'sheet': 'Emissions Reductions', 'unit': 'metric tonnes CO2e/acre/year',
       'records': records}
target = Path(__file__).resolve().parents[2] / 'public/data/comet-ca.json'
target.write_text(json.dumps(out, separators=(',', ':')))
print(f'{len(records)} records; {len(set(r["county"] for r in records))} counties; {target}')
for r in records:
    if r['county'] == 'Yolo' and r['planner_implementation'] == 'Add Legume Seasonal Cover Crop to Intensive Till Irrigated Cropland': print(r)
