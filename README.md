# Norway: law history in git

The law of Norway as a git history: one file per provision, one commit per decision or law on the day it took effect, and the decision or law that made each change as the commit's author. `git blame` names the decision behind every paragraph; `git log` lists every change to a paragraph; picking a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `no/`.

**What is in it now**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `grunnloven/` | Kongeriket Norges Grunnlov (the Constitution, bokmål) | 16 | From the language revision of 6 May 2014 to today, through every amendment Stortinget has decided since (the latest of 21 May 2024) |
| `grunnlova/` | Kongeriket Noregs grunnlov (the Constitution, nynorsk) | 16 | The same, in the nynorsk text, which has had equal standing since 6 May 2014 |
| `personopplysningsloven/` | Lov om behandling av personopplysninger (the Personal Data Act, 2018) | 3 | As enacted (in force 20 July 2018) to today |
| `arveloven/` | Lov om arv og dødsboskifte (the Succession Act, 2019) | 7 | As enacted (in force 1 January 2021) to today, through five amending laws |
| `ehandelsloven/` | Lov om visse sider av elektronisk handel og andre informasjonssamfunnstjenester (the E-Commerce Act, 2003) | 7 | As enacted (in force 1 July 2003) to today, through six amending laws |
| `ekomloven/` | Lov om elektronisk kommunikasjon (the Electronic Communications Act, 2024) | 3 | As enacted (in force 1 January 2025) to today, through three amending laws |
| `universitets-og-hoyskoleloven/` | Lov om universiteter og høyskoler (the Universities and University Colleges Act, 2024) | 5 | As enacted (in force 1 August 2024) to today, through five amending laws |
| `valgloven/` | Lov om valg til Stortinget, fylkesting og kommunestyrer (the Election Act, 2023) | 3 | As enacted (in force 1 May 2024) to today; one change already passed takes effect on 1 January 2028 (branch `fremtidig`) |

Every version is built from the official announcement in **Norsk Lovtidend**. Norway publishes no official consolidated texts: Lovtidend is the only official source of Norwegian law, and the up-to-date texts most people read are Lovdata's unofficial consolidations. This repository replays the official announcements one by one and then checks the result against Lovdata's consolidation (see *How it is checked*). The per-act `README.md` in each folder lists every provision, how often it changed and when.

## A lawyer's questions as git commands

| Question | Command |
| --- | --- |
| What did Grunnloven § 63 say on 31 May 2022? | `python tools/gjeldende.py 2022-05-31 grunnloven 63` |
| The same, with raw git (bash) | `git show $(git rev-list -1 --before="2022-05-31T23:59:59Z" main -- grunnloven/paragraf-063.md):grunnloven/paragraf-063.md` |
| The same, in PowerShell | `$r = git rev-list -1 --before="2022-05-31T23:59:59Z" main -- grunnloven/paragraf-063.md; git show "$($r):grunnloven/paragraf-063.md"` |
| The nynorsk text of the same paragraph | `python tools/gjeldende.py 2022-05-31 grunnlova 63` |
| Which decision wrote each ledd of § 49? | `git blame grunnloven/paragraf-049.md` |
| Every change to § 89, word by word | `git log -p --word-diff grunnloven/paragraf-089.md` |
| Every decision and law in the record, in order | `git log --reverse --format="%ad %an" --date=short main` |
| Everything one decision changed | `git show law/for-2022-06-22-1133` (tags `law/<key>` mark each commit; the key is the Lovtidend id) |
| The whole act on a date | `python tools/gjeldende.py 2019-01-01 personopplysningsloven` |
| The act on a version's in-force day | `git show grunnloven/2018-05-08` (tags `<act>/<in-force day>`) |

After a rebuild, refresh tags with `git fetch --force --tags`: a plain fetch keeps stale tags.

## Dates

