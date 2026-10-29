"""Replay Norwegian amending texts ("§ 5 første punktum skal lyde:", "§ 63 første ledd bokstav d oppheves.")
on a structured act, from the official Lovtidend document only. No model is involved.

State of an act: {key: item} where item is
    {'t': 'p', 'num': '75', 'title': '', 'ledd': [[line, line, ...], ...]}   a paragraph (§)
    {'t': 'h', 'label': 'A. Om statsformen'}                                  a chapter heading
A ledd is a list of lines: its own text, then one line per list item ('a) ...').

Addressing follows Norwegian drafting practice: ledd and punktum ordinals that are replaced or repealed
count the text as it read before the amendment; "nytt N. ledd/punktum" names the position in the new text;
list items (bokstav) are addressed by their letter. Anything the interpreter cannot read raises, so it is
never silently skipped.
"""
import copy, re
import lovdata as L

ORD = {'første': 1, 'annet': 2, 'andre': 2, 'tredje': 3, 'fjerde': 4, 'femte': 5, 'sjette': 6, 'sjuende': 7,
       'syvende': 7, 'åttende': 8, 'niende': 9, 'tiende': 10, 'ellevte': 11, 'tolvte': 12}
ORDRE = '|'.join(sorted(ORD, key=len, reverse=True))
HEAD_RE = re.compile(r'^§\s*(\d+(?:\s?[a-z])?)\s*\.?\s*(.*)$')
ABBR = {'jf.', 'nr.', 'bl.a.', 'f.eks.', 'ca.', 'pkt.', 'dvs.', 'mv.', 'm.v.', 'osv.', 'kgl.', 'res.', 'Dok.', 'tlf.'}


class ReplayError(Exception):
    pass


# ---------------------------------------------------------------- items <-> units
def render(item):
    if item['t'] == 'h':
        return L.chap_unit(item['label'])
    return L.para_unit(item['num'], item['title'], item['ledd'])


def units_of(state):
    return {k: render(v) for k, v in state.items()}


def para(num, title, ledd):
    return {'t': 'p', 'num': norm_num(num), 'title': title, 'ledd': ledd}


def norm_num(num):
    m = re.match(r'^(\d+)\s*([a-z]?)$', num.strip())
    return m.group(1) + (' ' + m.group(2) if m.group(2) else '')


def head_label(s):
    """'A Om statsformen' / 'E.<br>Menneskerettigheter' -> 'A. Om statsformen'."""
    s = L.norm(s)
    return re.sub(r'^([A-Z])\.?\s+', r'\1. ', s)


# ---------------------------------------------------------------- sentences
def sentences(s):
    out, cur = [], ''
    parts = re.split(r'(?<=[.!?])\s+', s)
    for i, p in enumerate(parts):
        cur = (cur + ' ' + p) if cur else p
        last = cur.split(' ')[-1]
        nxt = parts[i + 1] if i + 1 < len(parts) else ''
        if nxt and (last in ABBR or not re.match(r'^[«("]?[A-ZÆØÅ§]', nxt)):  # "§ 5-5 gjelder tilsvarende." starts one
            continue
        out.append(cur)
        cur = ''
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- blocks of an amending document
BLOCK = {'defaultP', 'legalP', 'centeredP', 'futuretitle', 'futureLegalArticleHeader', 'leddfortsettelse'}


def blocks(raw):
    root = L.dom(raw)
    main = root.first(lambda n: n.tag == 'main')
    out = []

    def walk(n):
        for k in n.elems():
            c = set(k.cls) & BLOCK
            if c:
                c = c.pop()
                if c == 'futureLegalArticleHeader':
                    v = k.first(lambda x: x.has('legalArticleTitle'))
                    title = L.text(v) if v is not None else ''
                    num = L.text(k, stop=lambda x: x.has('legalArticleTitle')).replace('§', '').strip(' .')
                    out.append(('head', '§ ' + num, title))
                elif c == 'legalP':
                    out.append(('p', L.ledd_lines(k), None))
                elif c == 'futuretitle':
                    out.append(('title', head_label(L.text(k)), None))
                else:
                    lists = [x for x in k.elems() if L.is_list(x)]
                    if lists and c == 'defaultP':
                        # an instruction with its new text printed inside it as a list: 'skal lyde:' + 'f) ...'
                        out.append(('d', L.text(k, stop=L.is_list), None))
                        for x in lists:
                            out.append(('p', L.list_lines(x), None))
                    else:
                        out.append(('d', L.text(k), None))
            elif k.tag == 'section':
                out.append(('sec', '', None))
                walk(k)
            else:
                walk(k)
    walk(main)
    return out


INSTR = re.compile(r'(skal\b[^:]{0,60}?\blyde:|oppheves\.?|blir\s+(?:nytt?\s+)?(?:%s)(?:\s*,\s*(?:nytt?\s+)?(?:%s)|\s+og\s+(?:nytt?\s+)?(?:%s))*\s+(?:ledd|punktum)\.?|blir\s+ny\s+§)'
                   % (ORDRE, ORDRE, ORDRE))  # also "blir femte og nytt sjette ledd\"


TARGET = re.compile(r'^(?:\d+\.\s+|[IVX]+\.?\s+)?(?:I\s+)?(?:[Mm]idlertidig\s+)?(?:[Ll]ov|[Ll]ova|[Ll]oven|[A-ZÆØÅa-zæøå-]+(?:loven|lova|lov))\b[^:§]{0,300}?'
                    r'(?:(?:følgende|følgjande)\s+endring|endres\s+slik|blir\s+endra\s+slik|vert\s+endra\s+slik)')


WORDS = r'(?:(?:ordet|ordene|ordet|uttrykket|utrykket|uttrykkene|betegnelsen|betegnelsene|henvisningen(?:\s+til)?|henvisningene|navnet|nemninga)\s+)?'
CHG = r'(?:skal\s+)?(?:endres|endras|erstattes|endra|endret|vert\s+endra|vert\s+endret|blir\s+endret|blir\s+endra)\s+(?:til|med)'
SUBST_LIST = re.compile(r'^I\s+(?:følgende|følgjande)\s+(?:bestemmelser?|lovbestemmelser?|lovføresegner|føresegner|paragrafer)\b.*?«.+»\s*' + CHG + r'\s*«.+»[^«]*:\s*$')
SUBST_INLINE = re.compile(r'^(I lov [^§]*?)?\s*I?\s*§\s*(\d+[^«]*?)\s*(?:skal\s+)?' + WORDS + r'(«.+»\s*' + CHG + r'\s*«.+?»)\s*\.?$')
SUBST_VERB = re.compile(r'^(?:I\s+)?(§§?\s*\d+[^«:]*?)\s+(?:skal\s+)?((?:erstattes|endres|utgår|strykes)\s+(?:ordet\s+|ordene\s+|uttrykket\s+)?«.+)$')
LAW_LINE = re.compile(r'^(?:\d+\.\s+)?(?:[Mm]idlertidig\s+)?(?:lov|Lov)\s+\d+\.\s+\w+\s+\d{4}')
WARN = []


