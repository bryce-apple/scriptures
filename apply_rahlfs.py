#!/usr/bin/env python3
"""
apply_rahlfs.py -- Step 3 of the Rahlfs pipeline. Takes the plan written by
plan_rahlfs.py, the rahlfs.json from parse_rahlfs.py, and your .tex file,
and produces a copy of the .tex with the Greek applied:

  - 'replace' rows: the existing \\item[LXX] \\gr{...} line gets the Rahlfs
    text (replacing Swete or whatever was there)
  - 'fill' rows: the commented "% \\item[LXX] \\gr{}" placeholder becomes an
    active line with the Rahlfs text
  - 'empty' rows: the line becomes \item[LXX] \gr{---}, showing that the
    Rahlfs edition has no verse at this location

Everything else in the file is untouched; CRLF line endings are preserved.

Also writes <texfile>_report.txt: everything that was NOT filled and every
verse worth checking by hand (remapped references, multi-verse
concatenations, lines that already had text and were overwritten).

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

    # plan: kjv_ref -> (action, [rahlfs refs], state, note)
    plan = {}
    unclaimed = []
    skips = []
    for line in open(args.plan, encoding='utf-8'):
        if line.startswith('# unclaimed\t'):
            unclaimed.append(line.split('\t')[1].strip())
            continue
        if line.startswith('#') or not line.strip():
            continue
        parts = line.rstrip('\n').split('\t')
        if len(parts) < 4:
            continue
        kjv_ref, state, action, refs = parts[0], parts[1], parts[2], parts[3]
        note = parts[4] if len(parts) > 4 else ''
        plan[kjv_ref] = (action, [r for r in refs.split('+') if r], state, note)
        if action == 'empty':
            skips.append((kjv_ref, state, note))

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

        action, refs, state, note = plan.get(current_ref, (None, [], '', ''))

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

        if (fm or pm) and action == 'empty':
            indent = (fm or pm).group(1)
            out_lines.append(f"{indent}\\item[LXX] \\gr{{---}}{eol}")
            skipped += 1
            continue
        out_lines.append(line)

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(out_lines))

    # ----- review report: what was NOT put in, and what to check by hand -----
    report_path = tex_path.with_name(tex_path.stem + '_report.txt')
    def ref_key(ref):
        m = re.search(r'(\d+):(\d+)$', ref)
        return (ref.rsplit(' ', 1)[0], int(m.group(1)), int(m.group(2))) if m else (ref, 0, 0)

    manual = sorted((r for r, p in plan.items() if p[0] == 'manual'), key=ref_key)
    # Same Rahlfs verse assigned to several document verses: usually a sign
    # the correspondence is loose (TVTMS 'nearest verse'), not genuine.
    source_uses = {}
    for r, p in plan.items():
        for ref in p[1]:
            source_uses.setdefault(ref, []).append(r)
    reused = sorted(((src_ref, sorted(users, key=ref_key))
                     for src_ref, users in source_uses.items() if len(users) > 1))
    remapped = sorted(((r, p[1]) for r, p in plan.items() if p[3] == 'remapped'),
                      key=lambda x: ref_key(x[0]))
    multi = sorted(((r, p[1]) for r, p in plan.items() if len(p[1]) > 1),
                   key=lambda x: ref_key(x[0]))
    overwritten = sorted((r for r, p in plan.items()
                          if p[0] == 'replace' and p[2] == 'filled'), key=ref_key)
    rep = []
    rep.append(f"apply_rahlfs report for {tex_path.name}")
    rep.append(f"Output: {out_path.name}")
    rep.append("")
    rep.append(f"Filled empty placeholders: {filled}")
    rep.append(f"Replaced existing lines:   {replaced}")
    rep.append(f"Marked empty with ---:     {skipped}")
    rep.append("")
    rep.append("=== No Rahlfs verse: marked with \\gr{---} ===")
    if skips:
        for ref, state, note in skips:
            rep.append(f"  {ref} ({state}): {note}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("=== CHECK BY HAND: commented LXX lines that already contain text ===")
    rep.append("(left untouched; uncomment/replace these yourself, or empty the")
    rep.append(" \\gr{} braces and re-run to have the pipeline fill them)")
    if manual:
        for ref in manual:
            rep.append(f"  {ref}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("=== CHECK BY HAND: filled from a remapped reference ===")
    rep.append("(the verse number in your document differs from the Rahlfs one;")
    rep.append(" confirm against the printed edition)")
    if remapped:
        for ref, refs in remapped:
            rep.append(f"  {ref}  <-  {'+'.join(refs)}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("=== CHECK BY HAND: same Rahlfs verse used for several verses ===")
    rep.append("(repeated Greek text usually means the LXX has no true counterpart")
    rep.append(" for some of these -- consider changing the extras to \\gr{---})")
    if reused:
        for src_ref, users in reused:
            rep.append(f"  {src_ref}  ->  {', '.join(users)}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("=== CHECK BY HAND: built from more than one Rahlfs verse ===")
    if multi:
        for ref, refs in multi:
            rep.append(f"  {ref}  <-  {'+'.join(refs)}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("=== CHECK BY HAND: lines that already had text and were overwritten ===")
    if overwritten:
        for ref in overwritten:
            rep.append(f"  {ref}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("=== Rahlfs verses no verse in this file claimed (LXX-only material) ===")
    if unclaimed:
        for ref in unclaimed:
            rep.append(f"  {ref}")
    else:
        rep.append("  (none)")
    rep.append("")
    rep.append("Final step: run check_lxx.py on the output file and review any")
    rep.append("verse it lists -- those are text differences, not just numbering.")
    Path(report_path).write_text('\n'.join(rep) + '\n', encoding='utf-8')

    print(f"Wrote {out_path}")
    print(f"  replaced: {replaced}")
    print(f"  filled:   {filled}")
    print(f"  marked empty (---): {skipped}")
    print(f"Review report: {report_path}")


if __name__ == '__main__':
    main()
