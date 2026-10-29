"""Further Norwegian acts, one corpus.d part each (corpus.d/60-<slug>.json), from the cache only (no network).

Each act is built exactly like personopplysningsloven and arveloven in parse.py (ordinary_act): the act as
promulgated in Norsk Lovtidend, then every amending law Lovtidend lists replayed in promulgation order, each change
dated by Lovdata's in-force note or the amending law's own in-force day. A part is written only when the replay
matches Lovdata's consolidated text in every unit; acts that do not are reported (parse_acts.log) and left out.
corpus.json is not touched.

    python -X utf8 parse_acts.py [slug ...]      # default: every act in ACTS
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parse as P  # noqa: E402
import lovdata as L  # noqa: E402
import replay as R  # noqa: E402

# (slug, short title, Lovtidend id of the act as promulgated). Acts promulgated since 2001 only: the open Lovtidend
# archive starts on 1 January 2001, so older acts have no promulgated text to replay from.
ACTS = [
    ('offentleglova', 'offl.', 'LOV-2006-05-19-16'),
    ('tvisteloven', 'tvl.', 'LOV-2005-06-17-90'),
    ('arbeidsmiljoloven', 'aml.', 'LOV-2005-06-17-62'),
    ('vergemalsloven', 'vergemålsl.', 'LOV-2010-03-26-9'),
    ('likestillings-og-diskrimineringsloven', 'ldl.', 'LOV-2017-06-16-51'),
    ('kommuneloven', 'koml.', 'LOV-2018-06-22-83'),
    ('hvitvaskingsloven', 'hvitvaskingsl.', 'LOV-2018-06-01-23'),
    ('sikkerhetsloven', 'sikkerhetsl.', 'LOV-2018-06-01-24'),
    ('andsverkloven', 'åndsverkl.', 'LOV-2018-06-15-40'),
    ('forbrukerkjopsloven', 'fkjl.', 'LOV-2002-06-21-34'),
    ('finansavtaleloven', 'finansavtalel.', 'LOV-2020-12-18-146'),
    ('skatteforvaltningsloven', 'sktfvl.', 'LOV-2016-05-27-14'),
    ('markedsforingsloven', 'mfl.', 'LOV-2009-01-09-2'),
    ('konkurranseloven', 'krrl.', 'LOV-2004-03-05-12'),
    ('angrerettloven', 'angrerettl.', 'LOV-2014-06-20-27'),
    ('statsborgerloven', 'statsborgerl.', 'LOV-2005-06-10-51'),
    ('plan-og-bygningsloven', 'pbl.', 'LOV-2008-06-27-71'),
    ('utlendingsloven', 'utl.', 'LOV-2008-05-15-35'),
    ('barnevernsloven', 'bvl.', 'LOV-2021-06-18-97'),
    ('opplaeringslova', 'opplæringslova', 'LOV-2023-06-09-30'),
    ('valgloven', 'vall.', 'LOV-2023-06-16-62'),
    ('eierseksjonsloven', 'esl.', 'LOV-2017-06-16-65'),
    ('burettslagslova', 'brl.', 'LOV-2003-06-06-39'),
    ('stiftelsesloven', 'stiftelsesl.', 'LOV-2001-06-15-59'),
    ('samvirkelova', 'samvirkelova', 'LOV-2007-06-29-81'),
    ('ehandelsloven', 'ehandelsl.', 'LOV-2003-05-23-35'),
    ('naturmangfoldloven', 'nml.', 'LOV-2009-06-19-100'),
    ('folkehelseloven', 'folkehelsel.', 'LOV-2011-06-24-29'),
    ('helse-og-omsorgstjenesteloven', 'hol.', 'LOV-2011-06-24-30'),
    ('pasientjournalloven', 'pasjournl.', 'LOV-2014-06-20-42'),
    ('politiregisterloven', 'politiregisterl.', 'LOV-2010-05-28-16'),
    ('straffegjennomforingsloven', 'strgjfl.', 'LOV-2001-05-18-21'),
    ('barnehageloven', 'bhl.', 'LOV-2005-06-17-64'),
    ('eiendomsmeglingsloven', 'emgl.', 'LOV-2007-06-29-73'),
    ('verdipapirhandelloven', 'vphl.', 'LOV-2007-06-29-75'),
    ('finansforetaksloven', 'finforetakslov.', 'LOV-2015-04-10-17'),
    ('tolloven', 'tollovenl.', 'LOV-2007-12-21-119'),
    ('matrikkellova', 'matrikkellova', 'LOV-2005-06-17-101'),
    ('dyrevelferdsloven', 'dyrevelferdsl.', 'LOV-2009-06-19-97'),
    ('havressurslova', 'havressurslova', 'LOV-2008-06-06-37'),
    ('mineralloven', 'minerall.', 'LOV-2009-06-19-101'),
    ('sosialtjenesteloven', 'sotjl.', 'LOV-2009-12-18-131'),
    ('nav-loven', 'nav-loven', 'LOV-2006-06-16-20'),
    ('arbeidsmarkedsloven', 'arbmrkl.', 'LOV-2004-12-10-76'),
    ('universitets-og-hoyskoleloven', 'uhl.', 'LOV-2024-03-08-9'),
    ('pengespilloven', 'pengespilll.', 'LOV-2022-06-24-82'),
    ('ekomloven', 'ekoml.', 'LOV-2024-12-13-76'),
]
LOGF = os.path.join(HERE, 'parse_acts.log')
EDITORIAL = re.compile(r'\[[a-zæøå]{1,3}\]')
INWORD_HYPHEN = re.compile(r'(?<=[a-zæøå])-(?=[a-zæøå])')


def ids(lid):
    y, mo, d, n = lid[4:].split('-')
    ref = 'lov/%s-%s-%s-%s' % (y, mo, d, n)
    gj = 'nl/nl-%s%s%s-%03d.xml' % (y, mo, d, int(n))
    target = r'(?i)\blov %d\. %s %s nr\. %d\b' % (int(d), P.MNAME[int(mo)], y, int(n))
    return ref, gj, target


def chapter_numbered(raw):
    """True for an act whose own sections are mostly numbered N-M (the consolidated text's article values)."""
    nums = re.findall(rb'legalArticleValue[^>]*>([^<]*)<', raw)
    chap = sum(1 for n in nums if re.search(rb'\d+\s*-\s*\d+', n))
    return bool(nums) and chap * 2 > len(nums)


def undo(x):
    """Every string in a part with the chapter-number tokens turned back into N-M (no-op when CHAPNUM is off)."""
    if isinstance(x, str):
        return L.dec(x)
    if isinstance(x, list):
        return [undo(v) for v in x]
    if isinstance(x, dict):
        return {k: undo(v) for k, v in x.items()}
    return x


def write_part(name, act, laws, pending, not_applied):
    lid = 'LOV-' + act['url'].rsplit('/', 1)[1]
    dec = ['%s: replayed from the act as promulgated (%s) through every amending law Norsk Lovtidend lists for it; '
           'the replay matches Lovdata\'s consolidated text (as of %s) in every unit (%d).' % (
               act['slug'], lid, P.gj_asof(), len(act['_official']))]
    dec += ['%s: %s is passed but not yet in force (Lovdata: "i kraft fra den tid Kongen bestemmer"); its changes '
            'are not in the history: %s.' % (act['slug'], P.lov_label(l), ', '.join(ks)) for s, l, ks in pending]
    dec += ['%s: amending instruction not applied by the replay (%s, %s): %s' % (act['slug'], l, why, src)
            for s, l, src, why in not_applied]
    dec += ['%s: %s %s' % (act['slug'], k, why) for k, why in act.get('_editorial', [])]
    for k in ('_official', '_final', '_skipped', '_mismatch', '_editorial'):
        act.pop(k, None)
    if L.CHAPNUM:
        dec.append('%s: its sections are numbered by chapter (§ 1-1); the replay reads every N-M number in the '
                   'amending instructions as a section number of that form (ranges are written "til").' % act['slug'])
    part = undo({'acts': [act], 'laws': dict(sorted(laws.items())), 'decisions': dec})
    d = os.path.join(HERE, 'corpus.d')
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name + '.json')
    with open(p + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(part, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(p + '.tmp', p)


def main():
    want = sys.argv[1:]
    L.REPEAL_PARTS = True  # whole-act repeal clauses are law text (see lovdata.walk_act)
    gj, idx = P.load()
    report = {}
    for slug, short, lid in ACTS:
        if want and slug not in want:
            continue
        ref, gjn, target = ids(lid)
        if lid not in idx or gjn not in gj:
            report[slug] = {'error': 'not in Lovtidend' if lid not in idx else 'not in gjeldende-lover (%s)' % gjn}
            continue
        laws = {}
        n_pend, n_na = len(P.PENDING), len(P.NOT_APPLIED)
        L.CHAPNUM = chapter_numbered(gj[gjn])
        try:
            act = P.ordinary_act(gj, idx, laws, slug, short, ref, gjn, lid, None, target)
        except (SystemExit, R.ReplayError, KeyError, ValueError, IndexError) as e:
            report[slug] = {'error': str(e)[:300], 'chapter_numbered': L.CHAPNUM}
            P.log('%s: stopped (%s)' % (slug, e))
            L.CHAPNUM = False
            continue
        mism = list(act['_mismatch'])
        # Lovdata's consolidated text (unofficial) inserts editorial letters in brackets into words the official
        # Lovtidend text misspells ("fast[s]att" where the law reads "fastatt"); the official wording is kept.
        editorial = []
        for k in list(mism):
            ours = (act['_final'].get(k) or {}).get('text')
            theirs = (act['_official'].get(k) or {}).get('text')
            if ours and theirs and EDITORIAL.sub('', theirs) == ours:
                editorial.append((k, 'has a letter that the consolidated text of Lovdata inserts in brackets (%s) and the '
                                     'official Lovtidend text does not have; the official wording is kept.'
                                  % ', '.join(EDITORIAL.findall(theirs))))
                mism.remove(k)
            elif (ours and theirs and 'Endringer i andre lover' in ours.splitlines()[0]
                  and theirs.startswith(ours)):
                # Lovdata's markup leaves an amendment payload for another act as a ledd of this paragraph; its
                # amendments to other acts are not kept here (only the opening words), as everywhere else
                editorial.append((k, '(amendments to other acts): the consolidated text of Lovdata prints an amendment '
                                     'for another act as a further ledd; here, as for every such paragraph, only the '
                                     'opening words are kept.'))
                mism.remove(k)
            elif ours and theirs and INWORD_HYPHEN.sub('', ours) == theirs:
                # the official text hyphenates a word ("student-representantene") that Lovdata writes joined
                editorial.append((k, 'is hyphenated in the official Lovtidend text (%s) where Lovdata writes the word '
                                     'joined; the official wording is kept.'
                                  % ', '.join(w for w in re.findall(r'\w+-\w+', ours)
                                              if w.replace('-', '') in theirs and w not in theirs)))
                mism.remove(k)
        act['_editorial'] = editorial
        report[slug] = {'versions': len(act['versions']), 'laws': len(laws), 'units': len(act['_official']),
                        'mismatches': len(mism), 'editorial': len(act['_editorial'])}
        report[slug]['chapter_numbered'] = L.CHAPNUM
        if not mism:
            write_part('60-' + slug, act, laws, P.PENDING[n_pend:], P.NOT_APPLIED[n_na:])
            report[slug]['written'] = True
        L.CHAPNUM = False
    with open(LOGF, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(P.LOG) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=1))
    with open(os.path.join(HERE, '.tmp-acts-report.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
