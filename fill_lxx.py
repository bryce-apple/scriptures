#!/usr/bin/env python3
"""
fill_lxx.py -- Fill empty "% \\item[LXX] \\gr{}" placeholders in a scripture
.tex file with Greek text from Swete's LXX (1930), using the TVTMS
versification mapping to translate KJV references to Greek-tradition ones.

Inputs (all downloadable, see URLs below):
  1. Your .tex file (e.g. gospel_scriptures_OT_genesis.tex)
  2. Swete word list:      01-Swete_word_with_punctuations.csv
     https://raw.githubusercontent.com/eliranwong/LXX-Swete-1930/master/01-Swete_word_with_punctuations.csv
  3. Swete verse index:    00-Swete_versification.csv
     https://raw.githubusercontent.com/eliranwong/LXX-Swete-1930/master/00-Swete_versification.csv
  4. TVTMS mapping:
     https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Versification/TVTMS%20-%20Translators%20Versification%20Traditions%20with%20Methodology%20for%20Standardisation%20for%20Eng%2BHeb%2BLat%2BGrk%2BOthers%20-%20STEPBible.org%20CC%20BY.txt

Output:
  - A copy of the .tex file with the Greek filled in (default: <input>_lxx.tex)
  - A report of everything that was filled, skipped, or needs attention
    (default: <input>_lxx_report.txt, also printed to the terminal)

Usage:
  python3 fill_lxx.py gospel_scriptures_OT_genesis.tex
  python3 fill_lxx.py gospel_scriptures_OT_genesis.tex --out out.tex
  (use --swete-words / --swete-verses / --tvtms if the data files are not
   in the same directory as this script)
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Book names as they appear in \paragraph{...} -> Swete CSV book codes
# ---------------------------------------------------------------------------
BOOK_CODES = {
    'Genesis': 'Gen', 'Exodus': 'Exo', 'Leviticus': 'Lev', 'Numbers': 'Num',
    'Deuteronomy': 'Deu', 'Joshua': 'Jos', 'Judges': 'Jdg', 'Ruth': 'Rut',
    '1 Samuel': '1Sa', '2 Samuel': '2Sa', '1 Kings': '1Ki', '2 Kings': '2Ki',
    '1 Chronicles': '1Ch', '2 Chronicles': '2Ch', 'Ezra': 'Ezr',
    'Nehemiah': 'Neh', 'Esther': 'Est', 'Job': 'Job', 'Psalm': 'Psa',
    'Psalms': 'Psa', 'Proverbs': 'Pro', 'Ecclesiastes': 'Ecc',
    'Song of Solomon': 'Sol', 'Song': 'Sol', 'Isaiah': 'Isa',
    'Jeremiah': 'Jer', 'Lamentations': 'Lam', 'Ezekiel': 'Eze',
    'Daniel': 'Dan', 'Hosea': 'Hos', 'Joel': 'Joe', 'Amos': 'Amo',
    'Obadiah': 'Oba', 'Jonah': 'Jon', 'Micah': 'Mic', 'Nahum': 'Nah',
    'Habakkuk': 'Hab', 'Zephaniah': 'Zep', 'Haggai': 'Hag',
    'Zechariah': 'Zec', 'Malachi': 'Mal',
}

# TVTMS book codes -> Swete CSV book codes. NOTE: TVTMS uses its own
# abbreviations (Exo/Deu/Jos/Jdg/Psa/Sng/Ezk/Jol/Nam...), NOT OSIS codes.
# Verified against the expanded section of the TVTMS file.
TVTMS_TO_SWETE = {
    'Gen': 'Gen', 'Exo': 'Exo', 'Lev': 'Lev', 'Num': 'Num', 'Deu': 'Deu',
    'Jos': 'Jos', 'Jdg': 'Jdg', 'Rut': 'Rut', '1Sa': '1Sa', '2Sa': '2Sa',
    '1Ki': '1Ki', '2Ki': '2Ki', '1Ch': '1Ch', '2Ch': '2Ch', 'Ezr': 'Ezr',
    'Neh': 'Neh', 'Est': 'Est', 'Job': 'Job', 'Psa': 'Psa', 'Pro': 'Pro',
    'Ecc': 'Ecc', 'Sng': 'Sol', 'Isa': 'Isa', 'Jer': 'Jer', 'Lam': 'Lam',
    'Ezk': 'Eze', 'Dan': 'Dan', 'Hos': 'Hos', 'Jol': 'Joe', 'Amo': 'Amo',
    'Oba': 'Oba', 'Jon': 'Jon', 'Mic': 'Mic', 'Nam': 'Nah', 'Hab': 'Hab',
    'Zep': 'Zep', 'Hag': 'Hag', 'Zec': 'Zec', 'Mal': 'Mal',
}
SWETE_TO_TVTMS = {v: k for k, v in TVTMS_TO_SWETE.items()}


def load_swete(words_path, verses_path):
    """Return {(book, chapter, verse): greek_text} from the Swete CSVs."""
    words = {}
    with open(words_path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2 and parts[0].isdigit():
                words[int(parts[0])] = parts[1]

    starts = []  # (word_id, book, chapter, verse)
    ref_re = re.compile(r'^(\w+)\.(\d+):(\d+)$')
    with open(verses_path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2 and parts[0].isdigit():
                m = ref_re.match(parts[1].strip())
                if m:
                    starts.append((int(parts[0]), m.group(1),
                                   int(m.group(2)), int(m.group(3))))

    # Swete's text-critical sigla (U+2E00-U+2E0F range) mean nothing in a
    # reading text; strip them and tidy the spacing that's left behind.
    sigla_re = re.compile('[⸀-⸏]')

    text = {}
    for i, (start, book, ch, vs) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else max(words) + 1
        verse_words = [words[w] for w in range(start, end) if w in words]
        verse = ' '.join(verse_words)
        verse = sigla_re.sub('', verse)
        verse = re.sub(r'\s+([,.·;:!?])', r'\1', re.sub(r'\s{2,}', ' ', verse)).strip()
        text[(book, ch, vs)] = verse
    return text


def parse_ref_list(refstring, default_book):
    """
    Parse a TVTMS reference like 'Gen.2:25', 'Gen.2:25-3:1', 'Gen.5:32; 6:1'
    into a list of (book, chapter, verse) tuples. Subverse markers (!a, .1,
    letters) are dropped. 'Title'/'0' verses are kept as verse 0.
    """
    out = []
    for part in refstring.split(';'):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'^(?:(\w+)\.)?(\d+):([\dA-Za-z!.]+)(?:-(?:(\w+)\.)?(\d+):([\dA-Za-z!.]+))?$',
                     part)
        if not m:
            # Things like 'Gen.31:55' with subverse '!a' attached, or odd forms
            m2 = re.match(r'^(?:(\w+)\.)?(\d+):(\d+)', part)
            if m2:
                book = m2.group(1) or default_book
                out.append((book, int(m2.group(2)), int(m2.group(3))))
            continue
        book1 = m.group(1) or default_book
        ch1 = int(m.group(2))
        vs1_m = re.match(r'\d+', m.group(3))
        if not vs1_m:
            continue
        vs1 = int(vs1_m.group(0))
        if m.group(5):  # range
            book2 = m.group(4) or book1
            ch2 = int(m.group(5))
            vs2_m = re.match(r'\d+', m.group(6))
            vs2 = int(vs2_m.group(0)) if vs2_m else vs1
            if book1 == book2 and ch1 == ch2:
                for v in range(vs1, vs2 + 1):
                    out.append((book1, ch1, v))
            else:
                # Cross-chapter range: expand conservatively (first and last
                # verse only; intermediate boundaries unknown without the text)
                out.append((book1, ch1, vs1))
                out.append((book2, ch2, vs2))
        else:
            out.append((book1, ch1, vs1))
    return out


def load_tvtms(tvtms_path, book_codes_needed):
    """
    Collect candidate mapping rules from the expanded section of TVTMS.
    Returns {standard (book,ch,vs): [(priority, [greek refs], tests_str)]}
    using rows whose SourceType involves the Greek tradition. Rules are
    validated later against the actual edition (Swete) via their tests.
    """
    candidates = {}

    def type_priority(source_type):
        # Higher wins. Plain Greek is the best match for printed editions.
        if source_type == 'Greek':
            return 3
        if source_type.startswith('Greek'):
            return 2
        return 1  # combined rows like Eng-KJV+Hebrew+Latin+Greek

    in_expanded = False
    with open(tvtms_path, encoding='utf-8') as f:
        for line in f:
            if '#DataStart(Expanded)' in line:
                in_expanded = True
                continue
            if not in_expanded:
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 4:
                continue
            source_type, source_ref, standard_ref = (
                parts[0].strip(), parts[1].strip(), parts[2].strip())
            if 'Greek' not in source_type:
                continue
            base_m = re.match(r'^(\w+)\.', source_ref)
            if not base_m:
                continue
            tv_book = base_m.group(1)
            if tv_book not in book_codes_needed:
                continue

            src_refs = parse_ref_list(source_ref, tv_book)
            std_refs = parse_ref_list(standard_ref, tv_book)
            if not src_refs or not std_refs:
                continue
            prio = type_priority(source_type)
            tests = parts[8].strip() if len(parts) > 8 else ''
            for std in std_refs:
                candidates.setdefault(std, []).append((prio, src_refs, tests))
    return candidates


def make_test_evaluator(swete):
    """
    Return a function that checks a TVTMS tests string (e.g.
    'Gen.36:44=Exist & Gen.37:1=Last') against the Swete verse inventory.
    Conditions we cannot evaluate (subverse refs, verse-length comparisons)
    are treated as passing, so they never veto a rule on their own.
    """
    last_verse = {}
    for (book, ch, vs) in swete:
        key = (book, ch)
        if vs > last_verse.get(key, 0):
            last_verse[key] = vs

    # Test refs are sometimes written in a different case than the data
    # rows (e.g. 'PSA.22:6=Last' vs 'Psa.22:1'), so look books up
    # case-insensitively.
    tvtms_upper = {k.upper(): v for k, v in TVTMS_TO_SWETE.items()}

    ref_re = re.compile(r'^(\w+)\.(\d+):(\d+)$')

    def evaluate(tests_str):
        if not tests_str:
            return True
        for cond in tests_str.split('&'):
            cond = cond.strip()
            m = re.match(r'^(\S+)=(Exist|NotExist|Last)$', cond)
            if not m:
                continue  # unevaluable condition type -> don't veto
            refstr, kind = m.group(1), m.group(2)
            rm = ref_re.match(refstr)
            if not rm:
                continue  # subverse like Gen.6:1.2 -> can't evaluate
            book, ch, vs = rm.group(1), int(rm.group(2)), int(rm.group(3))
            sw = (tvtms_upper.get(book.upper(), book), ch, vs)
            exists = sw in swete  # a numbered-but-empty slot still 'exists'
            if kind == 'Exist' and not exists:
                return False
            if kind == 'NotExist' and exists:
                return False
            if kind == 'Last':
                if last_verse.get((sw[0], ch)) != vs:
                    return False
        return True

    return evaluate


def main():
    ap = argparse.ArgumentParser(description='Fill LXX placeholders in a .tex file')
    ap.add_argument('texfile')
    here = Path(__file__).parent
    ap.add_argument('--swete-words', default=str(here / '01-Swete_word_with_punctuations.csv'))
    ap.add_argument('--swete-verses', default=str(here / '00-Swete_versification.csv'))
    ap.add_argument('--tvtms', default=None,
                    help='Path to the TVTMS txt file (default: auto-find TVTMS*.txt next to this script)')
    ap.add_argument('--out', default=None)
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    tex_path = Path(args.texfile)
    out_path = Path(args.out) if args.out else tex_path.with_name(tex_path.stem + '_lxx.tex')
    report_path = Path(args.report) if args.report else tex_path.with_name(tex_path.stem + '_lxx_report.txt')

    tvtms_path = args.tvtms
    if tvtms_path is None:
        candidates = sorted(here.glob('TVTMS*.txt'))
        if not candidates:
            sys.exit("Cannot find TVTMS*.txt next to the script; pass --tvtms PATH")
        tvtms_path = candidates[0]

    print("Loading Swete LXX ...")
    swete = load_swete(args.swete_words, args.swete_verses)
    print(f"  {len(swete)} verses loaded")

    # newline='' preserves the file's own line endings (CRLF or LF)
    with open(tex_path, encoding='utf-8', newline='') as f:
        lines = f.readlines()
    eol = '\r\n' if lines and lines[0].endswith('\r\n') else '\n'

    # Which books does this file quote? (needed to filter TVTMS)
    verse_head_re = re.compile(r'\\paragraph\{((?:\d\s)?[A-Za-z ]+?)\s+(\d+):(\d+)')
    books_in_file = set()
    for line in lines:
        m = verse_head_re.search(line)
        if m and m.group(1).strip() in BOOK_CODES:
            books_in_file.add(BOOK_CODES[m.group(1).strip()])
    tvtms_books = {SWETE_TO_TVTMS[b] for b in books_in_file if b in SWETE_TO_TVTMS}

    print(f"Books found in {tex_path.name}: {', '.join(sorted(books_in_file)) or '(none)'}")
    print("Loading TVTMS mapping ...")
    tvtms = load_tvtms(tvtms_path, tvtms_books)
    print(f"  {len(tvtms)} divergent verse mappings for these books")

    test_ok = make_test_evaluator(swete)

    def greek_for(book_code, ch, vs):
        """Return (greek_text, note) for a standard/KJV reference."""
        tv_book = SWETE_TO_TVTMS.get(book_code)
        std = (tv_book, ch, vs)

        empty_hits = []
        # Try TVTMS rules first (highest priority whose tests pass in Swete)
        for prio, src_refs, tests in sorted(tvtms.get(std, []),
                                            key=lambda c: -c[0]):
            if not test_ok(tests):
                continue
            texts, used, seen = [], [], set()
            for (gb, gch, gvs) in src_refs:
                sw = (TVTMS_TO_SWETE.get(gb, gb), gch, gvs)
                if sw in seen:
                    continue
                seen.add(sw)
                if sw in swete and swete[sw].strip():
                    texts.append(swete[sw])
                    used.append(f"{sw[0]}.{gch}:{gvs}")
            if texts:
                note = ''
                if used != [f"{book_code}.{ch}:{vs}"]:
                    note = 'LXX ' + '+'.join(used)
                return ' '.join(texts), note
            # rule passed its tests but its target slot(s) are empty
            empty_hits.extend(f"{TVTMS_TO_SWETE.get(gb, gb)}.{gch}:{gvs}"
                              for (gb, gch, gvs) in src_refs)

        # Fall back to identity
        sw = (book_code, ch, vs)
        if sw in swete:
            if swete[sw].strip():
                return swete[sw], ''
            return None, 'LXX omits this verse (empty in Swete)'
        if empty_hits:
            return None, ('maps to ' + '+'.join(dict.fromkeys(empty_hits)) +
                          ', but that slot is empty in Swete')
        return None, 'no LXX verse (absent from Swete, no mapping)'

    # Files use either "% \item[LXX] \gr{}" or "% % \item[LXX] \gr{}",
    # so allow one or more comment markers. Trailing \s* absorbs any \r.
    placeholder_re = re.compile(r'^(\s*)(?:%\s*)+\\item\[LXX\]\s*\\gr\{\}\s*$')
    filled_re = re.compile(r'\\item\[LXX\]\s*\\gr\{.+\}')

    current = None          # (display_ref, book_code, ch, vs)
    filled, skipped_filled, problems, caps_flags = [], [], [], []

    out_lines = []
    for line in lines:
        m = verse_head_re.search(line)
        if m and m.group(1).strip() in BOOK_CODES:
            book_name = m.group(1).strip()
            current = (f"{book_name} {m.group(2)}:{m.group(3)}",
                       BOOK_CODES[book_name], int(m.group(2)), int(m.group(3)))

        pm = placeholder_re.match(line)
        if pm and current:
            indent = pm.group(1)
            ref, code, ch, vs = current
            text, note = greek_for(code, ch, vs)
            if text:
                out_lines.append(f"{indent}\\item[LXX] \\gr{{{text}}}{eol}")
                filled.append((ref, note))
                first = text.split()[0] if text.split() else ''
                if len(first) > 1 and first.isupper():
                    caps_flags.append(ref)
                continue
            else:
                problems.append((ref, note))
        elif not is_comment(line) and filled_re.search(line) and current:
            skipped_filled.append(current[0])

        out_lines.append(line)

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(out_lines))

    # ----- report -----
    rep = []
    rep.append(f"fill_lxx report for {tex_path.name}")
    rep.append(f"Output written to: {out_path.name}")
    rep.append("")
    rep.append(f"Placeholders filled:        {len(filled)}")
    rep.append(f"Already filled (untouched): {len(skipped_filled)}")
    rep.append(f"Not fillable:               {len(problems)}")
    rep.append("")
    remapped = [(r, n) for r, n in filled if n]
    if remapped:
        rep.append("Filled via a versification remap (KJV ref -> different LXX ref);")
        rep.append("worth spot-checking these:")
        for r, n in remapped:
            rep.append(f"  {r}  <-  {n}")
        rep.append("")
    if caps_flags:
        rep.append("Filled but start with ALL-CAPS words (Swete's decorative opening")
        rep.append("capitals, printed without accents -- fix these by hand):")
        for r in caps_flags:
            rep.append(f"  {r}")
        rep.append("")
    if problems:
        rep.append("NOT filled (left as commented placeholders):")
        for r, n in problems:
            rep.append(f"  {r}: {n}")
        rep.append("")
    if skipped_filled:
        rep.append("Verses that already had LXX text (not modified):")
        for r in skipped_filled:
            rep.append(f"  {r}")

    report = '\n'.join(rep)
    Path(report_path).write_text(report + '\n', encoding='utf-8')
    print()
    print(report)


def is_comment(line):
    return line.lstrip().startswith('%')


if __name__ == '__main__':
    main()