def subst_pairs(t):
    """'«A» og «B» endres til «C» og «D»' -> [('A', 'C'), ('B', 'D')]."""
    m = re.search(CHG, t)
    olds = re.findall(r'«([^»]+)»', t[:m.start()])
    news = re.findall(r'«([^»]+)»', t[m.end():])
    if len(news) == 1 and len(olds) > 1:  # '«A» eller «B» endres til «C»'
        news = news * len(olds)
    if len(olds) != len(news):
        raise ReplayError('substitution pairs do not match: ' + t)
    return list(zip(olds, news))


def subst_refs(t):
    """'§ 43 andre ledd første punktum, § 58 første ledd og andre ledd, § 60' -> [('43', [2]), ('58', [1, 2]), ('60', None)]."""
    out = []
    # '§§ 11, 101 og 194' -> '§ 11, § 101 og § 194'
    t = re.sub(r'§§\s*((?:\d+(?:\s?[a-z]\b)?(?:\s*,\s*|\s+og\s+))*\d+(?:\s?[a-z]\b)?)',
               lambda m: re.sub(r'(\d+(?:\s?[a-z]\b)?)', r'§ \1', m.group(1)), t)
    for part in re.split(r'(?=§\s*\d)', t):
        m = re.match(r'§\s*(\d+(?:\s?[a-z](?![a-zæøå]))?)(.*)$', part.strip())
        if not m:
            continue
        ledd = sorted({ORD[w] for w in re.findall(r'(%s)\s+(?:og\s+(?:%s)\s+)?ledd' % (ORDRE, ORDRE), m.group(2))} |
                      {ORD[w] for w in re.findall(r'(%s)\s+og\s+(?:%s)\s+ledd' % (ORDRE, ORDRE), m.group(2))} |
                      {ORD[w] for w in re.findall(r'(?:%s)\s+og\s+(%s)\s+ledd' % (ORDRE, ORDRE), m.group(2))})
        out.append((norm_num(m.group(1)), ledd or None))
    return out


def subst_op(src, num, ledd, pairs, target):
    return {'src': src, 'num': num, 'act': 'subst', 'pairs': pairs, 'subst_ledd': ledd, 'lang': None, 'ledd': None,
            'ledd_to': None, 'ledd_new': False, 'pkt': None, 'pkt_new': False, 'bokstav': None, 'bokstav_new': False,
            'semikolon': False, 'heading': None, 'target': target, 'payload': {}, 'new_para': False}


def _subst_text(s, op):
    """One pass, longest word first, so «legemet» -> «kroppen» wins over «legeme» -> «kropp»; words the
    amending text says to keep ('skal det fortsatt stå «sprenglegeme»') are left alone."""
    table = {}
    for a, b in op['pairs']:
        table[a] = b
        table[a[:1].upper() + a[1:]] = b[:1].upper() + b[1:]
    keep = sorted(op.get('keep', []), key=len, reverse=True)
    alts = keep + sorted(table, key=len, reverse=True)
    rx = re.compile('|'.join(re.escape(x) for x in alts))
    return rx.sub(lambda m: m.group(0) if m.group(0) in keep else table[m.group(0)], s)


def _apply_subst(item, op):
    hit = False
    for i, ld in enumerate(item['ledd']):
        if op['subst_ledd'] and i + 1 not in op['subst_ledd']:
            continue
        for j, line in enumerate(ld):
            new = _subst_text(line, op)
            if new != line:
                ld[j] = L.norm(new)
                hit = True
    if not op['subst_ledd'] and item.get('title'):
        new = _subst_text(item['title'], op)
        if new != item['title']:
            item['title'] = new
            hit = True
    if not hit:
        WARN.append('substitution found nothing: § %s %s' % (op['num'], op['src'][:120]))


TARGET_IN = re.compile(r'^(?:\d+\.\s+)?Med virkning fra .*?(?:følgende|følgjande) endring(?:er|ar)? i (.*)$')


def is_target(t):
    """'I lov 14. juni 2019 nr. 21 om arv ... gjøres følgende endringer:' (also numbered '1. I lov ...'), or
    'Med virkning fra ... gjøres følgende endringer i lov 22. mai 1902 nr. 13 militær straffelov:'."""
    return bool(TARGET.match(t) or TARGET_IN.match(t))


def target_of(t):
    """The words that name the amended act: for 'Med virkning fra ... endringer i <act>:', only <act>."""
    m = TARGET_IN.match(t)
    return m.group(1) if m else t


def is_instr(t):
    return bool(INSTR.search(t)) or t.startswith('Følgende bestemmelser skal på')


def parse_instr(t, last_num):
    """One instruction sentence -> list of op dicts (a sentence may hold two, joined by '. ')."""
    ops = []
    for part in re.split(r'(?<=\.)\s+(?=Nåværende)', t):
        ops.append(_parse_one(part.strip(), last_num))
        last_num = ops[-1]['num'] or last_num
    return ops


