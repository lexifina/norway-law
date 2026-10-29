# How this repository was made (Norway)

This file is written by the build on 2026-10-29, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| Norsk Lovtidend avd. I (Lovdata public data) | <https://api.lovdata.no/publicData> | 2026-10-29 | NLOD 2.0 |
| Gjeldende lover (Lovdata public data) | <https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2> | 2026-10-29 | NLOD 2.0 |
| Lovdata API description and data set list | <https://api.lovdata.no/swagger/api.json> | 2026-10-29 | NLOD 2.0 |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `grunnloven` | Kongeriket Norges Grunnlov | 16 | 2014-05-06 to 2024-05-21 |
| `grunnlova` | Kongeriket Noregs grunnlov | 16 | 2014-05-06 to 2024-05-21 |
| `personopplysningsloven` | Lov om behandling av personopplysninger (personopplysningsloven) | 3 | 2018-07-20 to 2022-01-01 |
| `arveloven` | Lov om arv og dødsboskifte (arveloven) | 7 | 2021-01-01 to 2023-10-01 |
| `ehandelsloven` | Lov om visse sider av elektronisk handel og andre informasjonssamfunnstjenester (ehandelsloven). | 7 | 2003-07-01 to 2023-10-01 |
| `ekomloven` | Lov om elektronisk kommunikasjon (ekomloven) | 3 | 2025-01-01 to 2026-07-01 |
| `universitets-og-hoyskoleloven` | Lov om universiteter og høyskoler (universitets- og høyskoleloven) | 5 | 2024-08-01 to 2026-08-01 |
| `valgloven` | Lov om valg til Stortinget, fylkesting og kommunestyrer (valgloven) | 3 | 2024-05-01 to 2028-01-01 |

The build made 45 commits:

| Commits | Kind |
| ---: | --- |
| 8 | first version of an act |
| 37 | one law on its in-force day |
| 0 | changes no amendment note explains, credited to the publisher |

Other counts:
- 1 commits on the branch `fremtidig`: laws not yet in force on 2026-10-29.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 44 laws in the record.
- 94 tags.

## Dates

