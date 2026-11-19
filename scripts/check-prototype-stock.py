"""Compare fitted order codes against the PCB Parts public JLCPCB snapshot."""
import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from assembly_parts import assembly_suffix, is_fitted, load_board_parts

parser = argparse.ArgumentParser()
parser.add_argument('catalogue', type=Path, help='Checkout of Averyy/pcbparts-mcp')
args = parser.parse_args()
data = args.catalogue / 'data'
stamp = json.loads((data / 'manifest.json').read_text())['scraped_at']
commit = subprocess.check_output(['git', '-C', str(args.catalogue), 'rev-parse', 'HEAD'], text=True).strip()
groups = defaultdict(list)
parts = load_board_parts()
for part in parts.values():
    if not is_fitted(part):
        continue
    stage = 'hand-insert cartridge' if part.get('holder') else 'board component'
    groups[part['mpn'], part.get('lcsc', ''), stage].append(part['ref'])
    if part.get('holder'):
        groups[part['holder']['mpn'], '', 'through-hole fuse holder'].append(part['ref'] + ' holder')

mpns = {k[0].upper() for k in groups}
codes = {k[1] for k in groups if k[1]}
matches = defaultdict(list)
by_code = {}
for path in sorted((data / 'catalog/parts').rglob('*.jsonl')):
    for line in path.open():
        item = json.loads(line)
        code, mpn = item['l'], item['m'].upper()
        if mpn in mpns or code in codes:
            matches[mpn].append(item)
            by_code[code] = item
stock = {}
with (data / 'catalog/stock.tsv').open() as f:
    for code, qty in csv.reader(f, delimiter='\t'):
        if code in by_code:
            stock[code] = int(qty)
dest = Path('output/prototype')
dest.mkdir(exist_ok=True, parents=True)
rows = []
for (mpn, code, stage), refs in sorted(groups.items()):
    needed = len(refs) * 5
    options = matches[mpn.upper()]
    item = by_code.get(code) if code else (options[0] if len(options)==1 else None)
    exact = bool(item and item['m'].upper() == mpn.upper())
    qty = stock.get(item['l']) if exact else None
    status = ('MPN/code mismatch' if item and not exact else 'no unique exact listing') if not exact else ('stock unknown' if qty is None else ('below batch quantity' if qty < needed else 'covers batch in snapshot'))
    rows.append([mpn, code or (item['l'] if item else ''), item['m'] if item else '', item['f'] if item else '', ' '.join(refs), stage, len(refs), needed, qty, status, stamp, commit])
filename = f'five-board-stock{assembly_suffix(parts)}.csv'
with (dest / filename).open('w',newline='') as f:
    out=csv.writer(f)
    out.writerow(['Selected MPN','LCSC','Catalogue MPN','Manufacturer','References','Installation','Per board','Five boards minimum','Snapshot quantity','Result','Catalogue timestamp UTC','PCB Parts commit'])
    out.writerows(rows)
print(f'{dest / filename}: {len(rows)} order lines, {sum(r[7] for r in rows)} pieces for five boards')
for r in rows:
    if r[9] != 'covers batch in snapshot':
        print(r[0], r[1], r[2], r[4], r[7:10])
