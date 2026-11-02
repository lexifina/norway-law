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


# ---------------------------------------------------------------- the article reader and single-file acts
# For a document the paragraph reader above does not split (treaties numbered "Art I", "§ 21 A" / "§ 8 A-1" numbers,
# paragraphs it does not list, or no numbered articles at all), the units are read straight from the document's own
# markup: each numbered article (Lovdata's "legalArticle") is a unit, each section heading opens a heading unit, and
# text outside any article is its own unit. A document with no numbered articles is one unit holding its whole text
# (a single-file act). Nothing is dropped or reordered: the units' words, in order, must equal the document's text
# (Lovdata's editorial notes, footnotes and the title line apart; repealed "(Opphevet)" articles and empty
# placeholders apart, as for every current-text act).
BLOCK = {'article', 'section', 'div', 'p', 'ol', 'ul', 'li', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'caption',
         'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'footer', 'figure', 'figcaption', 'blockquote', 'main'}
HEADS = ('h2', 'h3', 'h4', 'h5', 'h6')


def _skip(n):
    return any(c in L.SKIP_CLASSES for c in n.cls)


def _is_art(n):
    return n.tag == 'article' and n.has('legalArticle')


def _art_head(a):
    return next((k for k in a.elems() if k.has('legalArticleHeader')), None)


def _dropped(a):
    """A repealed article printed only as "(Opphevet ...)", or a placeholder with no words of its own."""
    hd = _art_head(a)
    body = ' '.join(L.text(k) for k in a.elems() if k is not hd and not _skip(k)).strip()
    t = a.first(lambda x: x.has('legalArticleTitle'))
    tt = L.text(t).strip() if t is not None else ''
    if not body:
        return True
    return bool(re.match(r'^\((Opphevet|Opphevd|Oppheva)\b', body)) or (
        bool(re.match(r'^\((Opphevet|Opphevd|Oppheva)\b', tt)) and re.fullmatch(r'[\s–-]*', body) is not None)


def _sec_head(sec):
    return next((k for k in sec.elems() if k.tag in HEADS and not k.has('legalArticleHeader')), None)


def _key_part(s):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower().translate(FOLD)).strip('-')
    return re.sub(r'\d+', lambda m: m.group(0).zfill(2), s)


def _art_key(name):
    """'§21A' -> paragraf-021-a, '§8A-1' -> paragraf-08-a-001, '§1-3a' -> paragraf-01-003-a, 'a3a' -> artikkel-003-a,
    'aIV' -> artikkel-004; None when the number has another form."""
    m = re.fullmatch(r'§(\d+)\s*([A-Za-z]?)', name)
    if m:
        return 'paragraf-%03d' % int(m.group(1)) + ('-' + m.group(2).lower() if m.group(2) else '')
    m = re.fullmatch(r'§(\d+)\s*([A-Za-z]?)-(\d+)\s*([a-z]?)', name)
    if m:
        return ('paragraf-%02d' % int(m.group(1)) + ('-' + m.group(2).lower() if m.group(2) else '')
                + '-%03d' % int(m.group(3)) + ('-' + m.group(4) if m.group(4) else ''))
    m = re.fullmatch(r'a(\d+)([a-z]?)', name)
    if m:
        return 'artikkel-%03d' % int(m.group(1)) + ('-' + m.group(2) if m.group(2) else '')
    m = re.fullmatch(r'a([IVXL]+)', name)
    if m:
        return 'artikkel-%03d' % L.roman(m.group(1))
    return None