def _parse_one(t, last_num):
    op = {'src': t, 'num': None, 'new_para': False, 'lang': None, 'ledd': None, 'ledd_to': None, 'ledd_new': False,
          'pkt': None, 'pkt_new': False, 'bokstav': None, 'bokstav_new': False, 'semikolon': False, 'act': None,
          'heading': None}
    m = re.match(r'^(?:I lov [^§]*? skal\s+)?(?:Grunnloven\s+)?(Ny\s+|ny\s+|Nåværende\s+)?§\s*(\d+(?:\s?[a-z](?![a-zæøå]))?)\s*(.*)$', t)
    rest = t
    if m:
        op['num'] = norm_num(m.group(2))
        op['new_para'] = (m.group(1) or '').strip().lower() == 'ny'
        rest = m.group(3)
    elif t.startswith('Nåværende'):
        op['num'] = last_num
        rest = t[len('Nåværende'):]
    else:
        raise ReplayError('cannot read instruction: ' + t)
    if 'på bokmål før semikolon' in rest:
        op['semikolon'] = True
        rest = rest.replace('(på bokmål før semikolon)', '')
    lm = re.search(r'på\s+(bokmål|nynorsk)', rest)
    if lm:
        op['lang'] = 'bm' if lm.group(1) == 'bokmål' else 'nn'
    if re.search(r'\bnytt\s+siste\s+ledd\b', rest):
        rest = re.sub(r'\bnytt\s+siste\s+ledd\b', 'nytt tolvte ledd', rest)  # appended: any position past the end
    elif re.search(r'\bsiste\s+ledd\b', rest):
        op['last_ledd'] = True
        rest = re.sub(r'\bsiste\s+ledd\b', 'første ledd', rest)  # resolved to the real last ledd when applied
    OL = r'(?:%s)(?:(?:\s*,\s*|\s+og\s+|\s+til\s+)(?:nytt\s+)?(?:%s))*' % (ORDRE, ORDRE)
    mm = re.search(r'(nytt\s+)?(%s)\s+ledd' % OL, rest)
    if mm and 'blir' not in rest[:mm.start()]:
        ns = [ORD[w] for w in re.findall(ORDRE, mm.group(2))]
        op['ledd'] = ns[0]
        op['ledd_to'] = ns[-1] if len(ns) > 1 else None
        op['ledd_new'] = bool(mm.group(1))
    pm = re.search(r'(nytt\s+)?(%s)\s+punktum' % OL, rest)
    if pm and 'blir' not in rest[:pm.start()]:
        ns = [ORD[w] for w in re.findall(ORDRE, pm.group(2))]
        op['pkt'] = ns[0]
        op['pkt_to'] = ns[-1] if len(ns) > 1 else None
        op['pkt_new'] = bool(pm.group(1))
    bm = re.search(r'(ny\s+)?bokstav\s+([a-z])\)?((?:(?:\s*,\s*|\s+og\s+)(?:ny\s+)?(?:bokstav\s+)?[a-z]\b\)?)*)', rest)
    if not bm:
        bm = re.search(r'ledd\s+(ny\s+)?([a-z])\)()', rest)  # '§ 196 første ledd c) skal lyde:'
    op['intro'] = bool(re.search(r'\binnledningen\b', rest))
    if not bm:
        bm = re.search(r'(nytt?\s+)?nr\.\s*(\d+)((?:(?:\s*,\s*|\s+og\s+)(?:nytt?\s+)?(?:nr\.\s*)?\d+\b)*)', rest)
        if bm:
            op['bokstav'] = bm.group(2)
            op['bokstav_new'] = bool(bm.group(1))
            more = re.findall(r'(nytt?\s+)?(?:nr\.\s*)?(\d+)\b', bm.group(3) or '')
            op['bokstav_more'] = [(l, bool(n)) for n, l in more]
            bm = None
    if bm:
        op['bokstav'] = bm.group(2)
        op['bokstav_new'] = bool(bm.group(1))
        more = re.findall(r'(?:,\s*|\bog\s+)(ny\s+)?(?:bokstav\s+)?([a-z])\b', bm.group(3) or '')
        op['bokstav_more'] = [(l, bool(n)) for n, l in more]
    if re.search(r'\blyde:', t):
        op['act'] = 'set'
    elif re.search(r'oppheves', rest):
        op['act'] = 'del'
    elif re.search(r'blir\s+nytt?\s+(%s)\s+ledd\s+i\s+§\s*(\d+(?:\s?[a-z](?![a-zæøå]))?)' % ORDRE, rest):
        mv = re.search(r'blir\s+nytt?\s+(%s)\s+ledd\s+i\s+§\s*(\d+(?:\s?[a-z](?![a-zæøå]))?)' % ORDRE, rest)
        op['act'] = 'move'
        op['move_to'] = (norm_num(mv.group(2)), ORD[mv.group(1)])
    elif re.search(r'\bblir\b', rest):
        op['act'] = 'renum'
        rm = re.search(r'blir\s+(nytt?\s+)?(%s)\s+(ledd|punktum)' % ORDRE, rest)
        op['renum_to'] = (rm.group(3), ORD[rm.group(2)]) if rm else None
    else:
        raise ReplayError('no action in instruction: ' + t)
    return op


def split_payload(pl, op, nn_only, single_lang=None):
    """Payload blocks -> {'bm': [...], 'nn': [...]} of ('p', lines) / ('title', label) / ('head', num, title)."""
    if single_lang:
        return {single_lang: pl}
    dash = [i for i, b in enumerate(pl) if b[0] in ('d', 'p') and _btext(b) == '–']
    if dash:
        i = dash[0]
        return {'bm': pl[:i], 'nn': pl[i + 1:]}
    lang = op['lang'] or ('nn' if nn_only else None)
    if lang:
        return {lang: pl}
    heads = [i for i, b in enumerate(pl) if b[0] == 'head']
    if len(heads) == 2:
        return {'bm': pl[:heads[1]], 'nn': pl[heads[1]:]}
    if len(pl) % 2:
        raise ReplayError('cannot split payload in two languages: ' + op['src'])
    h = len(pl) // 2
    return {'bm': pl[:h], 'nn': pl[h:]}


def _btext(b):
    return b[1] if b[0] in ('d', 'title') else (' '.join(b[1]) if b[0] == 'p' else '')


