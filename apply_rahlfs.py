#!/usr/bin/env python3
"""
apply_rahlfs.py -- Step 3 of the Rahlfs pipeline. Takes the plan written by
plan_rahlfs.py, the rahlfs.json from parse_rahlfs.py, and your .tex file,
and produces a copy of the .tex with the Greek applied:

  - 'replace' rows: the existing \\item[LXX] \\gr{...} line gets the Rahlfs
    text (replacing Swete or whatever was there)
  - 'fill' rows: the commented "% \\item[LXX] \\gr{}" placeholder becomes an
    active line with the Rahlfs text
  - 'skip' rows: the line is left exactly as it is

Everything else in the file is untouched; CRLF line endings are preserved.

Usage:
    python3 apply_rahlfs.py gospel_scriptures_OT_genesis.tex \\
            gospel_scriptures_OT_genesis_plan.tsv rahlfs.json
    -> writes gospel_scriptures_OT_genesis_rahlfs.tex
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fill_lxx import BOOK_CODES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('texfile')
    ap.add_argument('plan')
    ap.add_argument('rahlfs_json')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    tex_path = Path(args.texfile)
    out_path = Path(args.out) if args.out else tex_path.with_name(tex_path.stem + '_rahlfs.tex')

    rahlfs = json.load(open(args.rahlfs_json, encoding='utf-8'))

    # plan: kjv_ref -> (action, [rahlfs refs])
    plan = {}
    for line in open(args.plan, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.rstrip('\n').split('\t')
        if len(parts) < 4:
            continue
        kjv_ref, state, action, refs = parts[0], parts[1], parts[2], parts[3]
        plan[kjv_ref] = (action, [r for r in refs.split('+') if r])

    def text_for(refs):
        out = []
        for r in refs:
            book, rest = r.split('.')
            ch, vs = rest.split(':')
            t = rahlfs.get(book, {}).get(ch, {}).get(vs, '').strip()
            if t:
                out.append(t)
        return ' '.join(out)

    verse_head_re = re.compile(r'\\paragraph\{((?:\d\s)?[A-Za-z ]+?)\s+(\d+):(\d+)')
    lxx_filled_re = re.compile(r'^(\s*)\\item\[LXX\]\s*\\gr\{.*\}\s*$')
    lxx_placeholder_re = re.compile(r'^(\s*)(?:%\s*)+\\item\[LXX\]\s*\\gr\{\}\s*$')

    with open(tex_path, encoding='utf-8', newline='') as f:
        lines = f.readlines()
    eol = '\r\n' if lines and lines[0].endswith('\r\n') else '\n'

    current_ref = None
    replaced = filled = skipped = 0
    out_lines = []
    for line in lines:
        m = verse_head_re.search(line)
        if m and m.group(1).strip() in BOOK_CODES:
            current_ref = f"{m.group(1).strip()} {m.group(2)}:{m.group(3)}"
            out_lines.append(line)
            continue

        action, refs = plan.get(current_ref, (None, []))

        fm = lxx_filled_re.match(line)
        if fm and action == 'replace':
            text = text_for(refs)
            if text:
                out_lines.append(f"{fm.group(1)}\\item[LXX] \\gr{{{text}}}{eol}")
                replaced += 1
                continue

        pm = lxx_placeholder_re.match(line)
        if pm and action == 'fill':
            text = text_for(refs)
            if text:
                indent = pm.group(1)
                out_lines.append(f"{indent}\\item[LXX] \\gr{{{text}}}{eol}")
                filled += 1
                continue

        if (fm or pm) and action == 'skip':
            skipped += 1
        out_lines.append(line)

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(out_lines))

    print(f"Wrote {out_path}")
    print(f"  replaced: {replaced}")
    print(f"  filled:   {filled}")
    print(f"  skipped:  {skipped}")


if __name__ == '__main__':
    main()
