"""Acts recorded with their current text only: every law in Lovdata's consolidated data set (gjeldende-lover) that
this record does not build from Norsk Lovtidend.

    python -X utf8 bulk.py [--size 60] [--only LID,...] [--out DIR]

Norway has no official consolidations: Norsk Lovtidend is the only official source, and for acts promulgated before
2001 it holds no full text. For those acts, and for acts whose amendment history is not yet replayed, the record
gives the text in force today as Lovdata's consolidated (unofficial) text, as one version credited to Lovdata as the
oldest version available (first_law null). That version is dated by the day Lovdata gives for the last change in
force ("lastChangeInForce"), or, for an act never changed, its own in-force day ("dateInForce").

Each act is checked before it is written:
- its paragraphs equal the consolidated document's own list of articles, read from the raw markup (repealed
  "(Opphevet)" articles and "Tilføyes ..." placeholders for later provisions apart);
- every unit key is a valid path and every text a clean line list (no reader tokens);
- its version day is on or before the data set's day.
Acts that fail any check are left out and listed in .tmp-bulk-report.json with the reason. Acts built with their
history (corpus.json and the 60-* parts) and the acts whose history is in progress (parse_acts.ACTS) are not
repeated here. Parts are corpus.d/70-lover-NN.json, NN-sized blocks in the data set's file order.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lovdata as L  # noqa: E402
import parse as P  # noqa: E402
import parse_acts as A  # noqa: E402

GJ_URL = 'https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2'
PUBLISHER = {'name': 'Lovdata (consolidated text, unofficial)', 'email': 'gjeldende-lover@lovdata.invalid'}
FOLD = str.maketrans({'æ': 'ae', 'ø': 'o', 'å': 'a', 'é': 'e', 'ü': 'u', 'ö': 'o', 'ä': 'a'})


def history_lids():
    """Lovdata ids of the acts built with their history, or in progress."""
    out = {row[2] for row in A.ACTS}
    c = json.load(open(os.path.join(HERE, 'corpus.json'), encoding='utf-8'))
    for a in c['acts']:
        m = re.search(r'/lov/(\d{4}-\d{2}-\d{2}(?:-\d+)?)', a.get('url', ''))
        if m:
            out.add('LOV-' + m.group(1))
    for f in os.listdir(os.path.join(HERE, 'corpus.d')):
        if f.startswith('60-') and f.endswith('.json'):
            for a in json.load(open(os.path.join(HERE, 'corpus.d', f), encoding='utf-8'))['acts']:
                m = re.search(r'/lov/(\d{4})-(\d{2})-(\d{2})-(\d+)', a.get('url', ''))
                if m:
                    out.add('LOV-%s-%s-%s-%s' % (m.group(1), m.group(2), m.group(3), int(m.group(4))))
    return {re.sub(r'-0*(\d+)$', lambda m: '-' + m.group(1), x) for x in out}


def official_articles(raw):
    """The consolidated document's own article numbers (raw markup), repealed and pending placeholders apart."""
    t = raw.decode('utf-8')
    off = []
    for m in re.finditer(r'<article class="legalArticle"[^>]*data-name="§([^"]+)"[^>]*>(?=(.{0,400}))', t, re.S):
        n = re.sub(r'\s+', '', m.group(1)).lower()
        if re.search(r'changesToParent"><strong>Tilføyes</strong>', m.group(2)):
            continue
        if re.search(r'legalArticleTitle">\((?:Opphevet|Oppheva)\)<', m.group(2)):
            continue
        off.append(n)
    return off


def our_articles(units):
    ours = []
    for k, u in units.items():
        if not k.startswith('paragraf'):
            continue
        m = re.match(r'# §[ ]*([0-9]+(?:[ ]*-[ ]*[0-9]+)?(?:[ ]?[a-zA-Z](?![a-zæøå]))?(?:[ ]*-[ ]*[0-9]+)?)', u['text'].split('\n', 1)[0])
        ours.append(re.sub(r'\s+', '', m.group(1)).lower() if m else '?' + k)
    return ours