def doc_ops(raw, only=None, single_lang=None, strict=True):
    """All instructions of an amending document, each with its payload split by language.

    `only(op)` may drop instructions aimed at other acts (decided by the caller from the intro sentence).
    `single_lang` ('bm'): an ordinary act published in one language, so payloads are not split."""
    bl = blocks(raw)
    ops, nn_only, last, cur_target = [], False, None, None
    subst = None  # (olds, news) while reading a list "I følgende bestemmelser skal «X» endres til «Y»:"
    i = 0
    while i < len(bl):
        b = bl[i]
        t = _btext(b)
        if b[0] == 'sec':
            subst = None
            cur_target = None
        if b[0] in ('d', 'p') and SUBST_LIST.match(t):
            subst = subst_pairs(t)
            i += 1
            continue
        if subst and b[0] in ('d', 'p'):
            if LAW_LINE.match(t):
                cur_target = target_of(t)
                i += 1
                continue
            if t.startswith('§'):
                for num, ledd in subst_refs(t):
                    ops.append(subst_op(t, num, ledd, subst, cur_target))
                i += 1
                continue
            subst = None
        if b[0] in ('d', 'p'):
            # 'I § 30, slik § 30 lyder etter endringer ved ..., skal første ledd bokstav g lyde:' -> '§ 30 første ledd bokstav g skal lyde:'
            t2 = re.sub(r'^I (§\s*%s),\s*slik [^,]*,\s*skal (.*?) lyde:' % NUM, r'\1 \2 skal lyde:', t)
            if t2 != t:
                t = t2
                bl[i] = (b[0], t, b[2]) if b[0] == 'd' else ('d', t, None)
                b = bl[i]
        m = re.match(r'^(?:\d+\.\s+)?(I\s+(?:midlertidig\s+)?lov\s.*?)\s+oppheves\s+(§§?\s*%s(?:(?:\s*,\s*|\s+og\s+|\s+til\s+)%s)*)\.?$' % (NUM, NUM), t) \
            if b[0] in ('d', 'p') else None
        if m:
            cur_target = m.group(1)
            ops.append(dict(struct_op(m.group(2) + ' oppheves.'), target=cur_target, payload={}))
            i += 1
            continue
        m = re.match(r'^I\s+§\s*(%s)\s+(?:(%s)\s+ledd\s+)?(?:bokstav\s+([a-z])\s+)?føyes\s+(§\s*%s)\s+til\s+i\s+opplistingen' % (NUM, ORDRE, NUM), t) \
            if b[0] in ('d', 'p') else None
        if m:
            ops.append({'act': 'list_ref', 'src': t, 'num': norm_num(m.group(1)), 'ledd': ORD[m.group(2)] if m.group(2) else None,
                        'letter': m.group(3), 'ref': m.group(4).replace('§', '').strip(), 'target': cur_target, 'lang': None,
                        'payload': {}, 'pkt': None, 'bokstav': None})
            last = norm_num(m.group(1))
            i += 1
            continue
        if b[0] in ('d', 'p') and SUBST_VERB.match(t):
            m = SUBST_VERB.match(t)
            # the source sometimes leaves out the quotes of the new word: '«legemet» med kroppen'
            pairs = [(a, b or c) for a, b, c in re.findall(r'«([^»]*)»\s+(?:med|til)\s+(?:«([^»]*)»|([\wæøåÆØÅ-]+))', m.group(2))]
            if m.group(2).startswith(('utgår', 'strykes')):
                pairs = [(x, '') for x in re.findall(r'«([^»]*)»', m.group(2))]
            if not pairs:
                ops.append({'act': 'error', 'src': t, 'error': 'cannot read substitution: ' + t, 'target': cur_target, 'num': None, 'lang': None})
            for num, ledd in subst_refs(m.group(1)):
                ops.append(subst_op(t, num, ledd, pairs, cur_target))
                last = num
            i += 1
            continue
        m = re.match(r'^I\s+§\s*(%s)[^«]*?skal det fortsatt stå\s+«([^»]+)»' % NUM, t) if b[0] in ('d', 'p') else None
        if m:
            for o in ops:
                if o['act'] == 'subst' and o['num'] == norm_num(m.group(1)):
                    o.setdefault('keep', []).append(m.group(2))
            i += 1
            continue
        m = re.match(r'^I\s+§\s*(%s)\s+(?:(%s)\s+ledd\s+)?føyes\s+det\s+til\s+(?:en\s+)?(?:ny\s+)?bokstav\s+([a-z]),?\s+som\s+skal\s+lyde:\s*(.*)$'
                     % (NUM, ORDRE), t) if b[0] in ('d', 'p') else None
        if m:
            pl, j = collect_payload(bl, i + 1)
            if m.group(4):
                pl = [('d', m.group(4), None)] + pl
            op = _parse_one('§ %s %sny bokstav %s skal lyde:' % (m.group(1), (m.group(2) + ' ledd ') if m.group(2) else '', m.group(3)), last)
            op.update(target=cur_target, payload={'bm': pl}, src=t)
            ops.append(op)
            last = op['num']
            i = j
            continue
        m = re.match(r'^Punktumet i bokstav ([a-z]) erstattes (?:av|med) et komma', t) if b[0] in ('d', 'p') else None
        if m:
            ops.append({'act': 'item_punct', 'src': t, 'num': last, 'letter': m.group(1), 'target': cur_target, 'lang': None,
                        'payload': {}, 'ledd': None, 'pkt': None, 'bokstav': None})
            i += 1
            continue
        if b[0] in ('d', 'p') and SUBST_INLINE.match(t):
            m = SUBST_INLINE.match(t)
            if m.group(1):
                cur_target = target_of(t)
            for num, ledd in subst_refs(m.group(2)):
                ops.append(subst_op(t, num, ledd, subst_pairs(m.group(3)), cur_target))
            i += 1
            continue
        if b[0] in ('d', 'p') and is_target(t):
            cur_target = target_of(t)
            i += 1
            continue
        if b[0] in ('d', 'p') and t.startswith('Følgende bestemmelser skal på nynorsk lyde'):
            nn_only = True
            i += 1
            continue
        if b[0] in ('d', 'p') and STRUCT.match(t):
            pl, j = collect_payload(bl, i + 1)
            try:
                op = struct_op(t)
            except ReplayError as e:
                op = {'act': 'error', 'src': t, 'error': str(e), 'num': None, 'lang': None}
            op['target'] = cur_target
            op['payload'] = {'bm': pl}
            ops.append(op)
            i = j
            continue
        if b[0] in ('d', 'p') and is_instr(t) and (t.startswith('§') or t.startswith('Ny') or t.startswith('ny ')
                                                 or t.startswith('Nåværende') or t.startswith('Grunnloven')
                                                 or (re.match(r'^(?:\d+\.\s+)?I lov ', t) and ' skal ' in t)):
            if re.match(r'^(?:\d+\.\s+)?I lov ', t):
                cur_target = target_of(t)
                t = re.sub(r'^\d+\.\s+', '', t)
            pl, j = collect_payload(bl, i + 1)
            try:
                parsed = parse_instr(t, last)
            except ReplayError as e:
                # kept, so that it stops the build only if it is aimed at the act being built
                ops.append({'act': 'error', 'src': t, 'error': str(e), 'target': cur_target, 'num': None, 'lang': None})
                i = j
                continue
            for op in parsed:
                op['target'] = cur_target
                prev = ops[-1] if ops else None
                if (op['src'].startswith('Nåværende') and op['ledd'] is None and op['pkt'] is not None and prev
                        and prev.get('num') == op['num'] and prev.get('ledd') is not None):
                    op['ledd'] = prev['ledd']  # 'Nåværende annet punktum blir ...' in the ledd just named
                try:
                    op['payload'] = split_payload(pl, op, nn_only, single_lang) if op['act'] == 'set' else {}
                except ReplayError as e:
                    op['payload'] = {'error': str(e)}
                if op['act'] != 'set' and not op['lang'] and nn_only:
                    op['lang'] = 'nn'
                last = op['num'] or last
                ops.append(op)
            i = j
            continue
        i += 1
    if only:
        ops = [o for o in ops if only(o)]
    for o in ops:
        if o['act'] == 'error':
            if strict:
                raise ReplayError(o['error'])
            WARN.append('instruction not read: ' + o['error'][:200])
    return [o for o in ops if o['act'] != 'error']


