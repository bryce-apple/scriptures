#!/usr/bin/env python3
"""
parse_rahlfs.py -- Turn raw text copied from the Rahlfs-Hanhart Septuaginta
PDF into a verse-per-entry JSON file.

Feed it one or more .txt files (each containing one book, or several books --
book headers like GENESIS in Greek capitals mark the boundaries) and it
writes rahlfs.json:

    { "Gen": { "1": { "1": "Ἐν ἀρχῇ ἐποίησεν ...", "2": "..." } } }

It handles the PDF artifacts seen in copied text:
  - page footers ("Text from: Septuaginta", copyright lines, page numbers)
  - line wraps inside verses
  - verse numbers glued to the following word (2ἡ δὲ γῆ)
  - standalone chapter numbers at paragraph starts
  - the em-dash paragraph marks of the edition
  - micro sign U+00B5 in place of Greek mu (font artifact)

Usage:
    python3 parse_rahlfs.py genesis.txt [exodus.txt ...] -o rahlfs.json
    python3 parse_rahlfs.py --check rahlfs.json    (show a summary)
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Greek book headers as printed in the edition -> short codes (Swete-style,
# same codes fill_lxx.py uses). Add entries as you feed in more books.
BOOK_HEADERS = {
    'ΓΕΝΕΣΙΣ': 'Gen', 'ΕΞΟΔΟΣ': 'Exo', 'ΛΕΥΙΤΙΚΟΝ': 'Lev',
    'ΑΡΙΘΜΟΙ': 'Num', 'ΔΕΥΤΕΡΟΝΟΜΙΟΝ': 'Deu', 'ΙΗΣΟΥΣ': 'Jos',
    'ΚΡΙΤΑΙ': 'Jdg', 'ΡΟΥΘ': 'Rut',
    'ΒΑΣΙΛΕΙΩΝ Α': '1Sa', 'ΒΑΣΙΛΕΙΩΝ Β': '2Sa',
    'ΒΑΣΙΛΕΙΩΝ Γ': '1Ki', 'ΒΑΣΙΛΕΙΩΝ Δ': '2Ki',
    'ΠΑΡΑΛΕΙΠΟΜΕΝΩΝ Α': '1Ch', 'ΠΑΡΑΛΕΙΠΟΜΕΝΩΝ Β': '2Ch',
    'ΕΣΔΡΑΣ Β': 'Ezr',  # Rahlfs 2 Esdras = Ezra-Nehemiah
    'ΕΣΘΗΡ': 'Est', 'ΙΩΒ': 'Job', 'ΨΑΛΜΟΙ': 'Psa',
    'ΠΑΡΟΙΜΙΑΙ': 'Pro', 'ΕΚΚΛΗΣΙΑΣΤΗΣ': 'Ecc', 'ΑΣΜΑ': 'Sol',
    'ΗΣΑΙΑΣ': 'Isa', 'ΙΕΡΕΜΙΑΣ': 'Jer', 'ΘΡΗΝΟΙ': 'Lam',
    'ΙΕΖΕΚΙΗΛ': 'Eze', 'ΔΑΝΙΗΛ': 'Dan',
    'ΩΣΗΕ': 'Hos', 'ΙΩΗΛ': 'Joe', 'ΑΜΩΣ': 'Amo', 'ΑΒΔΙΟΥ': 'Oba',
    'ΙΩΝΑΣ': 'Jon', 'ΜΙΧΑΙΑΣ': 'Mic', 'ΝΑΟΥΜ': 'Nah',
    'ΑΜΒΑΚΟΥΜ': 'Hab', 'ΣΟΦΟΝΙΑΣ': 'Zep', 'ΑΓΓΑΙΟΣ': 'Hag',
    'ΖΑΧΑΡΙΑΣ': 'Zec', 'ΜΑΛΑΧΙΑΣ': 'Mal',
}

FOOTER_RE = re.compile(
    r'^\s*(Text from: Septuaginta'
    r'|©.*Deutsche Bibelgesellschaft.*'
    r'|All rights reserved'
    r'|www\.\S+'
    r'|\d{1,4})\s*$'
)

GREEK_LETTER = r'Ͱ-Ͽἀ-῿'


def normalize(text):
    """Fix PDF font artifacts and tidy whitespace."""
    text = text.replace('µ', 'μ')          # micro sign -> Greek mu
    text = text.replace('—', ' ')          # edition's paragraph dashes
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def strip_diacritics_upper(s):
    nfd = unicodedata.normalize('NFD', s)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').upper()


def match_book_header(line):
    """Return a book code if the line is a book-title header."""
    key = strip_diacritics_upper(normalize(line))
    key = re.sub(r'\s+', ' ', key).strip()
    return BOOK_HEADERS.get(key)


def parse_files(paths):
    data = {}
    book = None
    chapter = None
    verse = None
    buf = []
    warnings = []

    def flush():
        nonlocal buf
        if book and chapter and verse and buf:
            text = normalize(' '.join(buf))
            data.setdefault(book, {}).setdefault(str(chapter), {})
            existing = data[book][str(chapter)].get(str(verse))
            if existing:
                warnings.append(f"duplicate {book} {chapter}:{verse} -- keeping first")
            else:
                data[book][str(chapter)][str(verse)] = text
        buf = []

    # A verse marker is digits glued to a Greek letter; a chapter marker is a
    # standalone number token. Both only make sense inside a known book.
    token_re = re.compile(
        rf'(\d+)(?=[{GREEK_LETTER}])'   # verse number stuck to a word
        rf'|(?<!\S)(\d+)(?!\S)'         # standalone chapter number
    )

    for path in paths:
        for raw in open(path, encoding='utf-8'):
            line = raw.rstrip('\n')
            if not line.strip():
                continue
            if FOOTER_RE.match(line):
                continue
            hb = match_book_header(line)
            if hb:
                flush()
                book, chapter, verse = hb, None, None
                continue
            if book is None:
                continue

            pos = 0
            for m in token_re.finditer(line):
                # text before this marker belongs to the current verse
                before = line[pos:m.start()]
                if before.strip():
                    buf.append(before)
                pos = m.end()
                if m.group(1) is not None:      # verse marker
                    flush()
                    verse = int(m.group(1))
                    if verse == 1 and chapter is None:
                        chapter = 1
                else:                            # standalone chapter number
                    flush()
                    chapter = int(m.group(2))
                    verse = None
            tail = line[pos:]
            if tail.strip():
                buf.append(tail)
    flush()
    return data, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('txtfiles', nargs='*')
    ap.add_argument('-o', '--output', default='rahlfs.json')
    ap.add_argument('--check', metavar='JSON',
                    help='print a summary of an existing JSON instead of parsing')
    args = ap.parse_args()

    if args.check:
        data = json.load(open(args.check, encoding='utf-8'))
        for book, chapters in data.items():
            n = sum(len(v) for v in chapters.values())
            print(f"{book}: {len(chapters)} chapters, {n} verses")
        return

    if not args.txtfiles:
        sys.exit("Give me at least one .txt file (raw text copied from the PDF)")

    out_path = Path(args.output)
    if out_path.exists():
        data = json.load(open(out_path, encoding='utf-8'))
        print(f"Extending existing {out_path}")
    else:
        data = {}

    new_data, warnings = parse_files(args.txtfiles)
    for book, chapters in new_data.items():
        data.setdefault(book, {})
        for ch, verses in chapters.items():
            data[book].setdefault(ch, {}).update(verses)

    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                        encoding='utf-8')

    for w in warnings:
        print("WARNING:", w)
    for book, chapters in new_data.items():
        n = sum(len(v) for v in chapters.values())
        print(f"Parsed {book}: {len(chapters)} chapters, {n} verses")
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main()
