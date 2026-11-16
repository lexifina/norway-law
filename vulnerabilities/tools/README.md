# Tools

The scripts behind this Norway-only run of global-law's vulnerability detectors. They run inside a copy of
[global-law/vulnerabilities/scripts](https://github.com/lexifina/global-law/tree/main/vulnerabilities/scripts) (Python 3.11+,
`pip install duckdb pyarrow`), with a bare clone of this repository at `sources/corpus/norway-law.git`, a blobless bare
clone of global-law at `sources/global-law.git`, and a `pins.json` that names only norway-law, its commit, its language
(`nb`) and its code (`NO`). `build_vulns.py`, `flags_chart.py`, `late_ext_select.py`, `late_ext_rebut.py` and
`config.json` sit three folders up, next to the copy of global-law (`gl/vulnerabilities/scripts/`).

| Script | What it does |
| --- | --- |
| `run.sh` | Indexes the history and texts, maps paths to act folders since a move (`map_moved.py`), adds this repository's history rows, and runs the detectors (`bash run.sh <shards>`) |
| `add_root.py` | Builds the history rows from this repository's own commits, so the history detectors read every change; it counts `Kind: law` and `Kind: publisher` (the first text of an act held with its current text only) as law, and was not changed for this repository |
| `run_triage.sh` | The model review: the 40 strongest flags per category, the 40 strongest lapsed time limits in law texts, and the empty periods |
| `late_ext_select.py` | Chooses the empty periods for global-law's review of that category (there were none here) |
| `late_ext_rebut.py` | Adds the second, arguing-against pass to the empty-period review, as `triage.py` does for the other categories |
| `build_vulns.py` | Builds `data/flags.csv`, `data/reviewed.csv` and `data/by_category.csv` from the findings and the model review |
| `flags_chart.py` | Draws the chart at the top of the READMEs, in Norwegian and English, light and dark |
| `config.json` | The repository, the Norwegian category names, the files and folders that are not law (with `README.md`, each act's list of provisions), and the chart's labels |
| `patch_detectors.py` | Fixes blind spots found in runs on several country repositories in the copy of global-law's scripts (`python -X utf8 patch_detectors.py <scripts dir>`; a fix already in place is skipped) |
| `patch_nb.py` | The Norwegian fixes, written for this run (below) |
| `patch_detectors_vi.py`, `patch_es.py`, `patch_ca.py`, `patch_en.py`, `patch_de.py`, `patch_en_et.py`, `patch_co.py`, `patch_sv.py`, `patch_pt.py`, `patch_ru.py`, `patch_r18.py`, `patch_xk.py`, `patch_mo.py`, `patch_lu.py`, `patch_li.py`, `patch_mx.py`, `patch_mn.py`, `patch_mt.py`, `patch_np.py`, `patch_en_nr.py`, `patch_dv.py`, `patch_az.py` | The same for other languages and repositories (found by other runs); `apply_patches.py` runs them on every repository, and they change nothing in Norwegian text |
| `apply_patches.py` | Runs the patches above once each, in a fixed order (`patch_nb.py` last), and records them in the scripts folder (`.kit_patches.json`) |
| `map_moved.py` | For a repository that moved its act folders (`data/paths.json`), rewrites the paths in the history table to each act's folder since the move; this repository has not moved its folders, so it does nothing here |
| `redo.py` | Runs the patches, then again only the scans and detectors the fixes change, the model review of lapsed time limits, references to deleted provisions and empty periods, and the build (`python -X utf8 redo.py <run folder> [--keep-reviews] [--full]`; `--keep-reviews` keeps every review already made and reviews only new strong flags; `--full` runs every step again through `run.sh`, sends every category to the model and keeps every review already made; `EMBED_FONTS` names the script that embeds the chart's fonts) |

The model review needs `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_AUTH` set for an OpenAI-compatible Responses API.
`run_triage.sh` was given `^(data|tools)/|(^|/)README\.md$|^(REPRODUCE\.md|LICENSE|jurisdiction\.json)$` as the files that
are not law; no flag is in them, so the 40 strongest lapsed time limits in law texts are the 40 strongest of all.

The detectors carried every patch above when they were run. Changes made for this repository, all in `patch_nb.py`, each
read only for a corpus whose language is `nb`, `nn` or `no`:

- `ingest/textscan.py`: the search for time limits read only "frem til" and "til og med" among the Norwegian words for
  "until". It now also reads "til 31. desember 2020", "inntil 1. mars 2018", "fram til 31. desember 2012" and the end of
  a year, "frem til utgangen av 2027" (31 December). "innen" (by) and "senest" (at the latest) are deadlines and stay
  unread, as the other languages' deadlines are. Lapsed time limits went from 241 to 617.
- `ingest/refscan.py`: Norwegian acts number their sections by chapter ("§ 14-9", "§ 1a-1", "§ 4-1 a") and write an
  inserted section with a space ("§ 6 a"). A reference "§ 14-9" was read as § 14, a heading "§ 4-1 a." gave the key 4, and
  the file names (`paragraf-14-009.md`, `paragraf-01-a-001.md`, `paragraf-04-001-a.md`) gave none, so a repealed § 14-12
  would never be missed while § 14-1 stood. The key is now "14-9", "1a-1", "4-1a" or "6a" in references (lists too:
  "§§ 22-6 og 22-7"), headings and file names; "§§ 291-296", after two section marks, also gives §§ 291 to 296, which only
  a plainly numbered act has. "62 §" (the Swedish order) is no longer read: in "lov 17. juni 2005 nr. 62 § 7" it was read
  as § 62. Another act named before the section ("barnelova § 3", "lov 17. juni 2005 nr. 62 § 7",
  "byggesaksforskriften § 5") or after it ("§ 3 første ledd i lov om ...", "§ 5 i folketrygdloven") is not the act's own.
  References to deleted provisions stayed at 2.
- `detectors/dup_labels.py`: "§ 3-1" and "§ 3-2" at the start of two lines were read as two units "§ 3", and an amending
  act's instructions ("§ 10 annet ledd skal lyde:", "§ 10 fjerde ledd skal lyde:") as two units "§ 10". Duplicate
  numbering went from 159 to 29.

Not changed, and stated in the READMEs: nothing reads "innen" (by) or "senest" (at the latest) as a time limit.