def collect_payload(bl, j):
    """The blocks after an instruction, up to the next instruction, target sentence or section."""
    pl = []
    while j < len(bl):
        if bl[j][0] == 'sec':
            break
        bt = _btext(bl[j])
        if bl[j][0] in ('d', 'p') and is_instr(bt) and (bt.startswith('§') or bt.startswith('Ny') or bt.startswith('Nåværende') or bt.startswith('Overskrift')
                                                       or bt.startswith('Følgende') or bt.startswith('I lov ') or bt.startswith('Grunnloven')):
            break
        if bl[j][0] in ('d', 'p') and (is_target(bt) or bt.startswith('Nåværende') or SUBST_LIST.match(bt)
                                       or SUBST_INLINE.match(bt) or STRUCT.match(bt) or SUBST_VERB.match(bt)
                                       or re.match(r'^(?:\d+\.\s+)?I\s+(?:§|lov\s)', bt) or bt.startswith('Punktumet')):
            break
        if bl[j][0] == 'd' and HEAD_RE.match(bt) and not is_instr(bt) and len(bt) < 12:
            pl.append(('head', bt, ''))
        else:
            pl.append(bl[j])
        j += 1
    return pl, j


# ---------------------------------------------------------------- structure: parts, chapters, headings, ranges
NUM = r'\d+(?:\s?[a-z](?![a-zæøå])(?!\s+lov\b))?'
STRUCT = re.compile(
    r'^(?:(?:Nytt|Ny|Nye)\s+kapit(?:tel|ler)\b|Kapittel\s+%s\s+(?:skal\s+lyde|oppheves)|Kapitlene\s|Lovens\s+\w+\s+del\s+skal\s+lyde'
    r'|(?:Etter\s+§\s*%s\s+skal\s+)?[Nn]y\s+(?:\w+\s+)?del\b.*lyde|(?:Ny\s+)?[Oo]verskrift(?:en)?\s+(?:til|i|for)\s'
    r'|§§\s.*oppheves|I\s+kapittel\s+%s\s+skal\s+ny\s+§|\w+\s+del\s+skal\s+lyde|(?:De delene av\s+)?§\s*%s\b[^:]*?\bblir\s+§\s*%s,?\s+og\s+skal\s+lyde'
    r'|I den alminnelige del(?:en)? fjernes alle punktum i paragrafoverskriftene'
    r'|Nåværende\s+§\s*%s\s+blir\s+(?:ny\s+)?§\s*%s\b.*skal\s+lyde|§\s*%s\s+overskriften\s+skal\s+lyde)' % (NUM, NUM, NUM, NUM, NUM, NUM, NUM, NUM))


def struct_op(t):
    op = {'src': t, 'num': None, 'lang': None, 'act': 'struct'}
    if t.startswith('I den alminnelige del'):
        op.update(kind='strip_title_dots', key='del-1')
        return op
    m = re.match(r'^§\s*(%s)\s+overskriften\s+skal\s+lyde' % NUM, t)
    if m:
        op.update(kind='para_title', num=norm_num(m.group(1)))
        return op
    m = re.match(r'^(?:De delene av\s+|Nåværende\s+)?§\s*(%s)\b[^:]*?\bblir\s+(?:ny\s+)?§\s*(%s)\b.*?skal\s+lyde' % (NUM, NUM), t)
    if m:
        op.update(kind='renumber', old=norm_num(m.group(1)), num=norm_num(m.group(2)))
        return op
    m = re.match(r'^(\w+)\s+del\s+skal\s+lyde', t)
    if m and m.group(1).lower() in L.PART_ORD:
        op.update(kind='replace_part', key=L.head_key(m.group(1).capitalize() + ' del'))
        return op
    m = re.match(r'^I\s+kapittel\s+(%s)\s+skal\s+ny\s+§\s*(%s)\s+lyde' % (NUM, NUM), t)
    if m:
        op.update(kind='para', chap=L.head_key('Kapittel ' + m.group(1).replace(' ', '')), num=norm_num(m.group(2)))
        return op
    m = re.match(r'^§§?\s+(.*?)\s+oppheves', t)
    if m:
        op.update(kind='del_paras', ranges=para_ranges(m.group(1)))
        return op
    m = re.match(r'^Kapittel\s+(%s)\s+oppheves' % NUM, t)
    if m:
        op.update(kind='del_chapter', key=L.head_key('Kapittel ' + m.group(1).replace(' ', '')))
        return op
    m = re.match(r'^Kapittel\s+(%s)\s+skal\s+lyde' % NUM, t)
    if m:
        op.update(kind='replace_chapter', key=L.head_key('Kapittel ' + m.group(1).replace(' ', '')))
        return op
    m = re.match(r'^Lovens\s+(\w+)\s+del\s+skal\s+lyde', t)
    if m:
        op.update(kind='replace_part', key=L.head_key(m.group(1).capitalize() + ' del'))
        return op
    m = re.match(r'^(?:Ny\s+)?[Oo]verskrift(?:en)?\s+(?:til|i|for)\s+(?:nytt\s+|ny\s+)?(.*?)\s+skal\s+lyde', t)
    if m:
        what = m.group(1)
        pm = re.match(r'^§\s*(%s)$' % NUM, what)
        if pm:
            op.update(kind='para_title', num=norm_num(pm.group(1)))
            return op
        km = re.match(r'^kapittel\s+([A-Z])$', what)
        if km:
            op.update(kind='heading', key='kapittel-' + km.group(1).lower())
            return op
        km = re.match(r'^kapittel\s+(%s)$' % NUM, what)
        if km:
            op.update(kind='heading', key=L.head_key('Kapittel ' + km.group(1).replace(' ', '')))
            return op
        km = re.match(r'^(\w+)\s+kapittel$', what)  # 'femte kapittel'
        if km and km.group(1) in ORD:
            op.update(kind='heading', key='kapittel-%02d' % ORD[km.group(1)])
            return op
        km = re.match(r'^(\w+)\s+del$', what)
        if km:
            op.update(kind='heading', key=L.head_key(km.group(1).capitalize() + ' del'))
            return op
        raise ReplayError('cannot read heading instruction: ' + t)
    if re.match(r'^(?:Nytt|Ny|Nye)\s+kapit', t) or re.search(r'[Nn]y\s+(?:\w+\s+)?del\b', t):
        op.update(kind='add')
        return op
    raise ReplayError('cannot read structure instruction: ' + t)