def _lines(node, out, pre):
    """Append the lines of a block node to out: one line per paragraph, list item or table row, list labels first."""
    buf = []

    def flush():
        if not buf:
            return
        n = L.Node('span', {}, None)
        n.kids = list(buf)
        buf.clear()
        t = L.text(n)
        if not t:
            return
        if all(isinstance(k, str) and not k.strip() or isinstance(k, L.Node) and k.has('data-marginOriginalId')
               for k in n.kids) and not pre[0]:
            pre[0] = t  # a number printed in the margin ("1.1.") goes before the line it numbers
            return
        out.append((pre[0] + ' ' + t) if pre[0] else t)
        pre[0] = ''
    for k in node.kids:
        if isinstance(k, str) or k.tag not in BLOCK:
            buf.append(k)
            continue
        if _skip(k):
            continue
        flush()
        if k.tag == 'tr':
            cells = [_cell(c) for c in k.elems() if c.tag in ('td', 'th') and not _skip(c)]
            t = ' | '.join(c for c in cells)
            if t.strip(' |'):
                out.append((pre[0] + ' ' + t) if pre[0] else t)
                pre[0] = ''
        elif k.tag == 'li':
            lab = L.li_label(k)
            if lab:
                pre[0] = (pre[0] + ' ' + lab) if pre[0] else lab
            _lines(k, out, pre)
            if pre[0]:  # an empty item (a blank line of a form): its label alone
                out.append(pre[0])
                pre[0] = ''
        else:
            _lines(k, out, pre)
    flush()


def _cell(c):
    """A table cell on one line (a list inside it keeps its labels)."""
    out = []
    _lines(c, out, [''])
    return ' '.join(out)


def generic_units(raw):
    """(units, single_file) read from the document's own markup (see above)."""
    root = L.dom(raw)
    main = root.first(lambda n: n.tag == 'main')
    arts = [a for a in main.find_all(_is_art) if not any(_is_art(p) for p in _ancestors(a))]
    single = not arts
    units = []  # [key, label, kind, lines]
    if single:
        lines = []
        _lines_main(main, lines)
        return ([['tekst', 'Tekst', 'text', lines]] if lines else []), True
    names = [a.attrs.get('data-name', '') for a in arts if not _dropped(a)]
    keys = [_art_key(x) for x in names]
    by_id = None in keys or len(set(keys)) != len(keys)

    def new(key, label, kind, lines):
        units.append([key, label, kind, lines])
        return units[-1]

    def walk(node, owner, base):
        cur = owner
        seq = [0]
        for k in node.kids:
            if isinstance(k, L.Node) and _skip(k):
                continue
            if isinstance(k, L.Node) and k.tag == 'h1' and node is main:
                continue
            if isinstance(k, L.Node) and _is_art(k):
                if _dropped(k):
                    continue
                v = k.first(lambda x: x.has('legalArticleValue'))
                key = (_key_part(k.attrs.get('id', '')) if by_id else _art_key(k.attrs.get('data-name', '')))
                label = L.text(v) if v is not None else k.attrs.get('id', '')
                kind = 'article' if re.match(r'^(Art|Artikkel)\b', label) else 'paragraph'
                hd = _art_head(k)
                lines = ['# ' + L.text(hd)] if hd is not None and L.text(hd) else []
                pre = ['']
                for c in k.kids:
                    if c is hd or isinstance(c, L.Node) and _skip(c):
                        continue
                    tmp = L.Node('div', {}, None)
                    tmp.kids = [c]
                    _lines(tmp, lines, pre)
                new(key, label, kind, lines)
                cur = None
                continue
            if isinstance(k, L.Node) and (k.tag == 'section' or k.tag in BLOCK and any(_is_art(x) for x in k.iter())):
                if k.tag == 'section':
                    hd = _sec_head(k)
                    sk = _key_part(k.attrs.get('id', '')) or (base + '-del')
                    if hd is not None:
                        u = new(sk, L.text(hd), 'heading', ['# ' + L.text(hd)])
                        sub = L.Node(k.tag, k.attrs, None)
                        sub.kids = [x for x in k.kids if x is not hd]
                        walk(sub, u, sk)
                    else:
                        walk(k, None, sk)
                else:
                    walk(k, None, base)
                cur = None
                continue
            if cur is None:
                seq[0] += 1
                key = (base + '-' if base else '') + 'tekst-%02d' % seq[0]
                while any(u[0] == key for u in units):
                    seq[0] += 1
                    key = (base + '-' if base else '') + 'tekst-%02d' % seq[0]
                cur = new(key, 'Tekst', 'text', [])
            tmp = L.Node('div', {}, None)
            tmp.kids = [k]
            _lines(tmp, cur[3], [''])
    walk(main, None, '')
    return [u for u in units if u[3]], False


