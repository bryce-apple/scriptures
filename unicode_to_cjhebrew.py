#!/usr/bin/env python3
"""
Convert Unicode Hebrew (with nikud) to cjhebrew input encoding.

Usage:
    python3 unicode_to_cjhebrew.py "בְּרֵאשִׁית"
    echo "שָׁלֹום" | python3 unicode_to_cjhebrew.py

Output is ready to paste into \\he{} or \\heb{} in your LaTeX files.
"""

import sys

# ---------------------------------------------------------------------------
# Consonant table (cjhebrew manual, Table 1)
# Final forms use uppercase variants.
# Shin (ש) is handled separately based on the following dot character.
# ---------------------------------------------------------------------------
CONSONANTS = {
    'א': "'",   # א  ALEPH
    'ב': 'b',   # ב  BET
    'ג': 'g',   # ג  GIMEL
    'ד': 'd',   # ד  DALET
    'ה': 'h',   # ה  HE
    'ו': 'w',   # ו  VAV
    'ז': 'z',   # ז  ZAYIN
    'ח': '.h',  # ח  HET
    'ט': '.t',  # ט  TET
    'י': 'y',   # י  YOD
    'ך': 'K',   # ך  FINAL KAF
    'כ': 'k',   # כ  KAF
    'ל': 'l',   # ל  LAMED
    'ם': 'M',   # ם  FINAL MEM
    'מ': 'm',   # מ  MEM
    'ן': 'N',   # ן  FINAL NUN
    'נ': 'n',   # נ  NUN
    'ס': 's',   # ס  SAMEKH
    'ע': '`',   # ע  AYIN
    'ף': 'P',   # ף  FINAL PE
    'פ': 'p',   # פ  PE
    'ץ': '.S',  # ץ  FINAL TSADI
    'צ': '.s',  # צ  TSADI
    'ק': 'q',   # ק  QOF
    'ר': 'r',   # ר  RESH
    'ש': None,  # ש  SHIN/SIN — resolved by dot below
    'ת': 't',   # ת  TAV
}

# Vowel points → cjhebrew suffix (appended after the consonant code)
VOWELS = {
    'ְ': ':',   # ְ  SHEWA
    'ֱ': 'E:',  # ֱ  HATAF SEGOL
    'ֲ': 'a:',  # ֲ  HATAF PATAH
    'ֳ': 'A:',  # ֳ  HATAF QAMATS
    'ִ': 'i',   # ִ  HIRIQ
    'ֵ': 'e',   # ֵ  TSERE
    'ֶ': 'E',   # ֶ  SEGOL
    'ַ': 'a',   # ַ  PATAH  (use /a for furtive patah if needed)
    'ָ': 'A',   # ָ  QAMATS
    'ֹ': 'o',   # ֹ  HOLAM  (upgraded to O for holam male, see below)
    'ֺ': 'o',   # ֺ  HOLAM HASER FOR VAV
    'ֻ': 'u',   # ֻ  QUBUTS
    'ּ': '*',   # ּ  DAGESH / MAPPIQ
}

# Combining characters that are silently ignored
_CANTILLATION = set(chr(cp) for cp in range(0x0591, 0x05B0))  # U+0591-U+05AF
_IGNORE = _CANTILLATION | {
    'ֽ',  # ֽ  METEG
    'ֿ',  # ֿ  RAFE
    '׀',  # ׀  PASEQ
    '׃',  # ׃  SOF PASUQ
    'ׄ',  # ׄ  UPPER DOT
    'ׅ',  # ׅ  LOWER DOT
    '׆',  # ׆  NUN HAFUKHA
    'ׇ',  # ׇ  QAMATS QATAN
    '‌',  # ZWNJ
    '‍',  # ZWJ
}

_SHIN_DOT = 'ׁ'  # ׁ shin dot (right)
_SIN_DOT  = 'ׂ'  # ׂ sin dot (left)
_DAGESH   = 'ּ'
_MAQQEF   = '־'  # ־

# Characters that are diacritics (not standalone consonants)
def _is_diacritic(c):
    return (c in VOWELS or c in _IGNORE or
            c in {_SHIN_DOT, _SIN_DOT} or
            ('֑' <= c <= 'ׇ' and c != _MAQQEF))


def convert(text):
    """Return the cjhebrew encoding of a Unicode Hebrew string."""
    out = []
    chars = list(text)
    n = len(chars)
    i = 0

    while i < n:
        c = chars[i]

        # --- Punctuation / whitespace ---
        if c == ' ':
            out.append(' ')
            i += 1
            continue

        if c == _MAQQEF:
            out.append('--')
            i += 1
            continue

        if c in _IGNORE:
            i += 1
            continue

        # --- Consonant ---
        if c in CONSONANTS:
            i += 1

            # Collect all following diacritics
            diacs = []
            while i < n and _is_diacritic(chars[i]):
                diacs.append(chars[i])
                i += 1

            # Resolve shin/sin
            if c == 'ש':
                if _SHIN_DOT in diacs:
                    code = '+s'
                    diacs = [d for d in diacs if d != _SHIN_DOT]
                elif _SIN_DOT in diacs:
                    code = ',s'
                    diacs = [d for d in diacs if d != _SIN_DOT]
                else:
                    code = '/s'
            else:
                code = CONSONANTS[c]

            has_dagesh = _DAGESH in diacs
            vowel_chars = [d for d in diacs if d in VOWELS and d != _DAGESH]

            # Shureq: vav + dagesh with no other vowel → U
            if c == 'ו' and has_dagesh and not vowel_chars:
                out.append('U')
                continue

            # Holam male: consonant + holam, followed by bare vav
            has_holam = any(d in {'ֹ', 'ֺ'} for d in vowel_chars)
            holam_male = False
            if has_holam:
                # Peek ahead: is the next consonant a bare vav (mater lectionis)?
                j = i
                while j < n and chars[j] in _IGNORE:
                    j += 1
                if j < n and chars[j] == 'ו':
                    # Collect diacritics of that vav
                    k = j + 1
                    vav_diacs = []
                    while k < n and _is_diacritic(chars[k]):
                        vav_diacs.append(chars[k])
                        k += 1
                    # It's a mater lectionis if the vav carries no vowel and no dagesh
                    vav_vowels = [d for d in vav_diacs if d in VOWELS and d != _DAGESH]
                    vav_dagesh = _DAGESH in vav_diacs
                    if not vav_vowels and not vav_dagesh:
                        holam_male = True
                        i = k  # consume the vav and its diacritics

            # Build cjhebrew token: code + dagesh(*) + vowel
            token = code
            if has_dagesh:
                token += '*'
            for d in vowel_chars:
                if d in {'ֹ', 'ֺ'}:
                    token += 'O' if holam_male else 'o'
                else:
                    token += VOWELS[d]

            out.append(token)

        else:
            # Non-Hebrew character (e.g. punctuation) — pass through
            out.append(c)
            i += 1

    return ''.join(out)


def main():
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        if sys.stdin.isatty():
            print("Paste Hebrew text and press Enter:")
        text = sys.stdin.read().strip()

    if not text:
        print("No input.", file=sys.stderr)
        sys.exit(1)

    print(convert(text))


if __name__ == '__main__':
    main()