def _numkey(num):
    m = re.match(r'^(\d+)\s*([a-z]?)$', num.strip())
    return (int(m.group(1)), m.group(2))


def para_ranges(s):
    """'80 til 86 og §§ 90 til 94 a' / '80-86' / '1, 2, 3 og 18' -> [((80,''),(86,'')), ...]"""
    s = s.replace('§§', ' ').replace('§', ' ')
    out = []
    for part in re.split(r'\s*,\s*|\s+og\s+', s.strip()):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'^(%s)\s*(?:til|-|–)\s*(%s)$' % (NUM, NUM), part)
        if m:
            out.append((_numkey(m.group(1)), _numkey(m.group(2))))
        elif re.match(r'^%s$' % NUM, part):
            out.append((_numkey(part), _numkey(part)))
        else:
            raise ReplayError('cannot read paragraph range: ' + s)
    return out


def payload_items(pl, chapter=None):
    """Whole chapters or parts in a payload -> [(key, item)] in order, each paragraph with its chapter."""
    items, cur = [], None
    for b in pl:
        if b[0] == 'title':
            lab = b[1]
            hk = L.head_key(lab, chapter)
            if hk is None:
                raise ReplayError('unknown heading in payload: ' + lab)
            items.append((hk, {'t': 'h', 'label': lab, 'parent': None}))
            if hk.startswith('kapittel-'):
                chapter = hk
            cur = None
        elif b[0] == 'head':
            m = re.match(r'^§\s*(%s)\s*\.?\s*(.*)$' % NUM, b[1])
            if not m:
                raise ReplayError('cannot read paragraph heading in payload: ' + b[1])
            num = norm_num(m.group(1))
            cur = para(num, b[2] or m.group(2).strip(' .'), [])
            cur['chap'] = chapter
            items.append((L.para_key(num), cur))
        elif b[0] == 'p' and cur is not None:
            cur['ledd'].append(list(b[1]))
        elif b[0] == 'd' and cur is not None and b[1] and b[1] != '–':
            cur['ledd'].append([b[1]])
    return items


def members(state, key):
    """Keys inside a chapter (its paragraphs and sub-sections) or a part (its chapters and their contents)."""
    out = set()
    if key.startswith('kapittel-'):
        for k, v in state.items():
            c = v.get('chap') if v['t'] == 'p' else v.get('parent')
            if c and (c == key or c.startswith(key + '-avsnitt-')):
                out.add(k)
            if v['t'] == 'h' and k.startswith(key + '-avsnitt-'):
                out.add(k)
    else:
        chs = {k for k, v in state.items() if v['t'] == 'h' and v.get('parent') == key}
        out |= chs
        for c in chs:
            out |= members(state, c)
    return out


def apply_struct(state, op, lang):
    kind = op['kind']
    pl = op['payload'].get(lang, [])
    if kind == 'del_paras':
        hit = [k for k, v in state.items() if v['t'] == 'p' and any(a <= _numkey(v['num']) <= b for a, b in op['ranges'])]
        if not hit:
            raise ReplayError('no paragraphs to repeal: ' + op['src'])
        for k in hit:
            del state[k]
    elif kind == 'del_chapter':
        for k in members(state, op['key']) | {op['key']}:
            state.pop(k, None)
    elif kind in ('replace_chapter', 'replace_part', 'add'):
        parent = None
        if kind in ('replace_chapter', 'replace_part'):
            if op['key'] not in state:
                raise ReplayError('no such chapter or part: ' + op['src'])
            parent = state[op['key']].get('parent')
            for k in members(state, op['key']) | {op['key']}:
                del state[k]
        part = parent
        for k, it in payload_items(pl):
            if it['t'] == 'h':
                if k.startswith('del-'):
                    part = k
                    it['parent'] = None
                elif '-avsnitt-' in k:
                    it['parent'] = k.split('-avsnitt-')[0]
                else:
                    it['parent'] = part or _guess_part(state, k)
            state[k] = it
    elif kind == 'heading':
        if op['key'] not in state:
            raise ReplayError('no such heading: ' + op['src'])
        lab = next((b[1] for b in pl if b[0] in ('title', 'd') and b[1] and b[1] != '–'), None)
        if lab is None:
            raise ReplayError('no heading text: ' + op['src'])
        state[op['key']] = dict(state[op['key']], label=lab)
    elif kind == 'para_title':
        k = L.para_key(op['num'])
        if k not in state:
            raise ReplayError('§ %s is not in the text (%s)' % (op['num'], op['src']))
        txt = next((b[1] for b in pl if b[0] in ('title', 'd') and b[1] and b[1] != '–'), None)
        if txt is None:
            txt = next((b[2] for b in pl if b[0] == 'head' and b[2]), None)
        if txt is None:
            raise ReplayError('no title text: ' + op['src'])
        state[k] = dict(state[k], title=txt)
    elif kind == 'strip_title_dots':
        inpart = members(state, op['key'])
        for k in inpart:
            v = state[k]
            if v['t'] == 'p' and v['title'].endswith('.') and not re.search(r'\b(?:mv|m\.m|osv|o\.l|m\.v)\.$', v['title']):
                state[k] = dict(v, title=v['title'].rstrip('.').rstrip())
    elif kind == 'renumber':
        old = state.pop(L.para_key(op['old']), None)
        if old is None:
            raise ReplayError('§ %s is not in the text (%s)' % (op['old'], op['src']))
        ledd, title = payload_ledd(pl)
        it = para(op['num'], title if title is not None else old['title'], ledd)
        before = [k for k, v in state.items() if v['t'] == 'p' and k < L.para_key(op['num']) and 'chap' in v]
        it['chap'] = state[max(before)]['chap'] if before else old.get('chap')
        state[L.para_key(op['num'])] = it
    elif kind == 'para':
        ledd, title = payload_ledd(pl)
        it = para(op['num'], title or '', ledd)
        it['chap'] = op['chap']
        state[L.para_key(op['num'])] = it
    else:
        raise ReplayError('unknown structure op: ' + kind)


def _guess_part(state, chap_key):
    """The part of the nearest existing chapter before `chap_key`."""
    best = None
    for k, v in state.items():
        if v['t'] == 'h' and k.startswith('kapittel-') and '-avsnitt-' not in k and k < chap_key:
            if best is None or k > best[0]:
                best = (k, v.get('parent'))
    return best[1] if best else None


