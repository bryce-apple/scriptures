# How the LXX text got into this document

Written August 2026, so that later readers (including future me) know where
the Greek came from, how it was placed, and how much to trust it.

## The text

The `\item[LXX]` lines in the Old Testament files contain the text of the
**Rahlfs-Hanhart Septuaginta** (Editio altera, Deutsche Bibelgesellschaft,
2006), taken from my own PDF copy of that edition. The text was extracted
book by book (copy-paste of the PDF text layer into .txt files), parsed
into a verse-indexed JSON file (`rahlfs.json`, kept locally, not in the
repository since the edition is copyrighted), and inserted into the .tex
files by script. A verse reading `\gr{---}` means the Rahlfs edition has
no verse at that location (the LXX genuinely lacks it).

## Versification

My document is organized by KJV verse numbers; the LXX numbers many
passages differently (the Psalms are off by roughly one psalm, Jeremiah is
substantially reordered, Exodus and other books shift within chapters).
Verses were aligned **by content**: each KJV verse received the Greek verse
that corresponds to it in meaning, even when the LXX numbers it
differently. The correspondence table used is **TVTMS** (Tyndale
Versification Traditions Mapping System, STEPBible.org, CC BY), whose
edition tests were evaluated against the Rahlfs text itself so that the
rules matching this specific edition's conventions were the ones applied.
Every verse filled from a different-numbered Greek verse is listed in that
book's `*_report.txt` under "filled from a remapped reference."

Where TVTMS could only offer a loose nearest-verse correspondence (one
Greek verse covering several KJV verses, as in the Exodus tabernacle
chapters), the repeated fills are flagged in the report and were mostly
replaced by `---`, since the LXX has no true counterpart there.

## Verification performed

1. **Round-trip check** (`check_lxx.py`): every inserted verse was
   re-derived independently from the JSON and compared; disagreements
   reported worst-first.
2. **Shift detector**: independent of the mapping, each verse was compared
   against its numerical neighbors in the JSON; chapters where several
   verses matched a neighbor better than their assigned verse were flagged
   as possible off-by-one errors.
3. **Deep audit** (`check_lxx.py --deep`): for every verse that did not
   match its assigned text well, the whole book was searched for where
   that Greek text actually occurs, reconstructing the mapping from the
   text itself with no reliance on TVTMS. Run on the hard books
   (Psalms, Jeremiah, Exodus, Job).
4. **Per-book review reports** (`*_report.txt`): omitted verses, remapped
   references, duplicate-source fills, and overwritten lines were listed
   for hand review against the printed edition.

## The pipeline (for re-running or adding books)

Files needed in one folder: `parse_rahlfs.py`, `plan_rahlfs.py`,
`apply_rahlfs.py`, `check_lxx.py`, `fill_lxx.py` (shared library),
`TVTMS*.txt` (from STEPBible), `rahlfs.json` (grows with each book).

```
python3 parse_rahlfs.py <book>.txt                # paste from PDF -> JSON
python3 plan_rahlfs.py <file>.tex rahlfs.json     # reviewable plan
python3 apply_rahlfs.py <file>.tex <file>_plan.tsv rahlfs.json
python3 check_lxx.py <file>_rahlfs.tex rahlfs.json --deep
```

Review `<file>_report.txt` and `<file>_rahlfs_check.txt`, then rename the
`_rahlfs.tex` output over the original.

## Known limitations

- Book-opening verses and a few others were checked by hand; see the
  reports archived in `lxx_reports/` (Swete run) and per-book reports.
- Daniel (Rahlfs prints Old Greek AND Theodotion), Esther (lettered
  additions A:1-F:11), and Nehemiah (= Rahlfs 2 Esdras 11-23) need
  special handling in the parser; done separately when those books were
  processed.
- The `µ`-for-`μ` (micro sign) font artifact of the PDF text layer is
  normalized by the parser; hand-pasted verses from before the pipeline
  may still contain it.

## A note suitable for the document itself

> The Greek text of the Old Testament quotations follows the
> Rahlfs-Hanhart *Septuaginta* (2006). Verses are aligned to the KJV
> numbering by content, following the versification correspondences of
> the Tyndale Versification Traditions Mapping System; a dash (---)
> marks places where the Septuagint has no corresponding verse.
