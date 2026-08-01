#!/usr/bin/env python3
"""
Generates gospel_appendices_greek_hebrew_index.tex automatically.

Scans concept files for \subparagraph{\texorpdfstring{\gr/he{word}}{}} entries
and scripture files for footnote-embedded word studies (label + BDAG reference).
Run this script before compiling gospel.tex whenever new word studies are added.

Usage:
    python3 generate_greek_hebrew_index.py
"""

import re
import unicodedata
import glob
from pathlib import Path

DIR = Path(__file__).parent
OUTPUT = DIR / 'gospel_appendices_greek_hebrew_index.tex'


def is_active(line):
    return not line.lstrip().startswith('%')


def clean_name(s):
    """Strip LaTeX commands and trailing alternatives for display."""
    s = re.sub(r'\\footnote\{[^{}]*\}', '', s)
    s = re.sub(r'\\[a-zA-Z]+\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    s = s.split(',')[0]  # "Atonement, Atone" -> "Atonement"
    return s.strip()


def greek_sort_key(word):
    """Sort Greek alphabetically by base letters, ignoring diacritics."""
    nfd = unicodedata.normalize('NFD', word.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def parse_concept_files():
    """
    Find word studies in concept files.
    Pattern: active \subparagraph{\texorpdfstring{\gr/he{word}}{}}
             followed within 5 lines by \label{WORDLABEL}
    Context: the \section{} + \label{} at the top of the file.
    """
    greek = []
    hebrew = []

    for filepath in sorted(DIR.glob('gospel_concepts_*.tex')):
        lines = open(filepath, encoding='utf-8').readlines()

        ctx_name = None
        ctx_label = None
        waiting_for_label = False
        pending_name = None

        for i, line in enumerate(lines):
            if not is_active(line):
                continue

            # Track \section and \subsection as potential context.
            # \subsection labels are used only when they have no hyphen —
            # hyphenated labels (e.g. ATONEMENT-OT) are sub-topics, not concepts.
            m = re.search(r'\\section\{([^}]+)\}', line)
            if m:
                pending_name = clean_name(m.group(1))
                waiting_for_label = True
                continue

            m = re.search(r'\\subsection\{([^}]+)\}', line)
            if m:
                pending_name = clean_name(m.group(1))
                waiting_for_label = True
                continue

            # Capture the label that follows a heading
            if waiting_for_label:
                m = re.search(r'\\label\{([^}]+)\}', line)
                if m:
                    label = m.group(1)
                    # Only use as context if the label has no hyphen
                    # (hyphened labels are sub-topic labels, not concept labels)
                    if '-' not in label:
                        ctx_name = pending_name
                        ctx_label = label
                    waiting_for_label = False
                    continue

            # Shorthand so the rest of the loop still uses these names
            section_name = ctx_name
            section_label = ctx_label

            # Detect active word-study heading at any level:
            # \subparagraph, \paragraph, or \subsubsection with \texorpdfstring{\gr/he{}}
            m = re.match(
                r'\s*\\(?:subparagraph|paragraph|subsubsection)\{\\texorpdfstring\{\\(gr[l]?|he[l]?)\{([^}]+)\}\}',
                line
            )
            if not m:
                continue

            lang_cmd = m.group(1)   # gr, grl, he, hel
            word = m.group(2)

            # Find the \label within the next 5 active lines
            word_label = None
            for j in range(i + 1, min(i + 6, len(lines))):
                if not is_active(lines[j]):
                    continue
                lm = re.search(r'\\label\{([^}]+)\}', lines[j])
                if lm:
                    word_label = lm.group(1)
                    break

            if word_label and section_label:
                entry = dict(
                    word=word,
                    word_label=word_label,
                    ctx_label=section_label,
                    ctx_name=section_name,
                )
                if lang_cmd.startswith('gr'):
                    greek.append(entry)
                else:
                    hebrew.append(entry)

    return greek, hebrew


def parse_scripture_files():
    """
    Find word studies embedded in scripture footnotes.
    Pattern: \label{WORDLABEL} followed (within 4 lines) by
             \gr{word} or \he{word} and a BDAG/lexical reference.
    Context: the nearest preceding \paragraph{} or \subsubsection{} with its \label{}.
    Also scans gospel_temple_endowment*.tex using the same logic.
    """
    greek = []
    hebrew = []

    files = sorted(DIR.glob('gospel_scriptures_*.tex')) + sorted(DIR.glob('gospel_temple_endowment*.tex'))

    for filepath in files:
        lines = open(filepath, encoding='utf-8').readlines()

        ctx_name = None
        ctx_label = None
        verse_heading_just_seen = False
        in_versebox = 0

        for i, line in enumerate(lines):
            if not is_active(line):
                continue

            # Track versebox depth so we ignore inline Greek inside verse boxes
            in_versebox += line.count('\\begin{versebox}') - line.count('\\end{versebox}')

            # Track nearest verse heading (\paragraph or \subsubsection) for context
            m = re.search(r'\\(?:paragraph|subsubsection)\{([^}]+)\}', line)
            if m:
                ctx_name = clean_name(m.group(1))
                verse_heading_just_seen = True

            lm = re.search(r'\\label\{([^}]+)\}', line)
            if lm:
                label = lm.group(1)

                # Only update ctx_label when this label belongs to a verse heading
                if verse_heading_just_seen:
                    ctx_label = label
                    verse_heading_just_seen = False

                elif in_versebox <= 0:
                    # Check the next 4 lines for Greek/Hebrew + lexical reference
                    window_lines = lines[i:min(i + 5, len(lines))]
                    window = ''.join(window_lines)

                    has_lexicon = bool(re.search(
                        r'BDAG|CGL|BDB|HALOT|TDNT|Liddell|LSJ\b', window
                    ))

                    gr_m = re.search(r'\\gr[l]?\{([^}]+)\}', window)
                    he_m = re.search(r'\\he[l]?\{([^}]+)\}', window)

                    if has_lexicon and ctx_label:
                        if gr_m:
                            word = gr_m.group(1)
                            if not any(e['word_label'] == label for e in greek):
                                greek.append(dict(
                                    word=word,
                                    word_label=label,
                                    ctx_label=ctx_label,
                                    ctx_name=ctx_name,
                                ))
                        elif he_m:
                            word = he_m.group(1)
                            if not any(e['word_label'] == label for e in hebrew):
                                hebrew.append(dict(
                                    word=word,
                                    word_label=label,
                                    ctx_label=ctx_label,
                                    ctx_name=ctx_name,
                                ))

    return greek, hebrew


def format_entry(e, is_greek):
    word_cmd = 'grl' if is_greek else 'hel'
    return (
        f"\t\t\\item \\hyperref[{e['word_label']}]"
        f"{{\\{word_cmd}{{{e['word']}}}}}, "
        f"in \\hyperref[{e['ctx_label']}]{{{e['ctx_name']}}}\n"
    )


# Entries that the automatic scanner cannot reach:
#  - Verse-level labels whose word study sits many lines below (HELEL, HEOSPHOROS)
#  - Labels whose word + lexicon appear more than 4 lines below the \label{} (KATARTIZO)
MANUAL_EXTRAS = {
    'greek': [
        dict(word='ἑωσφόρος', word_label='HEOSPHOROS',
             ctx_label='ISAIAH-14-12', ctx_name='Isaiah 14:12'),
        dict(word='καταρτίζω', word_label='KATARTIZO',
             ctx_label='2NEPHI-9-23', ctx_name='2 Nephi 9:23'),
    ],
    'hebrew': [
        dict(word='heylel', word_label='HELEL',
             ctx_label='ISAIAH-14-12', ctx_name='Isaiah 14:12'),
    ],
}


def generate():
    print("Scanning concept files...")
    gr_concepts, he_concepts = parse_concept_files()
    print(f"  Found {len(gr_concepts)} Greek, {len(he_concepts)} Hebrew entries")

    print("Scanning scripture files...")
    gr_scripture, he_scripture = parse_scripture_files()
    print(f"  Found {len(gr_scripture)} Greek, {len(he_scripture)} Hebrew entries")

    greek = gr_concepts + gr_scripture + MANUAL_EXTRAS['greek']
    hebrew = he_concepts + he_scripture + MANUAL_EXTRAS['hebrew']

    # Sort: Greek by base letters (diacritics stripped), Hebrew by raw input
    greek.sort(key=lambda e: greek_sort_key(e['word']))
    hebrew.sort(key=lambda e: e['word'].lower())

    # Remove duplicates (same word_label appearing twice)
    seen = set()
    greek = [e for e in greek if not (e['word_label'] in seen or seen.add(e['word_label']))]
    seen = set()
    hebrew = [e for e in hebrew if not (e['word_label'] in seen or seen.add(e['word_label']))]

    lines = []
    lines.append("% AUTO-GENERATED by generate_greek_hebrew_index.py -- do not edit manually.\n")
    lines.append("% Run this script before compiling whenever new word studies are added.\n")
    lines.append("\n")

    lines.append("% -----------------------------------------------------------\n")
    lines.append("\\section{Hebrew Index}\n")
    lines.append("% -----------------------------------------------------------\n")
    lines.append("\t\\label{HEBREWINDEX}\n")
    lines.append("\t\n")
    lines.append("\t\\begin{enumerate}\n")
    lines.append("\t\n")
    for e in hebrew:
        lines.append(format_entry(e, is_greek=False))
        lines.append("\t\n")
    lines.append("\t\\end{enumerate}\n")
    lines.append("\t\n")

    lines.append("% -----------------------------------------------------------\n")
    lines.append("\\section{Greek Index}\n")
    lines.append("% -----------------------------------------------------------\n")
    lines.append("\t\\label{GREEKINDEX}\n")
    lines.append("\t\n")
    lines.append("\t\\begin{enumerate}\n")
    lines.append("\t\n")
    for e in greek:
        lines.append(format_entry(e, is_greek=True))
        lines.append("\t\n")
    lines.append("\t\\end{enumerate}\n")

    OUTPUT.write_text(''.join(lines), encoding='utf-8')
    print(f"\nWrote {OUTPUT}")
    print(f"  Hebrew entries: {len(hebrew)}")
    print(f"  Greek entries:  {len(greek)}")


if __name__ == '__main__':
    generate()