def slug_of(h, lid, used):
    short = (h.get('titleShort') or '').split(' – ')[0].strip()
    s = re.sub(r'[^a-z0-9]+', '-', short.lower().translate(FOLD)).strip('-')
    if not s or not re.match(r'^[a-z]', s):
        s = lid.lower()
    if s in used:
        s = '%s-%s' % (s, lid[4:].lower())
    used.add(s)
    return s


def short_of(h, lid):
    t = h.get('titleShort') or ''
    if ' – ' in t:
        return t.split(' – ', 1)[1].strip()
    return t.strip() or lid


GJF_URL = 'https://api.lovdata.no/v1/publicData/get/gjeldende-sentrale-forskrifter.tar.bz2'
SETS = {
    # laws: the data set's day is its lastModified stamp in the data set list
    'lover': {'tar': GJ_URL, 'prefixes': ('nl/',), 'idre': r'^LOV-\d{4}-\d{2}-\d{2}(?:-\d+)?$', 'part': '70-lover-%02d',
              'publisher': PUBLISHER, 'kind': 'act', 'asof_words': 'as of'},
    # central regulations (forskrifter); the file was retrieved after the list's stamp, so its day is the retrieval day
    'forskrifter': {'tar': GJF_URL, 'prefixes': ('sf/',), 'idre': r'^FOR-\d{4}-\d{2}-\d{2}-\d+$',
                    'part': '80-forskrifter-%02d', 'asof': '2026-11-02', 'kind': 'regulation',
                    'publisher': {'name': 'Lovdata (consolidated text, unofficial)',
                                  'email': 'gjeldende-forskrifter@lovdata.invalid'},
                    'asof_words': 'as retrieved on'},
}
CFG = SETS['lover']


