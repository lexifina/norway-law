"""Shared reading of Lovdata's public data archives (cache only, no network).

- read the tar archives straight from .cache/ (bz2, streamed, one pass)
- a small DOM over Lovdata's HTML-in-XML documents
- the consolidated text of an act (gjeldende lover) as units: chapter headings and paragraphs
- text normalisation used everywhere, so replayed and official text compare like for like
"""
import hashlib, html, os, re, tarfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
API = 'https://api.lovdata.no/v1/publicData/'
GJ = API + 'get/gjeldende-lover.tar.bz2'
LT = [API + 'get/lovtidend-avd1-2001-2025.tar.bz2', API + 'get/lovtidend-avd1-2026.tar.bz2']


def cpath(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + '.bin')


def read_tar(url, want=None):
    """{member name: bytes} for the members `want(name)` accepts (all when None)."""
    out = {}
    with tarfile.open(cpath(url), 'r|bz2') as t:
        for m in t:
            if m.isfile() and (want is None or want(m.name)):
                out[m.name] = t.extractfile(m).read()
    return out


# ---------------------------------------------------------------- DOM
class Node:
    __slots__ = ('tag', 'attrs', 'kids', 'parent')

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, dict(attrs), [], parent

    @property
    def cls(self):
        return (self.attrs.get('class') or '').split()

    def has(self, c):
        return c in self.cls

    def iter(self):
        yield self
        for k in self.kids:
            if isinstance(k, Node):
                yield from k.iter()

    def find_all(self, pred):
        return [n for n in self.iter() if pred(n)]

    def first(self, pred):
        for n in self.iter():
            if pred(n):
                return n
        return None

    def elems(self):
        return [k for k in self.kids if isinstance(k, Node)]


VOID = {'br', 'img', 'hr', 'meta', 'link', 'base', 'input', 'col', 'wbr'}


class _B(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root', {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, d):
        self.cur.kids.append(d)


def dom(raw):
    b = _B()
    b.feed(raw.decode('utf-8') if isinstance(raw, bytes) else raw)
    b.close()
    return b.root


# ---------------------------------------------------------------- text
SKIP_CLASSES = {'changesToParent', 'footnotereference', 'footnotes', 'footnote', 'footnoteLabel', 'commentToParent'}


def norm(s):
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace('­', '')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('—', '–')
    s = re.sub(r'(?<=\d)–(?=\d)', '-', s)  # number ranges: one form of dash
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r' ([,;.:)])', r'\1', s)
    s = re.sub(r'\( ', '(', s)
    return s


def text(n, stop=None):
    """Plain text of a node, skipping notes, footnote markers and (when given) nodes `stop` accepts."""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
            return
        if any(c in SKIP_CLASSES for c in x.cls):
            return
        if stop and stop(x):
            return
        if x.tag == 'br':
            out.append(' ')
            return
        for k in x.kids:
            walk(k)
    walk(n)
    return norm(''.join(out))


def is_list(x):
    return x.tag in ('ul', 'ol') or x.has('defaultList')


def li_label(li):
    """List item label in one form: 'a)', '1)'. Lovtidend writes 'a)', the consolidated text 'a.'."""
    lab = (li.attrs.get('data-li-identifier') or li.attrs.get('data-name') or '').strip()
    m = re.match(r'^\(?([a-zæøå]|\d+)[.)]$', lab)
    return m.group(1) + ')' if m else lab


def ledd_lines(p):
    """One ledd (a legalP) as lines: its own text, then each list item as 'label text'."""
    lines = [text(p, stop=is_list)]
    for lst in p.elems():
        if is_list(lst):
            lines += list_lines(lst)
    return [l for l in lines if l]


def list_lines(lst):
    out = []
    for li in lst.elems():
        if li.tag != 'li':
            continue
        lab = li_label(li)
        body = []
        sub = []
        for art in li.elems():
            for p in ([art] if not art.has('listArticle') else art.elems()):
                if is_list(p):
                    sub += list_lines(p)
                    continue
                t = text(p, stop=is_list)
                if t:
                    body.append(t)
                for q in p.elems():
                    if is_list(q):
                        sub += list_lines(q)
        line = norm((lab + ' ' if lab else '') + ' '.join(body))
        out.append(line)
        out += sub
    return out


# ---------------------------------------------------------------- keys
def para_key(num):
    """'75' -> paragraf-075, '110 a' -> paragraf-110-a, '12a' -> paragraf-012-a."""
    m = re.match(r'^(\d+)\s*([a-z]?)$', num.strip())
    if not m:
        raise ValueError(num)
    return 'paragraf-%03d' % int(m.group(1)) + ('-' + m.group(2) if m.group(2) else '')


def chap_key(label):
    m = re.match(r'^(?:Kapittel\s+)?([0-9]+|[A-Z])\b', label.strip())
    v = m.group(1)
    return 'kapittel-' + (('%02d' % int(v)) if v.isdigit() else v.lower())


def para_unit(num, title, ledd):
    head = '# § ' + num + ('. ' + title if title else '')
    lines = [head] + [l for ld in ledd for l in ld]
    return {'label': '§ ' + num, 'kind': 'paragraph', 'text': '\n'.join(lines) + '\n'}


def chap_unit(label):
    return {'label': label, 'kind': 'heading', 'text': '# ' + label + '\n'}


