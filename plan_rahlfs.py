#!/usr/bin/env python3
"""
plan_rahlfs.py -- Step 2 of the Rahlfs pipeline. Takes the JSON produced by
parse_rahlfs.py, the TVTMS versification mapping, and one of your .tex
files, and writes a PLAN: one row per verse in the .tex saying which Rahlfs
verse belongs there and what apply_rahlfs.py should do about it.

The plan is a reviewable tab-separated file. Nothing touches your .tex
until you run apply_rahlfs.py with this plan.

Columns:  kjv_ref | tex_state | action | rahlfs_refs | note
  tex_state: 'filled' (an active \\item[LXX] line exists) or 'placeholder'
  action:    'replace' / 'fill' / 'skip'

The end of the report lists JSON verses no .tex verse claimed (LXX-only
material) and .tex verses with no Rahlfs text (edition omissions).

Usage:
    python3 plan_rahlfs.py gospel_scriptures_OT_genesis.tex rahlfs.json
    -> writes gospel_scriptures_OT_genesis_plan.tsv
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fill_lxx import (BOOK_CODES, SWETE_TO_TVTMS, TVTMS_TO_SWETE,
                      load_tvtms, make_test_evaluator)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('texfile')
    ap.add_argument('rahlfs_json')
    ap.add_argument('--tvtms', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    here = Path(__file__).parent
    tvtms_path = args.tvtms or next(iter(sorted(here.glob('TVTMS*.txt'))), None)
    if not tvtms_path:
        sys.exit("Cannot find TVTMS*.txt next to the script; pass --tvtms PATH")

    tex_path = Path(args.texfile)
    out_path = Path(args.out) if args.out else tex_path.with_name(tex_path.stem + '_plan.tsv')

    rahlfs = json.load(open(args.rahlfs_json, encoding='utf-8'))

    # Inventory of the Rahlfs edition, in the same shape the test
    # evaluator expects: {(book, ch, vs): text}
    inventory = {}
    for book, chapters in rahlfs.items():
        for ch, verses in chapters.items():
            for vs, text in verses.items():
                inventory[(book, int(ch), int(vs))] = text
    test_ok = make_test_evaluator(inventory)

    verse_head_re = re.compile(r'\\paragraph\{((?:\d\s)?[A-Za-z ]+?)\s+(\d+):(\d+)')
    lxx_filled_re = re.compile(r'^\s*\\item\[LXX\]\s*\\gr\{.*\}\s*$')
    lxx_placeholder_re = re.compile(r'^\s*(?:%\s*)+\\item\[LXX\]\s*\\gr\{\}\s*$')

    lines = open(tex_path, encoding='utf-8', newline='').readlines()
    books = {BOOK_CODES[m.group(1).strip()]
             for line in lines for m in [verse_head_re.search(line)]
             if m and m.group(1).strip() in BOOK_CODES}
    # All traditions' rules, not just Greek-typed: Rahlfs sometimes follows
    # Hebrew-style numbering, and the inventory tests pick the right rows.
    tvtms = load_tvtms(str(tvtms_path), {SWETE_TO_TVTMS[b] for b in books if b in SWETE_TO_TVTMS},
                       require_greek=False)

    def rahlfs_for(book_code, ch, vs):
        """Return (refs, texts, note) for a KJV reference."""
        std = (SWETE_TO_TVTMS.get(book_code), ch, vs)
        for prio, src_refs, tests in sorted(tvtms.get(std, []), key=lambda c: -c[0]):
            if not test_ok(tests):
                continue
            refs, texts, seen = [], [], set()
            for (gb, gch, gvs) in src_refs:
                key = (TVTMS_TO_SWETE.get(gb, gb), gch, gvs)
                if key in seen:
                    continue
                seen.add(key)
                t = inventory.get(key, '').strip()
                if t:
                    refs.append(f"{key[0]}.{gch}:{gvs}")
                    texts.append(t)
            if texts:
                note = 'remapped' if refs != [f"{book_code}.{ch}:{vs}"] else ''
                return refs, texts, note
        t = inventory.get((book_code, ch, vs), '').strip()
        if t:
            return [f"{book_code}.{ch}:{vs}"], [t], ''
        return [], [], 'no Rahlfs verse (edition omits it or not in JSON)'

    current = None
    rows = []
    claimed = set()
    for line in lines:
        m = verse_head_re.search(line)
        if m and m.group(1).strip() in BOOK_CODES:
            current = (f"{m.group(1).strip()} {m.group(2)}:{m.group(3)}",
                       BOOK_CODES[m.group(1).strip()],
                       int(m.group(2)), int(m.group(3)))
            continue
        if current is None:
            continue
        state = None
        if lxx_filled_re.match(line):
            state = 'filled'
        elif lxx_placeholder_re.match(line):
            state = 'placeholder'
        if state:
            ref, code, ch, vs = current
            refs, texts, note = rahlfs_for(code, ch, vs)
            for r in refs:
                b, rest = r.split('.')
                rc, rv = rest.split(':')
                claimed.add((b, int(rc), int(rv)))
            if texts:
                action = 'replace' if state == 'filled' else 'fill'
            else:
                action = 'skip'
            rows.append((ref, state, action, '+'.join(refs), note))

    unclaimed = sorted(set(inventory) - claimed)
    missing = [r for r in rows if r[2] == 'skip']

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("# plan for %s from %s\n" % (tex_path.name, args.rahlfs_json))
        f.write("# kjv_ref\ttex_state\taction\trahlfs_refs\tnote\n")
        for r in rows:
            f.write('\t'.join(r) + '\n')
        f.write("\n# --- Rahlfs verses no .tex verse claimed (LXX-only material) ---\n")
        for (b, c, v) in unclaimed:
            f.write("# unclaimed\t%s.%d:%d\n" % (b, c, v))

    n_replace = sum(1 for r in rows if r[2] == 'replace')
    n_fill = sum(1 for r in rows if r[2] == 'fill')
    n_remap = sum(1 for r in rows if r[4] == 'remapped')
    print(f"Plan written to {out_path}")
    print(f"  replace existing LXX line: {n_replace}")
    print(f"  fill empty placeholder:    {n_fill}")
    print(f"  skip (no Rahlfs text):     {len(missing)}")
    print(f"  of which remapped refs:    {n_remap}")
    if missing:
        print("\nVerses with no Rahlfs text:")
        for ref, state, action, refs, note in missing:
            print(f"  {ref} ({state}): {note}")
    if unclaimed:
        print(f"\nRahlfs verses unclaimed by this .tex: {len(unclaimed)}"
              f" (listed at the end of the plan)")


if __name__ == '__main__':
    main()
