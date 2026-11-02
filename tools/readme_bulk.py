"""Bring repo/README.md and repo/jurisdiction.json up to date with the current-text parts (corpus.d/70-lover-*,
80-forskrifter-*) of a folder. Idempotent: the sentences it owns are rewritten from the parts' own counts.

    python -X utf8 readme_bulk.py <folder>
"""
import glob
import json
import os
import re
import sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))


def count(pat):
    n, first, last = 0, None, None
    for f in sorted(glob.glob(os.path.join(D, 'corpus.d', pat))):
        for a in json.load(open(f, encoding='utf-8'))['acts']:
            n += 1
            d = a['versions'][0]['from']
            first = min(first or d, d)
            last = max(last or d, d)
    return n, first, last


laws, _, _ = count('70-lover-*.json')
regs, _, _ = count('80-forskrifter-*.json')
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November',
          'December']


def survey(pat):
    """(acts per data set day, single-file act slugs, in-force-in-part count) of a set's parts."""
    days, single, part = {}, [], 0
    for f in sorted(glob.glob(os.path.join(D, 'corpus.d', pat))):
        d = json.load(open(f, encoding='utf-8'))
        m = re.search(r'(?:as of|as retrieved on) (\d{4}-\d{2}-\d{2})', d['decisions'][0])
        days[m.group(1)] = days.get(m.group(1), 0) + len(d['acts'])
        for a in d['acts']:
            if list(a['versions'][0]['units']) == ['tekst']:
                single.append(a['slug'])
            if '; Lovdata gives the rest as' in a['versions'][0]['note']:
                part += 1
    return days, single, part


def day_words(days, noun):
    ds = sorted(days)
    words = ['%d %s %s' % (int(x[8:]), MONTHS[int(x[5:7]) - 1], x[:4]) for x in ds]
    if len(ds) == 1:
        return ' of ' + words[0]
    parts = ['%s (%d %s)' % (w, days[x], noun) for w, x in zip(words, ds)]
    return 's of ' + ', '.join(parts[:-1]) + ' and ' + parts[-1]


ldays, lsingle, lpart = survey('70-lover-*.json')
rdays, rsingle, rpart = survey('80-forskrifter-*.json')
single = len(lsingle) + len(rsingle)
p = os.path.join(D, 'repo', 'README.md')
s = open(p, encoding='utf-8').read()

CUR = ('**Acts with their current text only.** Beside the acts above, `lov-…`-named and short-titled folders hold %d '
       'further laws, and `for-…` folders %d central regulations (sentrale forskrifter), each as one version: the text '
       'in force today in Lovdata\'s consolidation (unofficial), credited to Lovdata as the oldest version available '
       'and dated by the day Lovdata gives for the last change in force (or, for one never changed, its own in-force '
       'day). They have no history yet. Laws: the `gjeldende-lover` data set%s; regulations: the '
       '`gjeldende-sentrale-forskrifter` data set%s. Each is split into its paragraphs (§) or articles '
       '("Art.") and headings as the document numbers them, except %d **single-file acts** (%d laws, %d regulations): '
       'documents with no numbered articles, such as amending acts and short acts of a few unnumbered ledd, each '
       'recorded as one file, `tekst.md`, holding its whole text (listed below). %d acts in force only in part are '
       'dated by the first in-force day Lovdata gives. Not included: laws and regulations not yet in force or whose '
       'last change takes effect later, regulations whose in-force day Lovdata gives only as a year ("Inntektsåret '
       '2014"), the delegation decisions and instructions in the regulations data set, and local regulations.' % (
           laws, regs, day_words(ldays, 'laws'), day_words(rdays, 'regulations'), single, len(lsingle), len(rsingle),
           lpart + rpart))
LIST = ('<details><summary>Single-file acts (%d)</summary>\n\n%s\n\n</details>'
        % (single, ', '.join('`%s`' % x for x in lsingle + rsingle)))
if '**Acts with their current text only.**' in s:
    s = re.sub(r'\*\*Acts with their current text only\.\*\*[^\n]*', lambda m: CUR, s)
    if '<details><summary>Single-file acts' in s:
        s = re.sub(r'<details><summary>Single-file acts.*?</details>', lambda m: LIST, s, flags=re.S)
    elif single:
        s = s.replace(CUR, CUR + '\n\n' + LIST, 1)