def _ancestors(n):
    p = n.parent
    while p is not None:
        yield p
        p = p.parent


def _lines_main(main, lines):
    tmp = L.Node('div', {}, None)
    for k in main.kids:
        if isinstance(k, L.Node) and k.tag == 'h1':
            continue
        if isinstance(k, L.Node) and k.tag == 'section':
            hd = _sec_head(k)
            if hd is not None and L.text(hd):
                lines.append('# ' + L.text(hd))
            sub = L.Node('div', {}, None)
            sub.kids = [x for x in k.kids if x is not hd]
            _lines_main(sub, lines)
            continue
        tmp.kids = [k]
        _lines(tmp, lines, [''])


def doc_words(raw):
    """The document's text as one string with no white space: every text node of the body in order, list labels
    included; editorial notes and footnotes (L.SKIP_CLASSES), the title line, and dropped articles apart."""
    root = L.dom(raw)
    main = root.first(lambda n: n.tag == 'main')
    out = []

    def walk(n):
        for k in n.kids:
            if isinstance(k, str):
                out.append(k)
                continue
            if _skip(k) or (k.tag == 'h1' and n is main) or (_is_art(k) and _dropped(k)):
                continue
            if k.tag == 'br':
                out.append(' ')
                continue
            if k.tag == 'li':
                out.append(' ' + L.li_label(k) + ' ')
            walk(k)
            if k.tag in BLOCK or k.tag in ('td', 'th'):
                out.append(' ')
    walk(main)
    return _squash(L.norm(''.join(out)))


def _squash(s):
    return re.sub(r'[\s|]+', '', s)


def units_words(units):
    return _squash(''.join(re.sub(r'(?m)^# ', '', u['text']) for u in units.values()))


def read_act(name, raw, asof):
    """(act, None) or (None, reason)."""
    h = L.header(raw)
    lid = h.get('legacyID') or ''
    if not re.match(CFG['idre'], lid):
        return None, 'no id in the header (%r)' % lid
    day, part = in_force_day(h)
    if not day:
        return None, 'no in-force day in the header (%r)' % (h.get('dateInForce') or '')[:60]
    if day >= '2027-01-01' and not stated_future_day(h):
        return None, 'no single stated future in-force day (%r)' % (h.get('dateInForce') or '')[:100]
    if day > asof and day < '2027-01-01':
        return None, 'last change in force %s is after the data set day %s' % (day, asof)
    act, why = read_paragraphs(name, raw, asof, h, lid, day)
    if act is not None or not GENERIC:
        return act, why
    units, single = generic_units(raw)
    if not units:
        return None, 'no text read (%s)' % why
    u = {}
    for key, label, kind, lines in units:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key) or key in u:
            return None, 'bad or repeated unit key %r (%s)' % (key, why)
        u[key] = {'label': label, 'kind': kind, 'text': '\n'.join(lines) + '\n'}
    if doc_words(raw) != units_words(u):
        return None, 'article reader: words differ from the document (%s)' % why
    act = make_act(name, raw, asof, h, lid, u, day, part)
    act['_how'] = 'single' if single else 'articles'
    act['_why'] = why
    return act, None


GENERIC = False  # --generic: read the documents the paragraph reader leaves out with the article reader