# ---------------------------------------------------------------- consolidated text
CHAP_RE = re.compile(r'^(?:Kapittel\s+)?([0-9]+|[A-Z])\b\.?')
PART_ORD = {'første': 1, 'annen': 2, 'andre': 2, 'tredje': 3, 'fjerde': 4, 'femte': 5, 'sjette': 6, 'sjuende': 7,
            'syvende': 7, 'åttende': 8, 'niende': 9, 'tiende': 10}


ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}


def roman(s):
    n, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        n, prev = (n - v, prev) if v < prev else (n + v, v)
    return n


def head_key(label, chapter=None):
    """Key of a part, chapter or sub-section heading, or None when it is none of these (an annex).

    Inside a chapter, 'I. ...', 'II. ...' are its numbered sub-sections (avsnitt): kapittel-07-avsnitt-02."""
    if chapter and chapter.startswith('kapittel-'):
        m = re.match(r'^([IVXL]+)\.\s', label)
        if m:
            return chapter.split('-avsnitt-')[0] + '-avsnitt-%02d' % roman(m.group(1))
    m = re.match(r'^(\w+) del\b', label, re.I)
    if m and m.group(1).lower() in PART_ORD:
        return 'del-%d' % PART_ORD[m.group(1).lower()]
    m = re.match(r'^Del\s+(\d+)\b', label)
    if m:
        return 'del-%d' % int(m.group(1))
    m = re.match(r'^Kapit+el\s+(\d+)\s*([a-z])?\b', label)
    if m:
        return 'kapittel-%02d' % int(m.group(1)) + ('-' + m.group(2) if m.group(2) else '')
    m = re.match(r'^([A-Z])\.?\s', label)
    if m:
        return 'kapittel-' + m.group(1).lower()
    return None


def section_heading(sec):
    for k in sec.elems():
        if k.tag in ('h2', 'h3', 'h4', 'h5'):
            return text(k)
        if k.tag == 'section' or k.has('legalArticle'):
            return None
    return None


def walk_act(raw, skipped=None):
    """Yield ('h', key, label, None, None) for headings and ('p', key, num, title, ledd) for paragraphs, in order.

    A section whose heading is not a part, chapter or sub-section is not walked (for personopplysningsloven:
    the annexed GDPR); its heading goes to `skipped`. A repealed paragraph printed only as "(Opphevet ...)" is
    not yielded: the editorial line is not law text."""
    root = dom(raw)
    main = root.first(lambda n: n.tag == 'main')
    out = []

    def walk(n, chapter):
        for k in n.elems():
            if k.tag == 'section':
                lab = section_heading(k)
                sub = chapter
                if lab is not None:
                    hk = head_key(lab, chapter)
                    if hk is None:
                        if skipped is not None:
                            skipped.append(lab)
                        continue
                    out.append(('h', hk, lab, None, None, chapter))
                    sub = hk
                walk(k, sub)
            elif k.has('legalArticle'):
                v = k.first(lambda x: x.has('legalArticleValue'))
                t = k.first(lambda x: x.has('legalArticleTitle'))
                num = text(v).replace('§', '').strip()
                ledd = [ledd_lines(p) for p in k.elems() if p.has('legalP') or p.has('numberedLegalP')]
                ledd = [l for l in ledd if l]
                if not ledd or all(re.match(r'^\((Opphevet|Opphevd|Oppheva)\b', x[0]) for x in ledd):
                    continue
                out.append(('p', para_key(num), num, text(t) if t is not None else '', ledd, chapter))
            else:
                walk(k, chapter)
    walk(main, None)
    return out


def linked_text(n):
    """Text of a note with each link written as 'text [href]'."""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
            return
        for k in x.kids:
            walk(k)
        if x.tag == 'a' and x.attrs.get('href'):
            out.append(' [' + x.attrs['href'] + ']')
    walk(n)
    return norm(''.join(out))


def notes(raw):
    """{unit key: [amendment note text with links]} from a consolidated document's changesToParent notes."""
    root = dom(raw)
    out = {}
    for art in root.find_all(lambda n: n.has('legalArticle')):
        v = art.first(lambda x: x.has('legalArticleValue'))
        if v is None:
            continue
        try:
            key = para_key(text(v).replace('§', '').strip())
        except ValueError:
            continue
        out[key] = [linked_text(c) for c in art.find_all(lambda n: n.has('changesToParent'))]
    return out


def consolidated(raw, skipped=None):
    """Units of a gjeldende-lover document: {key: unit}, in document order.

    A top-level section whose heading is not a chapter ("Kapittel N." or "A.") is not walked:
    for personopplysningsloven that is the annexed text of the GDPR. Its heading goes to `skipped`.
    """
    units = {}
    for kind, key, a, b, c, _ctx in walk_act(raw, skipped):
        if kind == 'p':
            # Lovdata's editorial mark for amendments of other acts it leaves out: ': – – –'
            c = [[re.sub(r'(?<=:)(\s*–){3}$', '', l) for l in ld] for ld in c]
        units[key] = chap_unit(a) if kind == 'h' else para_unit(a, b, c)
    return units


def header(raw):
    s = raw.decode('utf-8') if isinstance(raw, bytes) else raw
    s = s[:s.find('</header>')]
    out = {}
    for m in re.finditer(r'<dd class="([^"]+)">(.*?)</dd>', s, re.S):
        out[m.group(1)] = html.unescape(re.sub('<.*?>', ' ', m.group(2)))
        out[m.group(1)] = re.sub(r'\s+', ' ', out[m.group(1)]).strip()
        if m.group(1) == 'changesToDocuments':
            out['changes'] = re.findall(r'<li>(.*?)</li>', m.group(2))
    return out