else:
    a = 'Every version is built from the official announcement in **Norsk Lovtidend**.'
    assert s.count(a) == 1
    s = s.replace(a, 'Every version of the acts in the table is built from the official announcement in **Norsk '
                     'Lovtidend**.')
    s = s.replace('\n\n## How it is checked', '\n\n' + CUR + '\n\n## How it is checked', 1)

CHK = ('- **Current-text acts.** Each law and regulation recorded with its current text only has exactly the '
       'paragraphs the consolidated document itself lists (repealed "(Opphevet)" articles and paragraphs not yet in '
       'force apart); one that does not, or whose last change takes effect after the data set\'s day, is left out. '
       'Paragraphs of amendments to other acts that Lovdata prints as "– – –" keep their title only, as in the acts '
       'above. Annexes without numbered paragraphs (such as an annexed EU regulation) are not included; the record\'s '
       'decisions list them. A document whose paragraphs this reading does not list is read article by article '
       'instead, or recorded as a single-file act, and its words, in order, equal the document\'s own text '
       '(Lovdata\'s editorial notes, footnotes and repealed "(Opphevet)" articles apart; images in a few regulations '
       'are not included).')
if '- **Current-text acts.**' in s:
    s = re.sub(r'- \*\*Current-text acts\.\*\*[^\n]*', lambda m: CHK, s)
else:
    a = '- **Replay, not copying.**'
    assert s.count(a) == 1
    s = s.replace(a, CHK + '\n' + a, 1)

AUT = ('- **Acts with their current text only** are one commit each, "oldest version available", credited to Lovdata '
       '(`gjeldende-lover@lovdata.invalid`, `gjeldende-forskrifter@lovdata.invalid`) as the publisher of the '
       'consolidated text.')
if '- **Acts with their current text only** are one commit' in s:
    s = re.sub(r'- \*\*Acts with their current text only\*\* are one commit[^\n]*', lambda m: AUT, s)
else:
    a = '- Blame credits whole lines'
    assert s.count(a) == 1
    s = s.replace(a, AUT + '\n' + a, 1)

old_row = ('| [Gjeldende lover](https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2), Lovdata public data | '
           'Unofficial consolidation | current text only | yes, a note per provision with the in-force day | yes | Used '
           'to check the replay and for in-force days; no text taken from it |')
new_row = ('| [Gjeldende lover](https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2), Lovdata public data | '
           'Unofficial consolidation | current text only | yes, a note per provision with the in-force day | yes | Used '
           'to check the replay and for in-force days; the text of the laws recorded with their current text only |\n'
           '| [Gjeldende sentrale forskrifter](https://api.lovdata.no/v1/publicData/get/gjeldende-sentrale-forskrifter.tar.bz2), '
           'Lovdata public data | Unofficial consolidation | current text only | yes | yes | The text of the central '
           'regulations recorded with their current text only |')
if old_row in s:
    s = s.replace(old_row, new_row)

NO = ('- Gjeldende tekst: %d andre lover og %d sentrale forskrifter er tatt med slik de lyder i dag i Lovdatas '
      'ajourførte (uoffisielle) tekst, én versjon hver, uten historikk ennå%s.' % (
          laws, regs, ('; %d av dem er én fil med hele teksten (dokumenter uten nummererte paragrafer eller artikler)'
                       % single) if single else ''))
if '- Gjeldende tekst:' in s:
    s = re.sub(r'- Gjeldende tekst:[^\n]*', lambda m: NO, s)
else:
    a = '- Inneholder data under norsk lisens'
    assert s.count(a) == 1
    s = s.replace(a, NO + '\n' + a, 1)
open(p, 'w', encoding='utf-8', newline='\n').write(s)

j = os.path.join(D, 'repo', 'jurisdiction.json')
jd = json.load(open(j, encoding='utf-8'))
b = re.sub(r'; current text only: .*$', '', jd['build'])
jd['build'] = b + '; current text only: %d laws and %d central regulations (Lovdata consolidation%s)' % (
    laws, regs, ', %d of them single-file' % single if single else '')
open(j, 'w', encoding='utf-8', newline='\n').write(json.dumps(jd, ensure_ascii=False, indent=2) + '\n')
print('laws', laws, 'regulations', regs)