def stated_future_day(h):
    """Only a stated 2027+ start day belongs on fremtidig; a condition or several start days stays held."""
    d = (h.get('dateInForce') or '').strip()
    if re.fullmatch(r'Inntektsåret\s+\d{4}', d, re.I):
        return True
    # A bounded period gives one start day and one end day, unlike two commencement days.
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}\s*[–-]\s*\d{4}-\d{2}-\d{2}', d):
        return True
    return re.fullmatch(r'\d{4}-\d{2}-\d{2}', d) is not None


def in_force_day(h):
    """(day, partly): Lovdata's last change in force, else its in-force day; partly when Lovdata gives the rest of the
    act's in-force day as not yet set ("2026-07-01, Kongen bestemmer"). With GENERIC, the earliest day it names."""
    if (h.get('lastChangeInForce') or '')[:10] and re.fullmatch(r'\d{4}-\d{2}-\d{2}', h['lastChangeInForce'][:10]):
        return h['lastChangeInForce'][:10], False
    d = h.get('dateInForce') or ''
    year = re.fullmatch(r'Inntektsåret\s+(\d{4})', d.strip(), re.I)
    if year:
        return '%s-01-01' % year.group(1), False
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d[:10]):
        return d[:10], len(d) > 10
    if GENERIC:
        days = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', d)
        if days:
            return min(days), True
    return None, False


def read_paragraphs(name, raw, asof, h, lid, day):
    """The paragraph reader: (act, None) or (None, reason)."""
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
    if day > asof and day < '2027-01-01':
        return None, 'last change in force %s is after the data set day %s' % (day, asof)
    act = make_act(name, raw, asof, h, lid, units, day, False)
    act['_skipped'] = skipped
    return act, None


def make_act(name, raw, asof, h, lid, units, day, partly):
    if h.get('lastChangeInForce'):
        why = 'the last change Lovdata records in force'
    elif re.fullmatch(r'Inntektsåret\s+\d{4}', (h.get('dateInForce') or '').strip(), re.I):
        why = 'Lovdata says «%s», dated to the first day of that income year' % h['dateInForce'].strip()
    elif GENERIC and partly:
        why = ('the first day Lovdata gives for its entry into force; Lovdata gives the rest as %s'
               % ', '.join('«%s»' % x.strip() for x in (h.get('dateInForce') or '').split(',')
                           if not re.fullmatch(r'\s*\d{4}-\d{2}-\d{2}\s*', x)))
    else:
        why = 'its own in-force day; Lovdata records no change in force'
    return {
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
                     'consolidations) %s %s, %s %s (%s).' % (
                         CFG['asof_words'], asof,
                         'scheduled to take effect on' if day >= '2027-01-01' else 'in force since', day, why)),
        }],
        '_skipped': [],
        '_hdr': {k: h.get(k) for k in ('dateInForce', 'lastChangeInForce', 'lastChangedBy')},
    }