def read_act(name, raw, asof):
    """(act, None) or (None, reason)."""
    h = L.header(raw)
    lid = h.get('legacyID') or ''
    if not re.match(CFG['idre'], lid):
        return None, 'no id in the header (%r)' % lid
    L.CHAPNUM = A.chapter_numbered(raw)
    t = re.sub(r'<[^>]+>', ' ', raw.decode('utf-8', 'replace'))
    L.CHAP_NOSPACE = L.CHAPNUM and bool(re.search(r'§\s*\d{1,2}[A-Z]-\d', t)) and not re.search(r'§\s*\d{1,2} [A-Z]-\d', t)
    skipped = []
    try:
        units = A.undo(L.consolidated(raw, skipped))
    except (ValueError, KeyError, IndexError, AttributeError) as e:
        return None, 'reader error: %s' % str(e)[:200]
    finally:
        chap = L.CHAPNUM
        L.CHAPNUM = L.CHAP_NOSPACE = False
    if not units:
        return None, 'no units read'
    for k, u in units.items():
        if not re.fullmatch(r'[a-z0-9-]+', k):
            return None, 'bad unit key %r' % k
        tx = u.get('text') or ''
        if not tx.endswith('\n') or L.CONT in tx or re.search(r'\b9\d{5,6}\b', tx) and chap:
            return None, 'unclean text in %s' % k
    off, ours = official_articles(raw), our_articles(units)
    if sorted(off) != sorted(ours):
        return None, 'paragraphs differ from the official list: only official %s, only ours %s' % (
            sorted(set(off) - set(ours))[:8], sorted(set(ours) - set(off))[:8])
    day = h.get('lastChangeInForce') or h.get('dateInForce') or ''
    day = day[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        return None, 'no in-force day in the header'
    if day > asof:
        return None, 'last change in force %s is after the data set day %s' % (day, asof)
    act = {
        'lid': lid,
        'title': h.get('title') or lid,
        'short': short_of(h, lid),
        'url': ('https://lovdata.no/dokument/NL/lov/' + lid[4:]) if lid.startswith('LOV-')
               else 'https://lovdata.no/dokument/' + (h.get('dokid') or 'SF/forskrift/' + lid[4:]),
        'publisher': CFG['publisher'],
        'first_law': None,
        'earlier_laws': [],
        'versions': [{
            'from': day,
            'source_url': CFG['tar'] + '#' + name,
            'sha256': __import__('hashlib').sha256(raw).hexdigest(),
            'units': units,
            'credits': {},
            'note': ('Current text only: Lovdata\'s consolidated text (unofficial; Norway has no official '
                     'consolidations) %s %s, in force since %s (%s).' % (
                         CFG['asof_words'], asof, day, 'the last change Lovdata records in force'
                         if h.get('lastChangeInForce') else 'its own in-force day; Lovdata records no change in force')),
        }],
        '_skipped': skipped,
        '_hdr': {k: h.get(k) for k in ('dateInForce', 'lastChangeInForce', 'lastChangedBy')},
    }
    return act, None


def main():
    args = sys.argv[1:]
    size = int(args[args.index('--size') + 1]) if '--size' in args else 60
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    out_dir = args[args.index('--out') + 1] if '--out' in args else os.path.join(HERE, 'corpus.d')
    global CFG
    CFG = SETS[args[args.index('--set') + 1] if '--set' in args else 'lover']
    L.REPEAL_PARTS = True
    L.OLD_HEADS = True
    asof = CFG.get('asof') or P.gj_asof()
    gj = L.read_tar(CFG['tar'])
    skip = history_lids() if CFG['tar'] == GJ_URL else set()
    used = set()
    for f in os.listdir(os.path.join(HERE, 'corpus.d')):
        if f.startswith('60-') and f.endswith('.json'):
            used |= {a['slug'] for a in json.load(open(os.path.join(HERE, 'corpus.d', f), encoding='utf-8'))['acts']}
    used |= {a['slug'] for a in json.load(open(os.path.join(HERE, 'corpus.json'), encoding='utf-8'))['acts']}
    report = {'asof': asof, 'files': len(gj), 'history': [], 'ok': [], 'failed': {}}
    acts = []
    for name in sorted(gj):
        if not name.startswith(CFG['prefixes']):
            continue
        h = L.header(gj[name])
        lid = h.get('legacyID') or name
        if lid in skip:
            report['history'].append(lid)
            continue
        if only and lid not in only:
            continue
        act, why = read_act(name, gj[name], asof)
        if why:
            report['failed'][lid] = why
            continue
        act['slug'] = slug_of(h, lid, used) if lid.startswith('LOV-') else lid.lower()
        acts.append(act)
        report['ok'].append(lid)
    parts = [acts[i:i + size] for i in range(0, len(acts), size)]
    for i, block in enumerate(parts, 1):
        decisions = []
        for a in block:
            sk = a.pop('_skipped')
            a.pop('_hdr')
            lid = a.pop('lid')
            if sk:
                decisions.append('%s (%s): the consolidated text\'s section%s %s (not part of the act\'s own '
                                 'chapters, such as an annexed text) %s not included.' % (
                                     a['slug'], lid, 's' if len(sk) > 1 else '', '; '.join('«%s»' % x for x in sk),
                                     'are' if len(sk) > 1 else 'is'))
        decisions.insert(0, 'Current-text %ss (%d in this part): each is one version, Lovdata\'s consolidated text '
                            '(unofficial) %s %s, credited to Lovdata as the oldest version available and dated by '
                            'the day Lovdata gives for the last change in force (or its own in-force day). '
                            'Each one\'s paragraphs equal the consolidated document\'s own list of articles.'
                         % (CFG['kind'], len(block), CFG['asof_words'], asof))
        part = {'acts': [{k: a[k] for k in ('slug', 'short', 'title', 'url', 'publisher', 'first_law', 'earlier_laws',
                                             'versions')} for a in block],
                'laws': {}, 'decisions': decisions,
                'ai_use': ['none']}
        fn = os.path.join(out_dir, (CFG['part'] % i) + '.json')
        with open(fn + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
            json.dump(part, f, ensure_ascii=False, indent=1, sort_keys=False)
            f.write('\n')
        os.replace(fn + '.tmp', fn)
    report['parts'] = len(parts)
    with open(os.path.join(HERE, '.tmp-bulk-report-%s.json' % CFG['part'][:2]), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print('files %d, history %d, ok %d, failed %d, parts %d' % (
        len(gj), len(report['history']), len(report['ok']), len(report['failed']), len(parts)))


if __name__ == '__main__':
    main()