- Each commit is dated at **noon, Europe/Oslo, on the day the change took effect** (the in-force date). The decision or enactment date and the announcement date are trailers, and the in-force day is in `In-force:`, which the tools read.
- **Amendments to the Constitution** are decided by Stortinget under Grunnloven § 121 and then announced by royal resolution in Lovtidend. Each commit is dated on the day of Stortinget's decision, which is the "I kraft fra" day Lovdata records for every announcement in this record. Four decisions of 14 May 2020 are four commits on the same day, in the order of their announcement numbers (1085 to 1088).
- **Ordinary laws** usually leave commencement to the King ("Loven gjelder fra den tid Kongen bestemmer"). The day used is the one Lovdata's amendment note gives for the provision ("ikr. 1 jan 2022 iflg. res. 18 juni 2021 nr. 1967"), which names the commencement resolution, itself in Lovtidend. Where the note gives no day, the change took effect with the amending law itself: the first day in its "I kraft fra" field.
- **Changes made before an act took effect** take effect with it. Arveloven was amended on 18 December 2020, before it took effect on 1 January 2021; those changes are a second commit on 1 January 2021, after the act as enacted.
- **A law that splits its commencement** is one commit per day: lov 18. desember 2020 nr. 149 changed six paragraphs of arveloven from 1 January 2021 and added § 99 a from 1 January 2022.
- **13 and 27 May 2014.** The human-rights amendments of 13 May 2014 moved several paragraphs to a new chapter F "with a new paragraph number" without giving the number; Stortinget adopted the numbered, edited text of chapters E and F on 27 May 2014. The 13 May commit uses that numbered text; the 27 May commit records the edited version and changes no words.
- `--before="YYYY-MM-DD"` alone uses your clock's time of day, so a change that took effect that day may be missed before noon. Use `T23:59:59Z` as above, or the tool.

## How it is checked