def main():
    args = sys.argv[1:]
    size = int(args[args.index('--size') + 1]) if '--size' in args else 60
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    out_dir = args[args.index('--out') + 1] if '--out' in args else os.path.join(HERE, 'corpus.d')
    global CFG
    CFG = SETS[args[args.index('--set') + 1] if '--set' in args else 'lover']
    L.REPEAL_PARTS = True
    L.OLD_HEADS = True
    global GENERIC
    GENERIC = '--generic' in args
    history = CFG['tar'] == GJ_URL
    if '--tar' in args:
        # a later copy of the same data set (run_bulk.py --refresh), cached under "<url>@<lastModified>"
        CFG = dict(CFG, tar=args[args.index('--tar') + 1])
    asof = (args[args.index('--asof') + 1] if '--asof' in args else None) or CFG.get('asof') or P.gj_asof()
    gj = L.read_tar(CFG['tar'])
    skip = history_lids() if history else set()
    used = set()
    first = 1
    prefix = CFG['part'].split('-%')[0]
    for f in sorted(os.listdir(os.path.join(HERE, 'corpus.d'))):
        if (f.startswith('60-') or f.startswith(('70-', '80-'))) and f.endswith('.json'):
            acts_f = json.load(open(os.path.join(HERE, 'corpus.d', f), encoding='utf-8'))['acts']
            used |= {a['slug'] for a in acts_f}
            if '--new-only' in args and f.startswith(prefix + '-'):
                # published current-text parts stay as they are: their acts are not read again, new parts follow
                skip |= {('LOV-' if f.startswith('70-') else 'FOR-') + a['url'].rsplit('/', 1)[-1] for a in acts_f}
                first = max(first, int(re.search(r'-(\d+)\.json$', f).group(1)) + 1)
    if '--new-only' not in args:
        # a full run renumbers from 01 and must not see its own earlier output as taken slugs
        for f in os.listdir(os.path.join(HERE, 'corpus.d')):
            if f.startswith(('70-', '80-')) and f.endswith('.json'):
                used -= {a['slug'] for a in json.load(open(os.path.join(HERE, 'corpus.d', f), encoding='utf-8'))['acts']}
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
    for i, block in enumerate(parts, first):
        decisions = []
        for a in block:
            sk = a.pop('_skipped')
            lid = a.pop('lid')
            how = a.pop('_how', None)
            a.pop('_why', None)
            if how == 'single':
                decisions.append('%s (%s): single-file act. The consolidated document has no numbered articles, so '
                                 'the act is one unit (`tekst`) holding its whole text.' % (a['slug'], lid))
            elif how == 'articles':
                decisions.append('%s (%s): read article by article from the consolidated document (%s).' % (
                    a['slug'], lid, 'numbered "Art."' if any(
                        u['kind'] == 'article' for u in a['versions'][0]['units'].values()) else 'numbered by §'))
            if GENERIC and '; Lovdata gives the rest as' in a['versions'][0]['note']:
                decisions.append('%s (%s): in force in part; dated by the first in-force day Lovdata gives (%s), with '
                                 'the text as Lovdata prints it.' % (a['slug'], lid, a['versions'][0]['from']))
            income = re.fullmatch(r'Inntektsåret\s+(\d{4})', (a.get('_hdr', {}).get('dateInForce') or '').strip(), re.I)
            if income and not a['_hdr'].get('lastChangeInForce'):
                decisions.append('%s (%s): Lovdata gives the in-force day as «%s»; the income year begins on '
                                 '%s-01-01, used as this version\'s day.' % (
                                     a['slug'], lid, a['_hdr']['dateInForce'].strip(), income.group(1)))
            if a['versions'][0]['from'] >= '2027-01-01':
                decisions.append('%s (%s): Lovdata states %s as the in-force day; this version belongs on '
                                 'fremtidig until that day.' % (a['slug'], lid, a['versions'][0]['from']))
            if sk:
                decisions.append('%s (%s): the consolidated text\'s section%s %s (not part of the act\'s own '
                                 'chapters, such as an annexed text) %s not included.' % (
                                     a['slug'], lid, 's' if len(sk) > 1 else '', '; '.join('«%s»' % x for x in sk),
                                     'are' if len(sk) > 1 else 'is'))
            a.pop('_hdr')
        decisions.insert(0, ('Current-text %ss (%d in this part): each is one version, Lovdata\'s consolidated text '
                            '(unofficial) %s %s, credited to Lovdata as the oldest version available and dated by '
                            'the day Lovdata gives for the last change in force (or its own in-force day). '
                            + ('Each one\'s paragraphs equal the consolidated document\'s own list of articles.'
                               if not GENERIC else
                               'Each act\'s units hold the consolidated document\'s text word for word (Lovdata\'s '
                               'editorial notes, footnotes, the title line and repealed "(Opphevet)" articles apart; '
                               'images are not included): paragraphs, articles ("Art.") and headings as the document '
                               'numbers them, or one unit holding the whole text of a document with no numbered '
                               'articles (a single-file act).'))
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