Each commit is dated at noon (Europe/Oslo) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: Norway has no single default commencement rule in this record: each in-force day is the one Lovdata records for the official Norsk Lovtidend document ("I kraft fra"; for a decision amending the Constitution, the day of Stortinget's decision), and where a law leaves commencement to the King ("Kongen bestemmer"), the day Lovdata's amendment note gives for that provision ("ikr. ... iflg. res. ..."). https://api.lovdata.no/xmldocs

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `8f0a6e60bdd9fa642372cbf93a5f7afdc81b50ad7d696c351924e5b79a644c0d` (922417 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `a4faa25af85facb64b956b372f6b528aafdd7ec1`, `check.py` `3d00541d258745461ab52b1b0cb4e1716a27a95d`, `on.py` `644a6c0857fbcc72562032b58d57aa113fee0641`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

60 versions of 8 acts read back from git on the day each took effect and on the day before: 0 mismatches. Trailers: 0 commits whose trailers git cannot parse. Health: 0 merge commits on main, 0 commit dates that go backwards, 0 commits dated after the build.

A second build from the same corpus into an empty folder gave identical hashes for all 44 history commits and 94 tags (history tip `bcd9afade94dfcaed4d3bf34587453f6a4843469`).

## Decisions made by hand

- Text comes only from Norsk Lovtidend avd. I, the official announcement of Norwegian law; Lovdata's consolidated text (unofficial) is used only to check the replay and for in-force days of provisions whose law left commencement to the King.
- Grunnloven and Grunnlova are two acts: since 6 May 2014 the Constitution has official bokmål and nynorsk texts of equal standing, and every amendment is announced in both.
- Grunnloven starts on 2014-05-06 with the full text of the language revision announced by res. 9 May 2014 no. 613, as corrected by Lovdata on 2014-05-30 (bokmål §§ 2, 6, 53, 63, 92, 112). Earlier wording is in the old language and the full text before 2014 is not in the open archive, so this is the oldest version available (first_law null).
- The decision of 13 May 2014 (res. 14 May 2014 no. 628) moved provisions to a new chapter F "with a new paragraph number" it did not give. The 13 May version therefore uses the numbering and text of chapters E and F in the edited version Stortinget adopted on 27 May 2014 (res. 20 June 2014 no. 778), and the 27 May commit changes no words.
- Amendment instructions are applied by code: ledd and punktum being replaced or repealed count the text as it read before; "nytt" ledd and punktum name the new position; list letters are addressed by letter. An instruction the code cannot read stops the build.
- Grunnloven: amendments of 2014-2024 are dated by Stortinget's decision, the "I kraft fra" day Lovdata gives each announcement.
- Repealed paragraphs are removed files; the editorial "(Opphevet ved ...)" lines Lovdata prints are not law text and are left out.
- Chapter headings are units of their own (kapittel-*.md).
- List items are written "a) text", in one form for both sources (Lovtidend prints "a)", the consolidated text "a.").
- Number ranges are written with a hyphen (§§ 77-79): Lovdata prints an en dash in some texts and a hyphen in others.
- personopplysningsloven § 34 (Endringer i andre lover) keeps only its opening sentence, as in Lovdata's consolidated text: the amendments it made live on in the acts they amended.
- personopplysningsloven: the annexed Norwegian text of the GDPR (EEA version), which § 1 makes law, is not included; only the act's own chapters 1-9 are.
- personopplysningsloven: both amending laws left commencement to the King; each change is dated by the in-force day in Lovdata's note for the provision (2018-12-20 for § 12 a, 2022-01-01 for § 3), which matches the commencement resolutions FOR-2018-12-20-2093 and FOR-2021-06-18-1967.
- Ordinary acts: the amending laws are every law Lovtidend's metadata ("Endrer") lists as changing the act, replayed in promulgation order; no law Lovdata's notes name is missing from them.
- A change Lovdata's note gives no in-force day for took effect with the amending law itself: it is dated by the first day in that law's "I kraft fra" field, and never before the act itself took effect (arveloven: amendments of 18 December 2020 to the act that took effect on 1 January 2021 are same-day versions on that day).
- A change Lovdata marks "Endres ved lov ... (i kraft fra den tid Kongen bestemmer)" has no in-force day yet, so it is not in the history: arveloven § 103 and § 178 (lov 19. juni 2026 nr. 48).
- Word substitutions ("I følgende bestemmelser skal «fylkesmannen» endres til «statsforvalteren»") are applied to the paragraphs and ledd they name, in lower and capitalised form; inflected forms that contain the word (fylkesmannens) change with it.
- Lovdata's editorial mark ": – – –" after "gjøres følgende endringer i andre lover" is not compared.
- sha256 of a version is the sha256 of the single Lovtidend XML document (the tar member named after # in source_url) it was parsed from.
- ehandelsloven: replayed from the act as promulgated (LOV-2003-05-23-35) through every amending law Norsk Lovtidend lists for it; the replay matches Lovdata's consolidated text (as of 2026-10-21) in every unit (22).
- ehandelsloven: paragraf-006 has a letter that the consolidated text of Lovdata inserts in brackets ([s]) and the official Lovtidend text does not have; the official wording is kept.
- ekomloven: replayed from the act as promulgated (LOV-2024-12-13-76) through every amending law Norsk Lovtidend lists for it; the replay matches Lovdata's consolidated text (as of 2026-10-21) in every unit (168).
- ekomloven: its sections are numbered by chapter (§ 1-1); the replay reads every N-M number in the amending instructions as a section number of that form (ranges are written "til").
- universitets-og-hoyskoleloven: replayed from the act as promulgated (LOV-2024-03-08-9) through every amending law Norsk Lovtidend lists for it; the replay matches Lovdata's consolidated text (as of 2026-10-21) in every unit (139).
- universitets-og-hoyskoleloven: amending instruction not applied by the replay (LOV-2024-05-31-26, not read): instruction not read: cannot read instruction: I lov 8. mars 2024 nr. 9 om universiteter og høyskoler § 17-4 nr. 3 skal fagskoleloven § 4 b tredje og nytt fjerde ledd lyde:
- universitets-og-hoyskoleloven: paragraf-16-004 is hyphenated in the official Lovtidend text (student-representantene) where Lovdata writes the word joined; the official wording is kept.
- universitets-og-hoyskoleloven: its sections are numbered by chapter (§ 1-1); the replay reads every N-M number in the amending instructions as a section number of that form (ranges are written "til").
- valgloven: replayed from the act as promulgated (LOV-2023-06-16-62) through every amending law Norsk Lovtidend lists for it; the replay matches Lovdata's consolidated text (as of 2026-10-21) in every unit (170).
- valgloven: paragraf-22-002 (amendments to other acts): the consolidated text of Lovdata prints an amendment for another act as a further ledd; here, as for every such paragraph, only the opening words are kept.
- valgloven: its sections are numbered by chapter (§ 1-1); the replay reads every N-M number in the amending instructions as a section number of that form (ranges are written "til").

## What AI did and did not do

The scripts that read the sources and build this repository were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote Lexifina's code and read sample documents to design it. No model wrote, edited or summarised legal text, and no model runs at data-build or git-build time.