# ---------------------------------------------------------------- applying
def payload_ledd(pl):
    out, title = [], None
    for b in pl:
        if b[0] == 'p':
            out.append(list(b[1]))
        elif b[0] == 'd' and b[1] and b[1] != '–':
            out.append([b[1]])
        elif b[0] == 'head':
            title = b[2] or title
    return out, title


def apply_ops(state, ops, lang):
    """Apply one document's ops for one language ('bm' or 'nn'). Returns the set of keys changed."""
    changed = set()
    by_num = {}
    moved = []
    # renumbering refers to the numbers before the amendment, so it goes before new chapters reuse them
    for op in sorted([o for o in ops if o['act'] == 'struct'], key=lambda o: o['kind'] != 'renumber'):
        if not (op['lang'] and op['lang'] != lang):
            apply_struct(state, op, lang)
    ops = [o for o in ops if o['act'] != 'struct']
    for op in ops:
        if op['act'] != 'move' or (op['lang'] and op['lang'] != lang):
            moved.append(op)
            continue
        # a ledd moved to another paragraph: repeal it here, insert it there
        src = state.get(L.para_key(op['num']))
        if src is None or op['ledd'] is None or op['ledd'] > len(src['ledd']):
            raise ReplayError('cannot move: ' + op['src'])
        lines = src['ledd'][op['ledd'] - 1]
        dest, pos = op['move_to']
        moved.append(dict(op, act='del'))
        moved.append(dict(op, act='set', num=dest, ledd=pos, ledd_to=None, ledd_new=True, pkt=None, bokstav=None,
                          payload={lang: [('p', list(lines), None)]}))
    ops = moved
    for op in ops:
        if op['lang'] and op['lang'] != lang:
            continue
        if op['act'] == 'set' and lang not in op['payload']:
            if 'error' in op['payload']:
                raise ReplayError(op['payload']['error'])
            continue
        by_num.setdefault(op['num'], []).append(op)
    for num, lst in by_num.items():
        key = L.para_key(num)
        before = copy.deepcopy(state.get(key))
        _apply_para(state, key, num, lst, lang)
        if state.get(key) != before:
            changed.add(key)
    return changed


def _apply_para(state, key, num, ops, lang):
    for o in [o for o in ops if o['act'] == 'list_ref']:
        # 'føyes § 238 til i opplistingen': the number goes into the list of § numbers in its numeric place
        if key not in state:
            raise ReplayError('§ %s is not in the text (%s)' % (num, o['src']))
        item = copy.deepcopy(state[key])
        lds = [item['ledd'][(o['ledd'] or 1) - 1]] if o['ledd'] else item['ledd']
        done = False
        x = int(re.match(r'\d+', o['ref']).group(0))
        for ld in lds:
            for j, line in enumerate(ld):
                if o['letter'] and not re.match(r'^%s[).]\s' % o['letter'], line):
                    continue
                nums = [(mm.start(), mm.end(), int(mm.group(1))) for mm in re.finditer(r'(?<![\d-])(\d+)(?![\d-]| ledd| år| dager)', line)]
                for (s1, e1, a), (s2, e2, c) in zip(nums, nums[1:]):
                    between = line[e1:s2]
                    if a < x < c and re.fullmatch(r',\s*', between):
                        ld[j] = line[:e1] + ', ' + o['ref'] + line[e1:]
                        done = True
                        break
                if done:
                    break
            if done:
                break
        if not done:
            raise ReplayError('no place for § %s in the list (%s)' % (o['ref'], o['src']))
        state[key] = item
    ops = [o for o in ops if o['act'] != 'list_ref']
    for o in [o for o in ops if o['act'] == 'item_punct']:
        if key not in state:
            raise ReplayError('§ %s is not in the text (%s)' % (num, o['src']))
        item = copy.deepcopy(state[key])
        for ld in item['ledd']:
            for j, line in enumerate(ld):
                if re.match(r'^%s[).]\s' % o['letter'], line) and line.endswith('.'):
                    ld[j] = line[:-1] + ','
        state[key] = item
    ops = [o for o in ops if o['act'] != 'item_punct']
    subs = [o for o in ops if o['act'] == 'subst']
    ops = [o for o in ops if o['act'] != 'subst']
    if subs:
        if key not in state:
            raise ReplayError('§ %s is not in the text (%s)' % (num, subs[0]['src'][:120]))
        item = copy.deepcopy(state[key])
        for o in subs:
            _apply_subst(item, o)
        state[key] = item
    if not ops:
        return
    # whole-paragraph ops first
    for op in ops:
        if op['ledd'] is None and op['pkt'] is None and op['bokstav'] is None and not op.get('intro'):
            if op['act'] == 'set':
                ledd, title = payload_ledd(op['payload'][lang])
                old = state.get(key)
                state[key] = para(num, title if title is not None else (old['title'] if old else ''), ledd)
                if old and 'chap' in old:
                    state[key]['chap'] = old['chap']
                elif old is None:
                    before = [k for k, v in state.items() if v['t'] == 'p' and k < key and 'chap' in v]
                    if before:
                        state[key]['chap'] = state[max(before)]['chap']
                return
            if op['act'] == 'del':
                state.pop(key, None)
                return
    item = state.get(key)
    if item is None:
        raise ReplayError('§ %s is not in the text (%s)' % (num, ops[0]['src']))
    ops = [dict(o, ledd=len(item['ledd'])) if o.get('last_ledd') else o for o in ops]
    renums = [op for op in ops if op['act'] == 'renum']
    # "andre ledd tredje punktum skal lyde: ..." with "Nåværende andre ledd tredje punktum blir nytt fjerde punktum"
    # in the same law: the new sentence is inserted, the old one moves on (as becomes_insert does for ledd)
    ops = [dict(o, pkt_new=True) if o['act'] == 'set' and o.get('pkt') is not None and not o.get('pkt_new')
           and any(r.get('pkt') == o['pkt'] and r['ledd'] == o['ledd'] and r.get('renum_to')
                   and r['renum_to'][0] == 'punktum' for r in renums) else o for o in ops]
    slots = [{'orig': i, 'ledd': l, 'dead': False} for i, l in enumerate(item['ledd'])]
    inserts = []
    for op in ops:
        if op['act'] == 'renum':
            continue
        if op.get('intro') and op['act'] == 'set' and op['bokstav'] is None:
            # 'første ledd innledningen skal lyde:': the words before the list
            k = (op['ledd'] or 1) - 1
            tgt = [s for s in slots if s['orig'] == k]
            if not tgt:
                raise ReplayError('no such ledd for: ' + op['src'])
            txt = ' '.join(l for ld in payload_ledd(op['payload'][lang])[0] for l in ld)
            tgt[0]['ledd'] = [txt] + list(tgt[0]['ledd'][1:])
            continue
        if op['ledd'] is not None and op['pkt'] is None and op['bokstav'] is None:
            k = op['ledd'] - 1
            becomes_insert = any(r['ledd'] == op['ledd'] and r.get('renum_to') and r['renum_to'][0] == 'ledd' for r in renums)
            if op['act'] == 'set' and (op['ledd_new'] or becomes_insert):
                inserts.append((k, payload_ledd(op['payload'][lang])[0]))
                continue
            hi = (op['ledd_to'] or op['ledd']) - 1
            # ledd that another instruction of the same law renumbers ("nåværende fjerde og femte ledd blir femte og
            # nytt sjette ledd") move on; they are not replaced by a range like "første til fjerde ledd skal lyde"
            moved = {i for r in renums if r['ledd'] is not None
                     for i in range(r['ledd'] - 1, (r.get('ledd_to') or r['ledd']))}
            targets = [s for s in slots if s['orig'] is not None and k <= s['orig'] <= hi
                       and not (op['act'] == 'set' and s['orig'] in moved)]
            if op['act'] == 'del':
                if not targets:
                    raise ReplayError('no such ledd: ' + op['src'])
                for s in targets:
                    s['dead'] = True
            else:
                new = payload_ledd(op['payload'][lang])[0]
                if not targets:
                    if k == len(item['ledd']):
                        inserts.append((k, new))
                        continue
                    raise ReplayError('no such ledd: ' + op['src'])
                at = slots.index(targets[0])
                for s in targets:
                    s['dead'] = True
                for j, l in enumerate(new):
                    slots.insert(at + j, {'orig': None, 'ledd': l, 'dead': False})
        else:
            k = (op['ledd'] or 1) - 1
            tgt = [s for s in slots if s['orig'] == k]
            if not tgt:
                raise ReplayError('no such ledd for: ' + op['src'])
            s = tgt[0]
            s['ledd'] = list(s['ledd'])
            if op['bokstav'] is not None:
                _apply_item(s, op, lang)
            else:
                s.setdefault('pkt_ops', []).append(op)
    for s in slots:
        if s.get('pkt_ops'):
            s['ledd'][0] = _apply_sentences(s['ledd'][0], s['pkt_ops'], lang, num)
    live = [s for s in slots if not s['dead']]
    for k, new in sorted(inserts, key=lambda x: x[0]):
        for j, l in enumerate(new):
            live.insert(min(k + j, len(live)), {'orig': None, 'ledd': l, 'dead': False})
    item = dict(item)
    item['ledd'] = [s['ledd'] for s in live]
    state[key] = item


