#!/usr/bin/env python3
"""
check_lxx.py -- Compare the LXX text filled into a .tex file (Swete, via
fill_lxx.py) against an independent witness: the Rahlfs text parsed from
your PDF by parse_rahlfs.py.

For every verse that has both a filled \\item[LXX] line and a Rahlfs JSON
entry, the two texts are normalized (accents kept; punctuation, case, and
final-sigma differences ignored) and compared. Verses that differ get a
similarity score; the report lists them worst-first so you can review only
where the editions genuinely disagree.

Usage:
    python3 check_lxx.py gospel_scriptures_OT_genesis.tex rahlfs.json
    python3 check_lxx.py gospel_scriptures_OT_genesis.tex rahlfs.json --threshold 0.95
"""

import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fill_lxx import (BOOK_CODES, SWETE_TO_TVTMS, TVTMS_TO_SWETE,
                      load_tvtms, make_test_evaluator)


def comparable(text):
    """Normalize for comparison: unify mu, drop punctuation/case/final sigma."""
    text = text.replace('µ', 'μ')
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[.,·;:!?()\[\]\u2019\u1fbd\u02bc\u0374\u2014-]', ' ', text)
    text = text.lower().replace('ς', 'σ')
    return ' '.join(text.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('texfile')
    ap.add_argument('rahlfs_json')
    ap.add_argument('--tvtms', default=None)
    ap.add_argument('--swete-words', default=None)  # unused, kept for symmetry
    ap.add_argument('--threshold', type=float, default=0.98,
                    help='similarity below this is reported (default 0.98)')
    args = ap.parse_args()

    here = Path(__file__).parent
    tvtms_path = args.tvtms
    if tvtms_path is None:
        cands = sorted(here.glob('TVTMS*.txt'))
        if not cands:
            sys.exit("Cannot find TVTMS*.txt next to the script; pass --tvtms PATH")
        tvtms_path = cands[0]

    rahlfs = json.load(open(args.rahlfs_json, encoding='utf-8'))

    # Evaluate TVTMS tests against the inventory of the edition we are
    # comparing AGAINST (the Rahlfs JSON), so its own numbering conventions
    # decide which mapping rules apply -- same logic as plan_rahlfs.py.
    inventory = {}
    for book, chapters in rahlfs.items():
        for ch, verses in chapters.items():
            for vs, text in verses.items():
                inventory[(book, int(ch), int(vs))] = text
    test_ok = make_test_evaluator(inventory)

    verse_head_re = re.compile(r'\\paragraph\{((?:\d\s)?[A-Za-z ]+?)\s+(\d+):(\d+)')
    lxx_line_re = re.compile(r'^\s*\\item\[LXX\]\s*\\gr\{(.*)\}\s*$')

    lines = open(args.texfile, encoding='utf-8', newline='').readlines()
    books = {BOOK_CODES[m.group(1).strip()]
             for line in lines for m in [verse_head_re.search(line)]
             if m and m.group(1).strip() in BOOK_CODES}
    tvtms = load_tvtms(tvtms_path, {SWETE_TO_TVTMS[b] for b in books},
                       require_greek=False)

    def rahlfs_lookup(book_code, ch, vs):
        """Map a KJV ref to Greek numbering, then look up the Rahlfs JSON."""
        std = (SWETE_TO_TVTMS.get(book_code), ch, vs)
        for prio, src_refs, tests in sorted(tvtms.get(std, []), key=lambda c: -c[0]):
            if not test_ok(tests):
                continue
            texts = []
            for (gb, gch, gvs) in src_refs:
                b = TVTMS_TO_SWETE.get(gb, gb)
                t = rahlfs.get(b, {}).get(str(gch), {}).get(str(gvs))
                if t:
                    texts.append(t)
            if texts:
                return ' '.join(texts)
        return rahlfs.get(book_code, {}).get(str(ch), {}).get(str(vs))

    current = None
    compared = missing_rahlfs = 0
    results = []
    shift_hits = {}
    for line in lines:
        m = verse_head_re.search(line)
        if m and m.group(1).strip() in BOOK_CODES:
            current = (f"{m.group(1).strip()} {m.group(2)}:{m.group(3)}",
                       BOOK_CODES[m.group(1).strip()],
                       int(m.group(2)), int(m.group(3)))
            continue
        lm = lxx_line_re.match(line)
        if lm and current:
            ref, code, ch, vs = current
            tex_text = lm.group(1)
            if tex_text.strip() == '---':
                continue  # empty-verse marker, nothing to compare
            r_text = rahlfs_lookup(code, ch, vs)
            if not r_text:
                missing_rahlfs += 1
                continue
            compared += 1
            ratio = difflib.SequenceMatcher(
                None, comparable(tex_text), comparable(r_text)).ratio()
            if ratio < args.threshold:
                results.append((ratio, ref, tex_text, r_text))

            # Independent shift detector: does a NEIGHBORING verse in the
            # JSON match this .tex verse much better than the assigned one?
            # (Catches systematic off-by-one mapping errors, which the main
            # comparison cannot see because it uses the same mapping.)
            for d in (-1, 1):
                n_text = rahlfs.get(code, {}).get(str(ch), {}).get(str(vs + d))
                if not n_text:
                    continue
                n_ratio = difflib.SequenceMatcher(
                    None, comparable(tex_text), comparable(n_text)).ratio()
                if n_ratio > ratio + 0.15 and n_ratio > 0.8:
                    shift_hits.setdefault((code, ch), []).append((vs, d))

    results.sort()
    out = []
    out.append(f"Compared {compared} verses "
               f"({missing_rahlfs} in the .tex had no Rahlfs entry to check against)")
    out.append(f"Verses below similarity {args.threshold}: {len(results)}")
    out.append("")
    for ratio, ref, tex_text, r_text in results:
        out.append(f"--- {ref}  (similarity {ratio:.2f})")
        out.append(f"  in .tex:    {tex_text}")
        out.append(f"  Rahlfs:     {r_text}")
        out.append("")
    suspicious = {k: v for k, v in shift_hits.items() if len(v) >= 3}
    if suspicious:
        out.append("!!! POSSIBLE SYSTEMATIC SHIFTS (mapping may be wrong) !!!")
        out.append("A neighboring JSON verse matches these .tex verses much better")
        out.append("than the assigned one -- check the chapter against the PDF:")
        for (code, ch), hits in sorted(suspicious.items()):
            ds = {d for _, d in hits}
            out.append(f"  {code} chapter {ch}: {len(hits)} verses match better at "
                       f"offset {'/'.join('%+d' % d for d in sorted(ds))}")
        out.append("")
    report = "\n".join(out)
    print(report)
    report_path = Path(args.texfile).with_name(Path(args.texfile).stem + '_check.txt')
    report_path.write_text(report + "\n", encoding='utf-8')
    print(f"(also written to {report_path})")


if __name__ == '__main__':
    main()