- **Against today's text.** After replaying every announcement, the result is compared provision by provision with Lovdata's consolidated text of the same act (the `gjeldende-lover` data set, last modified 2026-10-21). All eight acts match exactly: Grunnloven and Grunnlova in all 116 units each, personopplysningsloven in all 44, arveloven in all 221, ehandelsloven in all 22, ekomloven in all 168, universitets- og høyskoleloven in all 139 and valgloven in all 170. Three places differ only editorially and keep the official Lovtidend wording: ehandelsloven § 6 ("fastatt", where Lovdata inserts "fast[s]att"), universitets- og høyskoleloven § 16-4 ("student-representantene", which Lovdata writes joined), and valgloven § 22-2, a paragraph of amendments to other acts, where Lovdata prints one amendment as a further ledd and this record keeps only the opening words, as for every such paragraph.
- **Replay, not copying.** The amendment instructions in each announcement ("§ 5 første punktum skal lyde:", "§ 63 første ledd ny bokstav c skal lyde:", "§ 101 tredje ledd oppheves.", "I følgende bestemmelser skal «fylkesmannen» endres til «statsforvalteren»") are applied by code to the text before it. An instruction the code cannot read stops the build; none is skipped in these four acts.
- **Every amending law is accounted for.** The amending laws are those Lovtidend's metadata lists for the act; Lexifina's code also checks every law Lovdata's notes name and logs any provision a named law should have changed but did not.
- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`. Results are in `REPRODUCE.md`.
- Health checks: no merge commits on `main`, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse with `git interpret-trailers --parse`.
- The repository is rebuilt from the same data a second time and must give identical hashes.

## What "author" means

The author of a commit is the decision or law that made the change, with an e-mail address that cannot exist (`for-2022-06-22-1133@lovdata.invalid`), so `git blame` and `git log --author` name them. The key is the Lovtidend identifier of the announcement (FOR-… for a constitutional decision announced by royal resolution, LOV-… for a law). The committer is always Lexifina.

- **Credits come only from the source.** A provision is credited to the announcement whose instructions changed it. No change in this record is unexplained.
- **The first commit of Grunnloven and Grunnlova** is "oldest version available", credited to the publisher: it is the full text of the language revision of 6 May 2014, not the Constitution of 17 May 1814.
- Blame credits whole lines (one ledd or list item per line). In a paragraph written by several decisions, use `git log -p --word-diff` to see exactly which words each one changed.

## What it does not show

- **The Constitution before 6 May 2014.** The 2014 revision rewrote every paragraph in modern bokmål and added an official nynorsk text. Lovtidend's open data starts in 2001 and holds the amendments of 2003-2012, but not a full text of the Constitution in the older language to apply them to, so the history starts with the revision.
- **The GDPR text annexed to personopplysningsloven.** § 1 makes the EEA version of the General Data Protection Regulation Norwegian law; Lovdata prints its Norwegian text after the act. Only the act's own chapters 1 to 9 are here.
- **The amendments personopplysningsloven § 34 made to other acts** in 2018: as in Lovdata's consolidation, § 34 keeps only its opening sentence, and those amendments belong to the acts they amended.
- **Changes passed but not yet in force.** Lov 19. juni 2026 nr. 48 (rekonstruksjonsforhandling) amends arveloven § 103 and § 178 "from the time the King decides", and no day has been set; Lovdata marks them "Endres ved". They are not in the history until a commencement day exists.
- **Straffeloven (2005).** The Penal Code's history is being built the same way (the act as promulgated in 2005 and more than 80 amending laws, most of them before it took effect on 1 October 2015), but its replay does not yet match today's text in every provision, so it is not published here.
- **Repealed paragraphs** are removed files. Lovdata's editorial "(Opphevet ved …)" lines and its amendment notes are not law text and are not in the files.
- **Court rulings.** Norwegian courts can set aside a statute in a case (Grunnloven § 89), but that strikes no words, so it is not in this record.

## How it is built

Lexifina reads the sources listed here and records each act's dated versions, and the laws that made each change, in one corpus file. `tools/build.py` writes this repository from that file, and the same corpus always gives the same commit hashes; `REPRODUCE.md` gives the details and the checks. A model (Claude) wrote Lexifina's code; it wrote no legal text, and no model runs when the history is built.

No AI model wrote or changed legal text. Claude Opus 5.5 wrote the scripts and chose the sources; see `REPRODUCE.md`.

## Sources

| Source | Kind | Past versions | Names the amending act | Bulk | Notes |
| --- | --- | --- | --- | --- | --- |
| [Norsk Lovtidend avd. I](https://api.lovdata.no/publicData), Lovdata public data | Official gazette | every announcement since 1 January 2001 | it is the amending text | yes, two tar archives (2001-2025, 2026) | Used: the text of every version |
| [Gjeldende lover](https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2), Lovdata public data | Unofficial consolidation | current text only | yes, a note per provision with the in-force day | yes | Used to check the replay and for in-force days; no text taken from it |
| [Lovdata](https://lovdata.no) | Official publisher's site | Lovdata Pro (paid) has historical versions | yes | no | Not read |
| [sondreskarsten/norwegian-laws](https://github.com/sondreskarsten/norwegian-laws) | Volunteer git repo (MIT), snapshots of the Lovdata API | from its own snapshots | partly | n/a | Prior art; not read, no text copied |

Research guides that cover every country: [GlobaLex](https://www.nyulawglobal.org/globalex/) and the [Law Library of Congress Guide to Law Online](https://www.loc.gov/research-centers/law-library-of-congress/researcher-resources/guide-to-law-online/).

## Licence

Norwegian laws and decisions of public authorities are not protected by copyright: "Lover, forskrifter, rettsavgjørelser og andre vedtak av offentlig myndighet er uten vern etter denne loven" (åndsverkloven, lov 15. juni 2018 nr. 40, § 14). Lovdata releases its public data sets under the Norwegian Licence for Open Government Data, NLOD 2.0 (https://data.norge.no/nlod/no/2.0): *Contains data under the Norwegian licence for Open Government data (NLOD) distributed by Lovdata.* The arrangement, tables, commit messages and tools are by Lexifina, under the terms in `LICENSE`.

This repository is not legal advice and not an official publication.

## På norsk

Norsk lovhistorie i git: én fil per paragraf og én commit per grunnlovsvedtak eller lov, datert den dagen endringen trådte i kraft og signert av vedtaket eller loven som gjorde endringen (`git blame` viser hvilket vedtak som skrev hvert ledd). Inneholder Grunnloven på bokmål (`grunnloven/`) og nynorsk (`grunnlova/`) fra språkrevisjonen 6. mai 2014 og alle senere grunnlovsvedtak, personopplysningsloven fra 2018 og arveloven fra 2021.

- Teksten på en dato: `python tools/gjeldende.py 2022-05-31 grunnloven 63`
- Kilde: Norsk Lovtidend avd. I (Lovdatas åpne data), den eneste offisielle kilden. Hver kunngjøring er anvendt på teksten før den, og resultatet er kontrollert mot Lovdatas ajourførte tekst: alle fire lovene stemmer helt.
- Datoer: Grunnlovsendringer er datert på Stortingets vedtaksdag; lover på ikrafttredelsesdagen Lovdata oppgir for bestemmelsen.
- Inneholder data under norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Lovdata. Ingen KI-modell har skrevet lovtekst.