def _apply_item(slot, op, lang):
    lines = slot['ledd']
    items = lines[1:]
    labels = [re.match(r'^([a-z]|\d+)([).])\s', x) for x in items]
    style = next((m.group(2) for m in labels if m), ')')
    letters = [(op['bokstav'], op['bokstav_new'])] + op.get('bokstav_more', [])
    if op['act'] == 'del':
        for letter, _ in letters:
            idx = [i for i, x in enumerate(items) if re.match(r'^%s[).]\s' % letter, x)]
            if not idx:
                raise ReplayError('no bokstav ' + letter + ': ' + op['src'])
            del items[idx[0]]
    else:
        pl = payload_ledd(op['payload'][lang])[0]
        texts = [l for ld in pl for l in ld]
        texts = [re.sub(r'^(?:[a-z]|\d+)[).]\s+', '', t) for t in texts]
        if len(letters) == 1:
            texts = [' '.join(texts)]
        if len(texts) != len(letters):
            raise ReplayError('%d letters, %d texts: %s' % (len(letters), len(texts), op['src']))
        for (letter, is_new), txt in zip(letters, texts):
            new = letter + style + ' ' + txt
            idx = [i for i, x in enumerate(items) if re.match(r'^%s[).]\s' % letter, x)]
            if idx and not is_new:
                items[idx[0]] = new
            elif idx and is_new:
                items.insert(idx[0], new)
            else:
                def lab_lt(x):
                    m = re.match(r'^([a-z]|\d+)[).]\s', x)
                    if not m:
                        return False
                    a = m.group(1)
                    return int(a) < int(letter) if a.isdigit() and letter.isdigit() else a < letter
                pos = len([x for x in items if lab_lt(x)])
                items.insert(pos, new)
    slot['ledd'] = [lines[0]] + items


def _apply_sentences(line, ops, lang, num):
    sl = [{'orig': i, 's': s, 'dead': False} for i, s in enumerate(sentences(line))]
    inserts = []
    for op in ops:
        if op['act'] == 'renum':
            continue
        k = op['pkt'] - 1
        if op['act'] == 'set':
            pl = payload_ledd(op['payload'][lang])[0]
            txt = ' '.join(l for ld in pl for l in ld)
            if op['pkt_new']:
                inserts.append((k, txt))
                continue
            tgt = [s for s in sl if s['orig'] == k]
            if not tgt:
                if k == len(sl):
                    inserts.append((k, txt))
                    continue
                raise ReplayError('§ %s: no punktum %d (%s)' % (num, k + 1, op['src']))
            if op['semikolon'] and lang == 'bm':
                s = tgt[0]['s']
                if ';' not in s:
                    raise ReplayError('§ %s: no semicolon (%s)' % (num, op['src']))
                tgt[0]['s'] = txt + s[s.index(';'):]
            else:
                tgt[0]['s'] = txt
            for s in sl:
                if op.get('pkt_to') and k < (s['orig'] if s['orig'] is not None else -1) <= op['pkt_to'] - 1:
                    s['dead'] = True
        elif op['act'] == 'del':
            hi = (op.get('pkt_to') or op['pkt']) - 1
            tgt = [s for s in sl if s['orig'] is not None and k <= s['orig'] <= hi]
            if not tgt:
                raise ReplayError('§ %s: no punktum %d (%s)' % (num, k + 1, op['src']))
            for s in tgt:
                s['dead'] = True
    live = [s for s in sl if not s['dead']]
    for k, txt in sorted(inserts):
        live.insert(min(k, len(live)), {'orig': None, 's': txt, 'dead': False})
    return ' '.join(s['s'] for s in live)
