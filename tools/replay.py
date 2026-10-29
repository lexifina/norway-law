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
import copy, difflib, re
import lovdata as L

ORD = {'første': 1, 'annet': 2, 'andre': 2, 'tredje': 3, 'fjerde': 4, 'femte': 5, 'sjette': 6, 'sjuende': 7,
       'syvende': 7, 'åttende': 8, 'niende': 9, 'tiende': 10, 'ellevte': 11, 'tolvte': 12,
       # nynorsk ("§ 14-3 fyrste ledd skal lyde:", "nytt sjuande ledd")
       'fyrste': 1, 'sjuande': 7, 'åttande': 8, 'niande': 9, 'tiande': 10}
ORDRE = '|'.join(sorted(ORD, key=len, reverse=True))
ORDN_EN = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth',
           10: 'tenth'}
# an instruction that names only a ledd and continues the paragraph just named: "Annet ledd oppheves."
LEDD_ONLY = re.compile(r'^(?:%s)\s+ledd\b[^:§]*\b(?:oppheves\.?|skal\s+lyde:)' % '|'.join(
    w.capitalize() for w in sorted(ORD, key=len, reverse=True)))
HEAD_RE = re.compile(r'^§\s*(\d+(?:\s?[a-z])?)\s*\.?\s*(.*)$')
ABBR = {'jf.', 'nr.', 'bl.a.', 'f.eks.', 'ca.', 'pkt.', 'dvs.', 'mv.', 'm.v.', 'osv.', 'kgl.', 'res.', 'Dok.', 'tlf.'}
# abbreviations that also end a sentence: "... til åndsverk m.v. Forskrifter gitt ..." is two punktum (åndsverkloven
# § 118 andre ledd andre punktum)
ABBR_END = {'mv.', 'm.v.', 'osv.', 'm.m.'}


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
        if nxt and ((last in ABBR and not (last in ABBR_END and re.match(r'^[A-ZÆØÅ][a-zæøå]+\s+[a-zæøå]', nxt)))
                    or not re.match(r'^[«("]?[A-ZÆØÅ§]', nxt)):  # "§ 5-5 gjelder tilsvarende." starts one
            continue
        out.append(cur)
        cur = ''
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- blocks of an amending document
BLOCK = {'defaultP', 'legalP', 'numberedLegalP', 'centeredP', 'futuretitle', 'futureLegalArticleHeader', 'leddfortsettelse'}


def blocks(raw):
    root = L.dom(raw)
    main = root.first(lambda n: n.tag == 'main')
    out = []

    def walk(n):
        for k in n.elems():
            if L.is_list(k) and n.has('futureLegalArticle'):
                # a new paragraph whose text is a list with no words before it: one ledd of the list's lines, as
                # lovdata.walk_act reads the act's own text
                out.append(('p', L.list_lines(k), None))
                continue
            c = set(k.cls) & BLOCK
            if c:
                c = c.pop()
                if c == 'futureLegalArticleHeader':
                    v = k.first(lambda x: x.has('legalArticleTitle'))
                    title = L.text(v) if v is not None else ''
                    num = L.text(k, stop=lambda x: x.has('legalArticleTitle')).replace('§', '').strip(' .')
                    out.append(('head', '§ ' + num, title))
                elif c in ('legalP', 'numberedLegalP'):
                    # numberedLegalP: a ledd printed with its number "(2) ..." (acts that number their ledd)
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
                        # a ledd's text after its list ("leddfortsettelse") is marked, so it joins that ledd
                        t = L.text(k)
                        if c == 'defaultP' and re.search(r'(?:^|\.\s+)Någjeldende\s', t):
                            # "Någjeldende fjerde ledd blir nytt femte ledd." (arbeidsmiljøloven, lov 23. februar 2007
                            # nr. 10): "Nåværende"
                            t = re.sub(r'(^|\.\s+)Någjeldende(?=\s)', r'\1Nåværende', t)
                        if c == 'defaultP' and re.match(r'^(?:Det\s+)?[Gg]jeldende\s+(?:\w+\s+ledd\s+)?bokstav\s+[a-z]\b.*\bblir\b', t):
                            t = re.sub(r'^(?:Det\s+)?[Gg]jeldende\s+', 'Nåværende ', t)  # a letter renumbering
                        _ren = r'(?:%s)\s+(?:ledd|punktum)\s+(?:vert|blir)\s+(?:nytt?\s+)?(?:%s)\s+(?:ledd|punktum)' % (ORDRE, ORDRE)
                        if c == 'defaultP' and re.match(r'^Noverande\s+%s(?:,?\s+og\s+noverande\s+%s)*\.?$' % (_ren, _ren), t):
                            # nynorsk renumbering in a bokmål law ("Noverande andre ledd vert nytt tredje ledd.", "Noverande
                            # andre ledd blir nytt fjerde ledd, og noverande tredje ledd blir nytt femte ledd.", lov 10.
                            # april 2019 nr. 13)
                            t = re.sub(r'\svert\s', ' blir ', re.sub(r'(^|\s)([Nn])overande\s', lambda m: m.group(1) + (
                                'Nåværende ' if m.group(2) == 'N' else 'nåværende '), t))
                        mm2 = c == 'defaultP' and re.match(
                            r'^Nåværende\s+(%s)\s+(ledd|punktum)\s+blir\s+(?:nytt?\s+)?(%s)\s+\2,?\s+og\s+nåværende\s+(%s)\s+\2'
                            r'\s+blir\s+(?:nytt?\s+)?(%s)\s+\2\.?$' % (ORDRE, ORDRE, ORDRE, ORDRE), t)
                        if mm2 and ORD[mm2.group(1)] < ORD[mm2.group(4)] and ORD[mm2.group(3)] < ORD[mm2.group(5)]:
                            # "Nåværende andre ledd blir nytt fjerde ledd, og nåværende tredje ledd blir nytt femte ledd."
                            # (eierseksjonsloven § 38, lov 10. april 2019 nr. 13): both renumberings, as "Nåværende andre
                            # og tredje ledd blir fjerde og femte ledd."
                            t = 'Nåværende %s og %s %s blir %s og %s %s.' % (mm2.group(1), mm2.group(4), mm2.group(2),
                                                                         mm2.group(3), mm2.group(5), mm2.group(2))
                        elif c == 'defaultP' and re.match(r'^Noverande\s+§\s*\d[^:«]*\svert\s+(?:nytt?\s+|nye\s+)?(?:(?:%s)\s+(?:ledd|punktum)|§\s*\d[^:«]*)\.?$' % ORDRE, t):
                            # "Noverande § 15-4 fyrste ledd andre punktum vert nytt tredje punktum." (nynorsk law)
                            t = re.sub(r'\svert\s', ' blir ', re.sub(r'^Noverande\s', 'Nåværende ', t))
                        if c == 'defaultP' and re.match(r'^§\s*\d[^:«]*\s(?:vert|blir)\s+oppheva\.?$', t):
                            # "§ 10-5 andre ledd bokstav i vert oppheva.", "§ 25 første ledd tredje og fjerde punktum blir
                            # oppheva." (lov 4. desember 2020 nr. 137)
                            t = re.sub(r'\s(?:vert|blir)\s+oppheva(\.?)$', r' oppheves\1', t)
                        if c == 'defaultP' and re.match(r'^Nåværende\s.*\bblir\s+til\s+nytt?\s', t):
                            t = re.sub(r'\bblir\s+til\s+(nytt?\s)', r'blir \1', t)  # "blir til nytt sjette ledd"
                        if c == 'defaultP' and L.CHAPNUM and re.search(r'§\s*\d{1,2}-[A-Z]\d{1,3}\b', t):
                            # "I § 28-A1 tredje ledd ..." (tvisteloven, lov 22. april 2016 nr. 3): § 28 A-1
                            t = re.sub(r'(§\s*)(\d{1,2})-([A-Z])(\d{1,3})\b',
                                       lambda m: m.group(1) + L.enc('%s %s-%s' % (m.group(2), m.group(3), m.group(4))), t)
                        if c == 'defaultP' and re.match(r'^§\s.*\sstrykes\.?$', t):
                            t = re.sub(r'\sstrykes(\.?)$', r' oppheves\1', t)  # "§ 156 første ledd annet punktum strykes."
                        if c == 'defaultP' and re.match(r'^Nytt\s+§\s*%s\s+(?:%s)\s+ledd\s+skal\s+lyde:?$' % (NUM, ORDRE), t):
                            # "Nytt § 6-7 fjerde ledd skal lyde:" (eiendomsmeglingsloven, lov 3. september 2010 nr. 54)
                            t = re.sub(r'^Nytt\s+(§\s*\S+(?:\s[a-z](?=\s))?)\s+', r'\1 nytt ', t)
                        if c == 'defaultP' and re.search(r'\b[Ll]ov\s+av\s+\d{1,2}\.\s+\w+\s+\d{4}\s+nr\.', t):
                            # "26. I lov av 29. juni 2007 nr. 73 om eiendomsmegling, skal § 2-3 nytt fjerde ledd lyde:"
                            # (lov 19. juni 2009 nr. 103): "lov 29. juni 2007 nr. 73"
                            t = re.sub(r'\b([Ll]ov)\s+av\s+(?=\d{1,2}\.\s+\w+\s+\d{4}\s+nr\.)', r'\1 ', t)
                        m2 = c == 'defaultP' and re.match(r'^(Nåværende\s+§\s*%s\s+oppheves\.)\s+((?:Nåværende|Gjeldende)\s+§.*)$'
                                                          % NUM, t)
                        if m2 and move_pairs(m2.group(2)):
                            # "Nåværende § 6-10 oppheves. Nåværende §§ 6-8 og 6-9 blir §§ 6-9 og 6-10." in one paragraph
                            # (eiendomsmeglingsloven, lov 10. april 2025 nr. 10): two instructions
                            out.append(('d', m2.group(1), None))
                            out.append(('d', m2.group(2), None))
                            continue
                        out.append(('d', t, 'cont' if c == 'leddfortsettelse' else None))
            elif k.tag == 'section':
                # an amending law's own parts ("I", "II" ...): <section data-name="kapII"><h2>II</h2>; the numeral
                # rides along (b[2]) so in-force sentences "Endringen under II ..." can find the part
                h2 = [x for x in k.elems() if x.tag == 'h2']
                lab = L.text(h2[0]).strip(' .') if h2 else ''
                out.append(('sec', '', lab if re.fullmatch(r'[IVXL]+', lab) else None))
                walk(k)
            else:
                walk(k)
    walk(main)
    # a numbered law item printed glued to the end of the previous payload paragraph ("... etter § 16-6.237. I lov
    # 19. juni 2009 nr. 97 om dyrevelferd gjøres følgende endring:", LOV-2015-06-19-65): split it off as the target
    # sentence it is
    fixed = []
    for b in out:
        if b[0] == 'p' and isinstance(b[1], list) and b[1]:
            m = re.match(r'^(.*?[.:;])(\d+\.\s+I\s+lov\s+\d+\.\s+\w+\s+\d{4}\s+nr\.\s*\d+\b[^:]*\bgjøres\s+følgende\s+endring(?:er|ar)?:)$',
                         b[1][-1], re.S)
            if m:
                fixed.append((b[0], list(b[1][:-1]) + [m.group(1)]) + tuple(b[2:]))
                fixed.append(('d', m.group(2), None))
                continue
        fixed.append(b)
    # "I kapitlene 34 og 35 skal følgende paragrafer lyde:" (plan- og bygningsloven, LOV-2009-05-08-27): the paragraphs
    # printed after it, between the law's other instructions, each read as "§ N skal lyde:"
    # "§ 6-4 tredje ledd skal lyde: ... Nåværende tredje ledd andre punktum blir nytt fjerde ledd og skal lyde: ..."
    # (plan- og bygningsloven, LOV-2023-06-16-73): the old third ledd is replaced whole by the new one, so the moved
    # sentence, in its new words, is a new fourth ledd of that §
    fx = []
    for b in fixed:
        t = _btext(b) if b[0] in ('d', 'p') else ''
        m = re.match(r'^(?:Fra\s+den\s+tid\s+[^,]*,\s*)?skal\s+(§\s*[^:]*?)\s+i\s+((?:lov|lova)\s+\d+\.\s+\w+\s+\d{4}\s+nr\.\s*\d+\b[^:§]*?)\s+lyde:$', t)
        if m:
            # "Fra den tid loven begynner å gjelde, skal § 14-4 i lov 27. juni 2008 nr. 71 om planlegging og
            # byggesaksbehandling lyde:" (LOV-2025-05-27-21): the target sentence and the instruction
            fx.append(('d', 'I %s gjøres følgende endringer:' % m.group(2), None))
            fx.append(('d', '%s skal lyde:' % m.group(1), None))
            continue
        if re.match(r'^I\s+lov\s+\d+\.\s+\w+\s+\d{4}\s+nr\.\s*\d+\b[^:§]*\):$', t):
            # "I lov 27. juni 2008 nr. 71 om planlegging og byggesaksbehandling (plan- og bygningsloven):"
            # (LOV-2014-09-12-64): the target sentence, without its verb
            fx.append(('d', t[:-1] + ' gjøres følgende endringer:', None))
            continue
        fx.append(b)
    fixed = fx
    last_d = None
    for i, b in enumerate(fixed):
        if b[0] != 'd':
            continue
        if (re.match(r'^§\s*\d[^:]*\sskal\s+lyde$', b[1]) and i + 1 < len(fixed) and fixed[i + 1][0] == 'p'):
            # "§ 21-5 nytt fjerde ledd skal lyde" + the new ledd (LOV-2010-06-25-48): the colon is missing
            fixed[i] = b = ('d', b[1] + ':') + tuple(b[2:])
        m = re.match(r'^Nåværende\s+(%s)\s+ledd\s+(?:%s)\s+punktum\s+blir\s+nytt\s+(%s)\s+ledd\s+og\s+skal\s+lyde:$'
                     % (ORDRE, ORDRE, ORDRE), b[1])
        pm = last_d and re.match(r'^(§\s*\S+(?:\s[a-z](?![a-zæøå]))?)\s+(%s)\s+ledd\s+skal\s+lyde:$' % ORDRE, last_d)
        if m and pm and pm.group(2) == m.group(1) and ORD[m.group(2)] == ORD[m.group(1)] + 1:
            fixed[i] = ('d', '%s nytt %s ledd skal lyde:' % (pm.group(1), m.group(2))) + tuple(b[2:])
        last_d = b[1]
    out, inside = [], False
    for b in fixed:
        if b[0] == 'd' and re.match(r'^I\s+kapitlene\s.*\bskal\s+følgende\s+paragrafer\s+lyde:$', b[1]):
            inside = True
            out.append(b)
            continue
        if b[0] == 'sec' or (b[0] == 'd' and is_target(b[1])):
            inside = False
        if inside and b[0] == 'head' and re.match(r'^§\s*\d', b[1]):
            out.append(('d', b[1] + ' skal lyde:', None))
        out.append(b)
    return out


INSTR = re.compile(r'(skal\b[^:]{0,60}?\blyde:|oppheves\.?|blir\s+(?:ny(?:tt|e)?\s+)?(?:%s)(?:\s*,\s*(?:nytt?\s+)?(?:%s)|\s+(?:og|til)\s+(?:nytt?\s+)?(?:%s))*\s+(?:ledd|punktum)\.?|blir\s+ny\s+§|^Nåværende\s.*\bbokstav\s+[a-z]\b.*\bblir\s+(?:§\s*\d+(?:\s?[a-z](?![a-zæøå]))?\s+)?(?:\w+\s+ledd\s+)?(?:ny\s+)?bokstav\s+[a-z]\b)'
                   % (ORDRE, ORDRE, ORDRE))  # also "blir femte og nytt sjette ledd\"


TARGET = re.compile(r'^(?:\d+\.\s+|[IVX]+\.?\s+)?(?:I\s+)?(?:[Mm]idlertidig\s+)?(?:Almindelig\s+borgerlig\s+(?=Straffelov))?(?:[Ll]ov|[Ll]ova|[Ll]oven|[A-ZÆØÅa-zæøå-]+(?:loven|lova|lov))\b[^:§]{0,300}?'
                    r'(?:(?:følgende|følgjande|desse|disse|denne)\s+endring|endres\s+slik|blir\s+endra\s+slik|vert\s+endra\s+slik'
                    r'|(?:blir|vert)\s+det\s+gjort\s+slike?\s+endring)')


WORDS = r'(?:(?:ordet|ordene|ordet|uttrykket|utrykket|uttrykkene|betegnelsen|betegnelsene|henvisningen(?:\s+til)?|henvisningene|navnet|nemninga)\s+)?'
CHG = (r'(?:(?:skal\s+)?(?:endres|endras|erstattes|endra|endret|vert\s+endra|vert\s+endret|blir\s+endret|blir\s+endra)\s+(?:til|med)'
       r'(?:\s+(?:ordet|ordene|uttrykket|uttrykkene|betegnelsen|betegnelsene)(?=\s+«))?'
       r'|(?:skal\s+)?erstattes\s+av(?:\s+(?:ordet|ordene|uttrykket|uttrykkene|betegnelsen|betegnelsene)(?=\s+«))?)')
SUBST_LIST = re.compile(r'^(?:\d+\.\s+)?I\s+(?:følgende|følgjande)\s+(?:bestemmelser?|lovbestemmelser?|lovføresegner|føresegner|paragrafer)\b.*?«.+»\s*' + CHG + r'\s*(?:henholdsvis\s+)?«.+»[^«]*:\s*$')
SUBST_INLINE = re.compile(r'^(I lov [^§]*?)?\s*I?\s*§\s*(\d+[^«]*?)\s*(?:skal\s+)?' + WORDS + r'(«.+»\s*' + CHG + r'\s*«.+?»)\s*\.?$')
SUBST_WORD_FIRST = re.compile(r'^(?:Ordet|Ordene|Uttrykket|Uttrykkene|Betegnelsen|Betegnelsene)\s+(«[^»]+»\s*' + CHG
                              + r'\s*«[^»]+»)\s+i\s+(§\s*\d.*?)\.?$')
SUBST_VERB = re.compile(r'^(?:I\s+)?(§§?\s*\d+[^«:]*?)\s+(?:skal\s+)?((?:erstattes|endres|utgår|strykes)\s+(?:ordet\s+|ordene\s+|uttrykket\s+)?«.+)$')
SUBST_LIST_VERB_FIRST = re.compile(r'^I\s+(?:følgende|følgjande)\s+(?:bestemmelser|lovbestemmelser|føresegner)\s+'
                                   r'(?:endres|endras|vert\s+endra|blir\s+endret)\s+«([^»]+)»\s+(?:til|med)\s+«([^»]+)»\s*:\s*$')
LAW_LINE = re.compile(r'^(?:\d+\.\s+)?(?:[Mm]idlertidig\s+)?(?:lov|Lov)\s+\d+\.\s+\w+\s+\d{4}')
WARN = []
NOTES = []  # (paragraph, note) on readings parse.py records as decisions
NUMBERED_LEDD = [False]  # set by parse.py for an act that numbers its ledd "(1)", "(2)" (tvisteloven)


def subst_pairs(t):
    """'«A» og «B» endres til «C» og «D»' -> [('A', 'C'), ('B', 'D')]."""
    if len(re.findall(CHG, t)) > 1:
        # '«A» endres til «B» og «C» endres til «D»': one pair per verb
        out = []
        parts = re.split(r'(?<=»)\s*(?:,|\bog\b)\s*(?:(?:begrepet|ordet|uttrykket|ordene|betegnelsen)\s+)?(?=«)', t)
        for part in (parts if len(parts) > 1 else []):
            if re.search(CHG, part):
                out += subst_pairs(part)
        if len(out) == len(re.findall(CHG, t)):
            return out
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
    for part in re.split(r'(?=§\s*\d)|(?=\b[Kk]apittel\s+\d)', t):
        mc = re.match(r'[Kk]apittel\s+(\d+(?:\s?[A-Za-z](?![a-zæøå]))?)\s+(?:kapittel)?overskrift(?:a|en)\b', part.strip())
        if mc:
            # "kapittel 7 kapitteloverskrifta": the chapter's heading
            out.append(('kapittel:' + mc.group(1), None))
            continue
        m = re.match(r'§\s*(\d+(?:\s?[a-z](?![a-zæøå]))?)(.*)$', part.strip())
        if not m:
            continue
        ledd = sorted({ORD[w] for w in re.findall(r'(%s)\s+(?:og\s+(?:%s)\s+)?ledd' % (ORDRE, ORDRE), m.group(2))} |
                      {ORD[w] for w in re.findall(r'(%s)\s+og\s+(?:%s)\s+ledd' % (ORDRE, ORDRE), m.group(2))} |
                      {ORD[w] for w in re.findall(r'(?:%s)\s+og\s+(%s)\s+ledd' % (ORDRE, ORDRE), m.group(2))})
        if ledd and re.match(r'^\s*overskrift(?:a|en)\b', m.group(2)):
            # "§ 47 overskrifta og første og andre ledd": the heading too (0)
            ledd = [0] + ledd
        elif not ledd and re.fullmatch(r'\s*overskrift(?:a|en)[\s,]*(?:og\s*)?', m.group(2)):
            # "§ 4-4 overskriften": the heading only (barnevernsloven, LOV-2022-06-17-45)
            ledd = [0]
        out.append((norm_num(m.group(1)), ledd or None))
    return out


def subst_op(src, num, ledd, pairs, target):
    if num.startswith('kapittel:'):
        return {'src': src, 'num': None, 'chapter': num.split(':', 1)[1], 'act': 'subst_chap', 'pairs': pairs, 'lang': None,
                'target': target, 'payload': {}}
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
    given = {a for a, _ in op['pairs']}
    news = dict(op['pairs'])

    def sub(m):
        w = m.group(0)
        if w in keep:
            return w
        if w not in given and w[:1].lower() + w[1:] in given and not re.search(r'(?:^|[.!?:]\s+|\n)$', s[:m.start()]):
            # a capitalised old word inside a sentence ("som Fylkesmannen mener"): the new word as the law writes it
            return news[w[:1].lower() + w[1:]]
        return table[w]
    return rx.sub(sub, s)


def _apply_subst(item, op):
    hit = False
    for i, ld in enumerate(item['ledd']):
        if op['subst_ledd'] and i + 1 not in op['subst_ledd']:
            continue
        for j, line in enumerate(ld):
            new = _subst_text(line, op)
            if new != line:
                # (the words after a list ride after CONT, which norm's whitespace folding would turn into a space)
                ld[j] = L.CONT.join(L.norm(x) for x in new.split(L.CONT))
                hit = True
    if (not op['subst_ledd'] or 0 in op['subst_ledd']) and item.get('title'):
        new = _subst_text(item['title'], op)
        if new != item['title']:
            item['title'] = new
            hit = True
    if not hit:
        WARN.append('substitution found nothing: § %s %s' % (op['num'], op['src'][:120]))


TARGET_IN = re.compile(r'^(?:\d+\.\s+)?(?:Med virkning fra .*?(?:følgende|følgjande) endring(?:er|ar)? i (.*)'
                       r'|(?:Fra den tid(?:en)?|Frå den tida?)\b.*?(?:følgende|følgjande) endring(?:er|ar)? i ([Ll]ova?\s+\d.*)'
                       # a numbered law of a list of amendments, alone on its line: "7. Lov 17. juni 2005 nr. 62 om
                       # arbeidsmiljø-, arbeidstid og stillingsvern" (likestillings- og diskrimineringsloven 2017 § 44)
                       r'|\d+\.\s+((?:[Ll]ov|[Ll]ova)\s+\d{1,2}\.\s+[a-zæøå]+\s+\d{4}\s+nr\.?\s*\d+\b[^§:«»]*?):?'
                       # (LOV-2021-12-22-163 § 18) a new act's own list of amendments, its last item naming the act
                       r'|(?:Fra den tid(?:en)?|Frå den tida?)\b[^:]*?endring(?:er|ar)? i andre lover:\s.*\s\d+\)\s+I\s+'
                       r'((?:[Ll]ov|[Ll]ova)\s+\d{1,2}\.\s+[a-zæøå]+\s+\d{4}\s+nr\.?\s*\d+\b[^:§]*?)\s+gjøres\s+følgende\s+endring(?:er)?:)$')


def is_target(t):
    """'I lov 14. juni 2019 nr. 21 om arv ... gjøres følgende endringer:' (also numbered '1. I lov ...'), or
    'Med virkning fra ... gjøres følgende endringer i lov 22. mai 1902 nr. 13 militær straffelov:'."""
    return bool(TARGET.match(t) or TARGET_IN.match(t))


def target_of(t):
    """The words that name the amended act: for 'Med virkning fra ... endringer i <act>:', only <act>."""
    m = TARGET_IN.match(t)
    return (m.group(1) or m.group(2) or m.group(3) or m.group(4)) if m else t


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
    m = re.match(r'^(?:I lov [^§]*? skal\s+)?(?:I\s+(?=§[^:]*\bskal\b[^:]*\blyde:))?(?:Grunnloven\s+)?(Ny\s+|ny\s+|Nåværende\s+)?§\s*(\d+(?:\s?[a-z](?![a-zæøå]))?)\s*(.*)$', t)
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
    lm0 = re.match(r'^\((\d{1,2})\)(?=\s)', rest)
    if lm0 and 1 <= int(lm0.group(1)) <= 12:
        # "skal § 12-5 (1) lyde:" (arbeidsmiljøloven, lov 21. april 2006 nr. 10): the numbered ledd
        rest = next(w for w, v in ORD.items() if v == int(lm0.group(1))) + ' ledd' + rest[lm0.end():]
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
    if re.search(r'\bsiste\s+punktum\b', rest):
        # "første ledd siste punktum skal lyde:", "første ledd nytt siste punktum skal lyde:"
        op['last_pkt'] = True
        rest = re.sub(r'\bsiste\s+punktum\b', 'første punktum', rest)
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
        # "andre og nytt tredje punktum skal lyde:" (opplæringslova § 2-1, LOV-2024-06-25-53): the old second sentence
        # is replaced and a third added; the old third stays (as the fourth)
        nm = re.fullmatch(r'(%s)((?:(?:\s*,\s*|\s+og\s+)nytt\s+(?:%s))+)' % (ORDRE, ORDRE), pm.group(2))
        if nm and not pm.group(1):
            added = [ORD[w] for w in re.findall(ORDRE, nm.group(2))]
            if added == list(range(ns[0] + 1, ns[0] + 1 + len(added))):
                op['pkt_to'] = None
                op['pkt_adds'] = len(added)
    bm = re.search(r'(ny\s+)?bok?stav\s+([a-z])\)?((?:(?:\s*,\s*|\s+og\s+)(?:ny\s+)?(?:bokstav\s+)?[a-z]\b\)?)*)', rest)
    if bm and re.match(r'\s+(?:nytt?\s+)?nr\.\s*\d', rest[bm.end():]):
        if not bm.group(3):
            op['in_letter'] = bm.group(2)  # the numbers of that letter's own list
        bm = None  # the numbered items inside a letter are the target, not the letter
    if not bm:
        bm = re.search(r'ledd\s+(ny\s+)?([a-z])\)()', rest)  # '§ 196 første ledd c) skal lyde:'
    op['intro'] = bool(re.search(r'\binnledning(?:en|ssetningen)\b', rest))  # "innledningssetningen" (LOV-2018-03-23-2)
    if not bm:
        bm = re.search(r'(ny(?:tt?)?\s+)?nr\.\s*(\d+)((?:(?:\s*,\s*|\s+og\s+)(?:ny(?:tt?)?\s+)?(?:nr\.\s*)?\d+\b)*)', rest)
        if bm:
            op['bokstav'] = bm.group(2)
            op['bokstav_new'] = bool(bm.group(1))
            more = re.findall(r'(ny(?:tt?)?\s+)?(?:nr\.\s*)?(\d+)\b', bm.group(3) or '')
            op['bokstav_more'] = [(l, bool(n)) for n, l in more]
            rg = re.match(r'\s+til\s+(ny(?:tt?)?\s+)?(?:nr\.\s*)?(\d+)\b', rest[bm.end():])
            if rg and not more and int(rg.group(2)) > int(bm.group(2)):
                # "nr. 10 til ny nr. 12": every number of the range, the last one new when it says so
                op['bokstav_more'] = [(str(n), bool(rg.group(1)) and n == int(rg.group(2)))
                                      for n in range(int(bm.group(2)) + 1, int(rg.group(2)) + 1)]
            bm = None
    if bm:
        op['bokstav'] = bm.group(2)
        op['bokstav_new'] = bool(bm.group(1))
        more = re.findall(r'(?:,\s*|\bog\s+)(ny\s+)?(?:bokstav\s+)?([a-z])\b', bm.group(3) or '')
        op['bokstav_more'] = [(l, bool(n)) for n, l in more]
        rg = re.match(r'\s+til\s+(ny\s+)?(?:bokstav\s+)?([a-z])\b', rest[bm.end():])
        if rg and not more and rg.group(2) > bm.group(2):
            # "§ 59 bokstav c til ny e skal lyde:": the letters c to e, the last one new when it says so
            op['bokstav_more'] = [(chr(c), bool(rg.group(1)) and chr(c) == rg.group(2))
                                  for c in range(ord(bm.group(2)) + 1, ord(rg.group(2)) + 1)]
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
        rm = re.search(r'blir\s+(ny(?:tt|e)?\s+)?(%s)(?:(?:\s*,\s*|\s+til\s+|\s+og\s+)(?:nytt?\s+)?(?:%s))*\s+(ledd|punktum)' % (ORDRE, ORDRE), rest)
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


# "§ 16-3 nr. 32 om endringer i skattebetalingsloven:", "§ 16-3 Endringer i andre lover pkt. 7 om endringar i lov ...:",
# "§ 16-3 nr. 19 om endringer i lov ... oppheves.": the instructions that follow amend that item of the act's own list
# of amendments to other acts, which the record keeps as its opening words only
AMEND_ITEM = re.compile(r'^§\s*\d+(?:\s?[a-z])?\b[^:«]{0,60}?\b(?:nr|pkt)\.\s*\d+\s+om\s+endring(?:er|ar)?\s+i\s+[^:]*(?::|\boppheves\.?)$'
                        # "I § 30-3 skal endringene i privatskolelova § 4-5 lyde:" (opplæringslova, LOV-2024-06-14-36)
                        r'|^I\s+§\s*\d+(?:\s?[a-z])?\s+skal\s+endring(?:ene|ane)\s+i\s+[\wæøå-]+\s+§[^:]*\blyde:$')


DEFERRED = re.compile(r'^Med\s+virkning\s+fra\s+den\s+tid\s+(?:hele\s+)?[^:]{0,120}?\s+sett(?:es|ast|ast)\s+i\s+kraft,\s+'
                      r'(?:gjøres|gjerast)\s+(?:følgende|følgjande)\s+endring(?:er|ar)\s+i\s+(?:annen\s+lovgivning|andre\s+lover):$')


def doc_ops(raw, only=None, single_lang=None, strict=True):
    """All instructions of an amending document, each with its payload split by language.

    `only(op)` may drop instructions aimed at other acts (decided by the caller from the intro sentence).
    `single_lang` ('bm'): an ordinary act published in one language, so payloads are not split."""
    bl = blocks(raw)
    ops, nn_only, last, cur_target = [], False, None, None
    subst = None  # (olds, news) while reading a list "I følgende bestemmelser skal «X» endres til «Y»:"
    i = 0
    cur_part, ntag = None, 0  # the amending law's own part ("II") each instruction stands in
    # the list of amendments to other acts of another law, replaced by this one ("I lov 14. juni 2019 nr. 21 ... gjøres
    # følgende endringer: ... § 181 skal lyde: ... Fra den tid loven trer i kraft gjøres følgende endringer i andre
    # lover: 1. ... 33. I lov 26. mars 2010 nr. 9 om vergemål gjøres følgende endringer: ..."): the target of that law,
    # carried by every later op of the same part as 'restates'
    restating = None
    # "Nåværende § 402 blir § 412 og skal lyde: § 412 Endringer i andre lover / Med virkning fra den tid hele straffeloven
    # 20. mai 2005 nr. 28 settes i kraft, gjøres følgende endringer i annen lovgivning:" (lov 19. juni 2009 nr. 74): the
    # numbered amendments after it, to the end of the part, are the text of another act's list of amendments, carried
    # by every op as 'deferred'
    deferred = None
    while i < len(bl):
        b = bl[i]
        t = _btext(b)
        for o in ops[ntag:]:
            o['part'] = cur_part
            if deferred:
                o['deferred'] = deferred
            if restating:
                o['restates'] = restating
            elif (o.get('act') in ('set', 'struct') and o.get('target') and re.search(r'(?i)\blov\s+\d', o['target'])
                  and re.search(r'endring(?:er|ar) i andre lover:', str(o.get('payload')))
                  and any(re.search(r'(?i)endring(?:er|ar) i andre lover', str(b[2] if b[0] == 'head' else b[1]))
                          for b in (o.get('payload') or {}).get('bm', []) if b[0] in ('head', 'title'))):
                # the replaced paragraph or chapter is itself headed "Endringer i andre lover"
                restating = o['target']
            elif (o.get('act') == 'set' and o.get('target') and re.search(r'(?i)\blov\s+\d', o['target'])
                  and o.get('ledd') is None and o.get('pkt') is None and o.get('bokstav') is None
                  and not any(x[0] == 'p' for x in (o.get('payload') or {}).get('bm', []))
                  and b[0] == 'd' and re.match(r'^1\.\s+I\s+lov\s+\d', t) and is_target(t)):
                # "§ 37-3 skal lyde:" + at once "1. I lov 20. juli 1893 nr. 2 ... gjøres følgende endringer:" (lov 26.
                # januar 2007 nr. 3 on tvisteloven's paragraph of amendments to other acts): the paragraph is a
                # numbered list of amendments, restated
                restating = o['target']
        ntag = len(ops)
        if b[0] == 'd' and AMEND_ITEM.match(t):
            # skip the item's instructions (up to the next part, target sentence or item), and record them as one
            j, n = i + 1, 0
            while j < len(bl) and bl[j][0] != 'sec' and not (bl[j][0] in ('d', 'p') and (
                    is_target(_btext(bl[j])) or AMEND_ITEM.match(_btext(bl[j])))):
                n += bl[j][0] == 'd' and bool(is_instr(_btext(bl[j])) or re.match(r'^(?:I\s+)?[Ee]ndring', _btext(bl[j])))
                j += 1
            ops.append({'act': 'error', 'src': t, 'target': cur_target, 'num': None, 'lang': None,
                        'error': 'amends an item of the act\'s list of amendments to other acts (kept as its opening '
                                 'words only)%s: %s' % ((' (%d instruction%s)' % (n, 's' if n > 1 else '')) if n else '', t)})
            i = j
            continue
        if b[0] == 'sec':
            subst = None
            restating = None
            deferred = None
            if b[2]:
                # a new part of the law ("II"): its instructions go on amending the act named before, unless the
                # part names another act ("I lov ... gjøres følgende endringer")
                cur_part = b[2]
            else:
                cur_target = None
        if b[0] in ('d', 'p') and DEFERRED.match(t) and i and bl[i - 1][0] == 'head':
            # only as the text of a paragraph a payload replaces (its heading just before); a law's own sentence of this
            # kind (lov 7. mars 2008 nr. 4) is an ordinary in-force rule for the amendments after it
            deferred = t
            cur_target = target_of(t) if is_target(t) else cur_target  # "annen lovgivning": no act of its own
            i += 1
            continue
        if b[0] == 'p' and len(b[1]) > 1 and SUBST_LIST.match(b[1][0]):
            # the substitution sentence and its list of provisions printed as one ledd with a list
            bl[i:i + 1] = [('d', b[1][0], None), ('p', list(b[1][1:]), None)]
            b = bl[i]
            t = _btext(b)
        if b[0] in ('d', 'p') and SUBST_LIST.match(t):
            subst = subst_pairs(t)
            i += 1
            continue
        m = SUBST_LIST_VERB_FIRST.match(t) if b[0] in ('d', 'p') else None
        if m:
            # "I følgende bestemmelser endres «forvaltningsloven §§ 13 til 13 e» til «... og 13 g»:"
            subst = [(m.group(1), m.group(2))]
            i += 1
            continue
        if subst and b[0] in ('d', 'p'):
            # a list of laws each with its provisions on one line: "1) Lov 13. august 1915 nr. 5 om domstolene § 63 a
            # andre ledd 2) Lov ...", or one line per law "lov 22. juni 2018 nr. 83 om kommuner ... § 29-1 annet ledd"
            lines = list(b[1]) if b[0] == 'p' else [t]
            items = [re.sub(r'^(?:\d+|[a-z])\)\s*', '', x).strip() for ln in lines
                     for x in re.split(r'\s(?=(?:\d+|[a-z])\)\s+[Ll]ov\b)', ln)]  # "1) Lov ...", "a) lov ..."
            items = [re.sub(r'\bnr\.\s+nr\.?\s*(?=\d)', 'nr. ', x) for x in items]  # misprint "2009 nr. nr 35"
            # (a law without a number: "lov 10. februar 1967 om behandlingsmåten i forvaltningssaker § 30")
            law_refs = [re.match(r'^((?:[Mm]idlertidig\s+)?(?:[Ll]ov|[Ll]ova)\s+\d+\.\s+\w+\s+\d{4}(?:\s+nr\.?\s*\d+\b)?[^§]*?)\s*(§.*)$', x)
                        for x in items]
            if items and all(law_refs):
                for m in law_refs:
                    for num, ledd in subst_refs(m.group(2)):
                        ops.append(subst_op(m.string if len(law_refs) > 1 else t, num, ledd, subst, m.group(1)))
                i += 1
                continue
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
        m = re.match(r'^I\s+§\s*(%s)\s+(?:gjøres|gjerast)\s+(?:følgende|følgjande)\s+endring(?:er|ar)?:$' % NUM, t) \
            if b[0] == 'd' else None
        if m:
            # "I § 15-11 gjøres følgende endringer:" + "Tredje ledd skal lyde: ..." (arbeidsmiljøloven, lov 21. desember
            # 2005 nr. 121): the ledd instructions after it are that paragraph's
            last = norm_num(m.group(1))
            i += 1
            continue
        if b[0] == 'd' and LEDD_ONLY.match(t) and last:
            # "§ 130 første ledd skal lyde: ... Annet ledd oppheves. Nåværende tredje ledd blir nytt annet ledd."
            # (samvirkelova, lov 14. juni 2013 nr. 41): the same paragraph
            t = '§ %s %s' % (last, t[0].lower() + t[1:])
            bl[i] = b = ('d', t, None)
        if b[0] in ('d', 'p'):
            # 'I § 30, slik § 30 lyder etter endringer ved ..., skal første ledd bokstav g lyde:' -> '§ 30 første ledd bokstav g skal lyde:'
            t2 = re.sub(r'^I (§\s*%s),\s*slik [^,]*,\s*skal (.*?) lyde:' % NUM, r'\1 \2 skal lyde:', t)
            if t2 != t:
                t = t2
                bl[i] = (b[0], t, b[2]) if b[0] == 'd' else ('d', t, None)
                b = bl[i]
            # 'Lov 19. mai 2006 nr. 16 om ... § 19 første punktum skal lyde:': the act named in the instruction itself
            m3 = re.match(r'^(?:\d+\.\s+)?(?:I\s+)?((?:[Ll]ov|[Ll]ova)\s+\d+\.\s+\w+\s+\d{4}\s+nr\.?\s*\d+\b[^§:]*?)\s+(§\s*\d[^:§]*?\b(?:skal\b[^:§]{0,60}?\blyde:|oppheves\.?))$', t)
            if m3 and not is_target(t):
                cur_target = m3.group(1)
                t = m3.group(2)
                bl[i] = ('d', t, None)
                b = bl[i]
            # '23. lov 26. mars 2010 nr. 9 om vergemål skal § 39 første ledd bokstav e lyde:' (no "I", "skal" first)
            m3 = re.match(r'^(?:\d+\.\s+)?((?:[Ll]ov|[Ll]ova)\s+\d+\.\s+\w+\s+\d{4}\s+nr\.?\s*\d+\b[^§:]*?)\s+skal\s+(§\s*\d[^:§]*?)\s+lyde:$', t)
            if m3 and not is_target(t):
                cur_target = m3.group(1)
                t = m3.group(2) + ' skal lyde:'
                bl[i] = ('d', t, None)
                b = bl[i]
        m = re.match(r'^I\s+\w+\s+del\s+skal\s+(nytt\s+kapittel\s+\d+(?:\s?[A-Z])?)\s+lyde:$', t) if b[0] in ('d', 'p') else None
        if m:
            # "I femte del skal nytt kapittel 28 A lyde:" (tvisteloven, lov 31. mai 2013 nr. 25)
            t = m.group(1)[0].upper() + m.group(1)[1:] + ' skal lyde:'
            b = ('d', t, None)
            bl[i] = b
        m = re.match(r'^(?:\d+\.\s+)?(I\s+(?:midlertidig\s+)?lov\s.*?)\s+oppheves\s+(§\s*%s\s+(?:(?:%s)\s+(?:ledd|punktum)\b\s*)+)\.?$'
                     % (NUM, ORDRE), t) if b[0] in ('d', 'p') else None
        if m and not is_target(t):
            # "10. I lov 17. juni 2005 nr. 90 om ... oppheves § 4-4 fjerde ledd tredje punktum."
            cur_target = m.group(1)
            for op in parse_instr(m.group(2).strip() + ' oppheves.', last):
                op.update(target=cur_target, payload={}, in_amendment=False)
                ops.append(op)
                last = op['num'] or last
            i += 1
            continue
        m = re.match(r'^I\s+(?:del\s+[IVXL]+\s+i\s+)?endringen\s+av\s+((?:[Ll]ov|[Ll]ova)\s+\d+\.\s+\w+\s+\d{4}\s+nr\.?\s*\d+\b[^§]*?)\s+(§\s*%s)\b' % NUM, t) \
            if b[0] in ('d', 'p') else None
        if m:
            # "I del II i endringen av lov 17. juni 2005 nr. 90 om ... § 4-4 oppheves fjerde ledd.": a change another
            # amending law made to the act, amended before it took effect; recorded, not applied (parse.py dates the
            # amended law's own change by Lovdata's notes)
            ops.append({'act': 'error', 'src': t, 'target': m.group(1), 'num': None, 'lang': None,
                        'error': 'amends the change an earlier amending law made to %s, before that change took effect: %s'
                                 % (m.group(2), t)})
            i += 1
            continue
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
            pairs = [(a, b or c) for a, b, c in re.findall(r'«([^»]*)»\s+(?:med|til|av)\s+(?:«([^»]*)»|([\wæøåÆØÅ-]+))', m.group(2))]
            if m.group(2).startswith(('utgår', 'strykes')):
                pairs = [(x, '') for x in re.findall(r'«([^»]*)»', m.group(2))]
            if not pairs:
                ops.append({'act': 'error', 'src': t, 'error': 'cannot read substitution: ' + t, 'target': cur_target, 'num': None, 'lang': None})
            for num, ledd in subst_refs(m.group(1)):
                ops.append(subst_op(t, num, ledd, pairs, cur_target))
                last = num
            i += 1
            continue
        m = re.match(r'^I\s+§\s*(%s)\s+((?:(?:%s)\s+ledd\s+)?)skal\s+(?:uttrykket|ordet|ordene|ordlyden)\s+«([^»]+)»\s+lyde:$'
                     % (NUM, ORDRE), t) if b[0] in ('d', 'p') else None
        if m:
            pl, j = collect_payload(bl, i + 1)
            txt = ' '.join(x for bb in pl if bb[0] in ('p', 'd') for x in ([bb[1]] if bb[0] == 'd' else bb[1])).strip()
            txt = re.sub(r'^«(.*)»\.?$', r'\1', txt)
            if txt.endswith('.') and not m.group(3).endswith('.'):
                txt = txt[:-1]  # the full stop ends the instruction's payload, not the words
            if not txt:
                ops.append({'act': 'error', 'src': t, 'error': 'no new words for: ' + t, 'target': cur_target, 'num': None, 'lang': None})
            else:
                ld = [ORD[w] for w in re.findall(ORDRE, m.group(2))] or None
                ops.append(subst_op(t, norm_num(m.group(1)), ld, [(m.group(3), txt)], cur_target))
            last = norm_num(m.group(1))
            i = j
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
        in_amendment = False
        in_act = None
        m = re.match(r'^I\s+lovens\s+del\s+[IVXL]+\s+om\s+endring(?:er|ar)?\s+i\s+(lov\s+\d+\.\s+\w+\s+\d{4}\s+nr\.?\s*\d+)\b[^§]*?'
                     r'\s(?:skal\s+(§\s*%s\b[^:§]*?)\s*lyde:|føyes\s+ny\s+§\s*%s\s+til\s+etter\s+§\s*%s\.\s+(Ny\s+§\s*%s\s+skal\s+lyde:))$'
                     % (NUM, NUM, NUM, NUM), t) if b[0] in ('d', 'p') else None
        if m:
            # "I lovens del I om endringer i lov 10. april 2015 nr. 17 om finansforetak ... skal § 11-16 første ledd
            # lyde:", "... føyes ny § 11-21 til etter § 11-20. Ny § 11-21 skal lyde:" (LOV-2025-04-10-11 amending
            # LOV-2021-04-23-22 before it took effect): read as instructions on the act named, marked in_amendment
            in_act = m.group(1)
            t = re.sub(r'\s+', ' ', (m.group(2) + ' skal lyde:') if m.group(2) else m.group(3))
            in_amendment = True
            b = ('d', t, None)
            bl[i] = b
        m = re.match(r'^I\s+(?:endringen|endringa|tilføyelsen\s+av\s+ny|tilføyinga\s+av\s+ny)\s+(?:i\s+)?(§\s*%s)\s+(.*)$' % NUM, t) \
            if b[0] in ('d', 'p') else None
        if m:
            # an amending law amended before it took effect: "I endringen i § 26 blir ...", "I tilføyelsen av ny § 26 b
            # skal første ledd lyde:" (read as instructions on the act; parse.py accepts them only when the law they
            # amend is one of the act's own amending laws)
            rest = m.group(2)
            ms = re.match(r'^skal\s+(.*?)\s*lyde:$', rest)
            t = '%s %s' % (m.group(1), (ms.group(1) + ' skal lyde:') if ms else rest)
            t = re.sub(r'\s+', ' ', t)
            in_amendment = True
            b = ('d', t, None)
            bl[i] = b
        m = re.match(r'^§\s*(%s)\s+blir\s+nåværende\s+(%s)\s+ledd\s+nytt\s+(%s)\s+ledd\s+(%s)\s+punktum\.\s*(.*)$'
                     % (NUM, ORDRE, ORDRE, ORDRE), t) if b[0] in ('d', 'p') else None
        if m:
            # "§ 26 blir nåværende tredje ledd nytt andre ledd andre punktum. Nåværende fjerde ledd blir nytt tredje
            # ledd, ...": a ledd becomes a sentence of the ledd before it; the later ledd move up by one
            ops.append({'act': 'ledd_to_pkt', 'src': t, 'num': norm_num(m.group(1)), 'ledd': ORD[m.group(2)],
                        'to_ledd': ORD[m.group(3)], 'pkt': ORD[m.group(4)], 'bokstav': None, 'target': cur_target,
                        'lang': None, 'payload': {}, 'in_amendment': in_amendment})
            last = norm_num(m.group(1))
            pairs = re.findall(r'[Nn]åværende\s+(%s)\s+ledd\s+blir\s+(?:nytt\s+)?(%s)\s+ledd' % (ORDRE, ORDRE), m.group(5))
            rest = re.sub(r'(?:,\s*|\s+og\s+)?[Nn]åværende\s+(%s)\s+ledd\s+blir\s+(?:nytt\s+)?(%s)\s+ledd' % (ORDRE, ORDRE), '',
                          m.group(5)).strip(' .')
            if rest or any(ORD[y] != ORD[x] - 1 for x, y in pairs):
                ops.append({'act': 'error', 'src': t, 'error': 'cannot read instruction: ' + t, 'target': cur_target,
                            'num': None, 'lang': None})
            i += 1
            continue
        m = re.match(r'^I\s+§\s*(%s)\s+blir\s+(%s)\s+ledd\s+(%s)\s+punktum\s+nytt\s+(%s)\s+ledd\.\s*(.*)$'
                     % (NUM, ORDRE, ORDRE, ORDRE), t) if b[0] in ('d', 'p') else None
        if m:
            # "I § 203 blir tredje ledd annet punktum nytt fjerde ledd. Nåværende fjerde ledd blir femte ledd.": the
            # sentence (with the list it introduces) becomes a ledd of its own; the later ledd move on by one
            ops.append({'act': 'pkt_to_ledd', 'src': t, 'num': norm_num(m.group(1)), 'ledd': ORD[m.group(2)],
                        'pkt': ORD[m.group(3)], 'to_ledd': ORD[m.group(4)], 'bokstav': None, 'target': cur_target,
                        'lang': None, 'payload': {}})
            last = norm_num(m.group(1))
            rest = m.group(5).strip()
            if rest and not re.fullmatch(r'Nåværende\s+(%s)\s+ledd\s+blir\s+(?:nytt\s+)?(%s)\s+ledd\.?' % (ORDRE, ORDRE), rest):
                ops.append({'act': 'error', 'src': t, 'error': 'cannot read instruction: ' + t, 'target': cur_target,
                            'num': None, 'lang': None})
            i += 1
            continue
        m = re.match(r'^Punktum(?:et)?\s+etter\s+«([^»]+)»\s+i\s+§\s*(%s)\s+bokstav\s+([a-z])\s+(?:fjernes|strykes|utgår)\.?$' % NUM, t) \
            if b[0] in ('d', 'p') else None
        if m:
            # "Punktum etter «finansskatt på lønn» i § 1-1 bokstav k fjernes." (a new letter follows it)
            ops.append({'act': 'item_punct', 'src': t, 'num': norm_num(m.group(2)), 'letter': m.group(3), 'after': m.group(1),
                        'to': '', 'target': cur_target, 'lang': None, 'payload': {}, 'ledd': None, 'pkt': None, 'bokstav': None})
            last = norm_num(m.group(2))
            i += 1
            continue
        m = re.match(r'^Punktumet i bokstav ([a-z]) erstattes (?:av|med) et komma', t) if b[0] in ('d', 'p') else None
        if m:
            ops.append({'act': 'item_punct', 'src': t, 'num': last, 'letter': m.group(1), 'target': cur_target, 'lang': None,
                        'payload': {}, 'ledd': None, 'pkt': None, 'bokstav': None})
            i += 1
            continue
        m = SUBST_WORD_FIRST.match(t) if b[0] in ('d', 'p') else None
        if m:
            # "Ordet «atferdsinstitusjon» skal endres til «barnevernsinstitusjon» i § 1-2 tredje og fjerde ledd, § 4-4
            # overskriften, ... og § 13-4 første ledd bokstav e og l." (barnevernsloven, LOV-2022-06-17-45)
            pairs = subst_pairs(m.group(1))
            for num, ledd in subst_refs(m.group(2)):
                ops.append(subst_op(t, num, ledd, pairs, cur_target))
            i += 1
            continue
        if b[0] in ('d', 'p') and SUBST_INLINE.match(t):
            m = SUBST_INLINE.match(t)
            if m.group(1):
                cur_target = target_of(t)
            try:
                pairs = subst_pairs(m.group(3))
            except ReplayError as e:
                # kept, so that it stops the build only if it is aimed at the act being built
                ops.append({'act': 'error', 'src': t, 'error': str(e), 'target': cur_target, 'num': None, 'lang': None})
                i += 1
                continue
            for num, ledd in subst_refs(m.group(2)):
                ops.append(subst_op(t, num, ledd, pairs, cur_target))
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
        mp = move_pairs(t) if b[0] == 'd' else None
        if mp and (len(mp) > 1 or not t.startswith('Nåværende') or not STRUCT.match(t)):
            for old, new in mp:
                ops.append({'act': 'struct', 'kind': 'move_para', 'src': t, 'old': old, 'num': new, 'lang': None,
                            'target': cur_target, 'payload': {'bm': []}})
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
                                                 or re.match(r'^I\s+§[^:«]*\bskal\b[^:«]*\blyde:$', t)
                                                 or (re.match(r'^(?:\d+\.\s+)?I lov ', t) and ' skal ' in t)):
            if re.match(r'^(?:\d+\.\s+)?I lov ', t):
                # only the words naming the act: the new text may follow on the same line and name another act
                # ("I lov 21. juni 1996 nr. 38 om statlig naturoppsyn skal § 2 nytt første ledd nr. 7 lyde: 7) lov
                # 19. juni 2009 nr. 100 om ... (naturmangfoldloven)")
                cur_target = re.split(r'\s+(?:skal\s+)?§', target_of(t), 1)[0]
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
                op['in_amendment'] = in_amendment
                if in_act:
                    op['in_act'] = in_act
                prev = ops[-1] if ops else None
                if (op['src'].startswith('Nåværende') and op['ledd'] is None and op['pkt'] is not None and prev
                        and prev.get('num') == op['num'] and prev.get('ledd') is not None):
                    op['ledd'] = prev['ledd']  # 'Nåværende annet punktum blir ...' in the ledd just named
                if (op['src'].startswith('Nåværende bokstav') and op['act'] == 'renum' and op['ledd'] is None and prev
                        and prev.get('num') == op['num'] and prev.get('ledd') is not None and prev.get('bokstav')):
                    # "§ 6-2 første ledd ny bokstav c skal lyde: ... Nåværende bokstav c til e blir bokstav d til f."
                    # (tvisteloven, lov 26. januar 2007 nr. 3): the letters of the ledd just named
                    op['ledd'] = prev['ledd']
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
    for o in ops[ntag:]:
        o['part'] = cur_part
    split = []
    for o in ops:
        m = re.search(r'punktum\s+og\s+nytt\s+(%s)\s+ledd\s+skal\s+lyde' % ORDRE, o.get('src') or '')
        pl = (o.get('payload') or {}).get('bm') or []
        ps = [b for b in pl if b[0] == 'p']
        if (m and o['act'] == 'set' and o.get('pkt') and set(o['payload']) == {'bm'} and len(ps) == 2
                and pl[-1] is ps[1]):
            # one sentence set and a new ledd in one instruction: two instructions, each with its own text
            i = pl.index(ps[1])
            split.append(dict(o, payload={'bm': pl[:i]}))
            split.append(dict(o, pkt=None, pkt_to=None, pkt_new=False, ledd=ORD[m.group(1)], ledd_to=None,
                              ledd_new=True, payload={'bm': pl[i:]}))
        elif (o['act'] == 'set' and set(o['payload']) == {'bm'} and len(ps) == 2 and pl[-1] is ps[1]
              and re.search(r'\b(%s)\s+ledd\s+og\s+(%s)\s+ledd\s+(%s)\s+punktum\s+(?:skal\s+)?lyde' % (ORDRE, ORDRE, ORDRE),
                            o.get('src') or '')):
            # "§ 87 første ledd og andre ledd første punktum skal lyde:": a ledd and a sentence of the next, one text each
            m = re.search(r'\b(%s)\s+ledd\s+og\s+(%s)\s+ledd\s+(%s)\s+punktum' % (ORDRE, ORDRE, ORDRE), o['src'])
            i = pl.index(ps[1])
            split.append(dict(o, ledd=ORD[m.group(1)], ledd_to=None, pkt=None, pkt_to=None, pkt_new=False,
                              payload={'bm': pl[:i]}))
            split.append(dict(o, ledd=ORD[m.group(2)], ledd_to=None, pkt=ORD[m.group(3)], pkt_to=None, pkt_new=False,
                              payload={'bm': pl[i:]}))
        elif (o['act'] == 'set' and o.get('ledd') and o.get('bokstav') and not o.get('pkt') and not o.get('bokstav_more')
              and set(o['payload']) == {'bm'} and all(b[0] == 'p' for b in pl)
              and re.search(r'\b(?:%s)\s+ledd\s+(?:nr\.?|bokstav)\s*\w+\s+og\s+(%s)(?:\s+og\s+(%s))?\s+ledd\s+(?:skal\s+)?lyde'
                            % (ORDRE, ORDRE, ORDRE), o.get('src') or '')):
            # "§ 1-2 annet ledd nr. 5 og tredje og fjerde ledd skal lyde:" (eiendomsmeglingsloven, lov 25. mai 2012
            # nr. 27): one item, then whole ledd, one text each
            m = re.search(r'\b(?:%s)\s+ledd\s+(?:nr\.?|bokstav)\s*\w+\s+og\s+(%s)(?:\s+og\s+(%s))?\s+ledd' % (ORDRE, ORDRE, ORDRE),
                          o['src'])
            a = ORD[m.group(1)]
            b = ORD[m.group(2)] if m.group(2) else None
            if len(ps) != (3 if b else 2) or (b is not None and b != a + 1):
                split.append(o)
            else:
                split.append(dict(o, payload={'bm': [ps[0]]}))
                split.append(dict(o, ledd=a, ledd_to=b, ledd_new=False, bokstav=None, bokstav_new=False,
                                  payload={'bm': ps[1:]}))
        elif (o['act'] == 'set' and o.get('ledd') and not o.get('pkt') and not o.get('bokstav')
              and set(o['payload']) == {'bm'} and all(b[0] == 'p' for b in pl)
              and re.search(r'\b(%s)\s*,\s*(nye|nytt)\s+(%s)(?:\s+og\s+(%s))?\s+ledd\s+(?:skal\s+)?lyde' % (ORDRE, ORDRE, ORDRE),
                            o.get('src') or '')):
            # "§ 23 første, nye andre og tredje ledd skal lyde:" / "§ 38 første, nytt andre og tredje ledd skal lyde:"
            # (eierseksjonsloven, lov 10. april 2019 nr. 13): the first ledd set, the new one(s) added; a third without
            # "nye" is set (an insertion when the same law renumbers that ledd)
            m = re.search(r'\b(%s)\s*,\s*(nye|nytt)\s+(%s)(?:\s+og\s+(%s))?\s+ledd' % (ORDRE, ORDRE, ORDRE), o['src'])
            a, b = ORD[m.group(1)], ORD[m.group(3)]
            c = ORD[m.group(4)] if m.group(4) else None
            if b != a + 1 or (c is not None and c != b + 1) or len(ps) != (3 if c else 2):
                split.append(o)
            else:
                split.append(dict(o, ledd=a, ledd_to=None, ledd_new=False, payload={'bm': [ps[0]]}))
                if c and m.group(2) == 'nye':
                    split.append(dict(o, ledd=b, ledd_to=c, ledd_new=True, payload={'bm': ps[1:]}))
                else:
                    split.append(dict(o, ledd=b, ledd_to=None, ledd_new=True, payload={'bm': [ps[1]]}))
                    if c:
                        split.append(dict(o, ledd=c, ledd_to=None, ledd_new=False, payload={'bm': [ps[2]]}))
        elif (o['act'] == 'set' and o.get('ledd') and o.get('ledd_to') and not o.get('pkt') and not o.get('bokstav')
              and set(o['payload']) == {'bm'} and all(b[0] == 'p' for b in pl)
              and re.search(r'\b((?:%s)(?:(?:\s*,\s*|\s+og\s+)(?:%s))+)\s+ledd\s+(?:skal\s+)?lyde' % (ORDRE, ORDRE), o.get('src') or '')):
            # "§ 3-55 annet og fjerde ledd skal lyde:": the ledd named (not a range), one text each
            ns = [ORD[w] for w in re.findall(ORDRE, re.search(
                r'\b((?:%s)(?:(?:\s*,\s*|\s+og\s+)(?:%s))+)\s+ledd\s+(?:skal\s+)?lyde' % (ORDRE, ORDRE), o['src']).group(1))]
            if len(ns) == len(ps) and ns != list(range(ns[0], ns[0] + len(ns))):
                for n, b in zip(ns, ps):
                    split.append(dict(o, ledd=n, ledd_to=None, payload={'bm': [b]}))
            else:
                split.append(o)
        else:
            split.append(o)
    ops = split
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
        if bl[j][0] == 'd' and re.match(r'^(?:Det\s+)?[Gg]jeldende\s+.*\bblir\b.*\b(?:ledd|punktum)\.?$', bt):
            # "Det gjeldende annet ledd annet punktum blir annet ledd tredje punktum.": the instruction's own note on
            # where the old sentence goes ("nytt" already inserts), not law text
            j += 1
            continue
        if bl[j][0] == 'd' and re.match(r'^§\s*\d.*\b(?:vert\s+endra|blir\s+endra|endres)\s+slik:?$', bt):
            break  # "§ 102 nr. 1 vert endra slik:": the next instruction
        if bl[j][0] in ('d', 'p') and re.match(r'^Med\s+virkning\s+fra\b.*\boppheves\s+følgende\s+lover\b', bt):
            break  # "Med virkning fra ... oppheves følgende lover: 1) ...": the amending law's own repeal clause
        if bl[j][0] in ('d', 'p') and re.match(r'^\d+\.\s+[Ll]ova?\s+\d+\.\s+\w+\s+\d{4}\s+nr\.?\s*\d+\b[^§:]*?\s+skal\s+§[^:]*\blyde:$', bt):
            break  # "23. lov 26. mars 2010 nr. 9 om vergemål skal § 39 ... lyde:": the next item of a list of laws
        if bl[j][0] in ('d', 'p') and re.match(r'^\d+\.\s+[Ll]ova?\s+\d+\.\s+\w+\s+\d{4}\s+nr\.?\s*\d+\b[^§:]*?\s+§\s*\d[^:§]*?\b(?:skal\b[^:§]{0,60}?\blyde:|oppheves\.?)$', bt):
            break  # "25. Lov 27. mai 2016 nr. 14 om skatteforvaltning § 7-3 første ledd bokstav h og i skal lyde:"
        if bl[j][0] == 'p' and len(bl[j][1]) > 1 and SUBST_LIST.match(bl[j][1][0]):
            break  # a substitution sentence printed with its list of provisions as one ledd
        if bl[j][0] == 'd' and LEDD_ONLY.match(bt):
            break  # "Annet ledd oppheves. Nåværende tredje ledd blir nytt annet ledd.": the next instruction
        if bl[j][0] == 'd' and (move_pairs(bt) or AMEND_ITEM.match(bt)):
            break  # "Gjeldende §§ 8-14 og 8-15 blir ...", "§ 16-3 nr. 32 om endringer i skattebetalingsloven:"
        if bl[j][0] in ('d', 'p') and re.match(r'^I\s+lovens\s+del\s+[IVXL]+\s+om\s+endring(?:er|ar)?\s+i\s+lov\s.*?\s(?:skal\s+§|føyes\s+ny\s+§)', bt):
            break  # "I lovens del I om endringer i lov 10. april 2015 nr. 17 ... skal § 11-19 tredje ledd lyde:"
        if bl[j][0] == 'd' and re.match(r'^Lovens\s+del\s+[IVXL]+(?:\s+til\s+[IVXL]+)?(?:\s+[A-ZÆØÅ][^.:]*)?\s+oppheves\.', bt):
            # "Lovens del II oppheves. Del III blir del II." (LOV-2025-04-10-11): an amendment of the amending law;
            # "Lovens del II Ikrafttredelse og overgangsregler oppheves." (eiendomsmeglingsloven, LOV-2017-12-15-106)
            break
        if bl[j][0] == 'd' and re.match(r'^I\s+kapittel\s+\S+\s+gjøres\s+følgende\s+endring(?:er)?:$', bt):
            break  # "I kapittel 19 gjøres følgende endring:" (LOV-2009-05-08-27): the next instructions' heading
        if bl[j][0] == 'd' and re.match(r'^I\s+kapitlene\s.*\bskal\s+følgende\s+paragrafer\s+lyde:$', bt):
            break  # "I kapitlene 34 og 35 skal følgende paragrafer lyde:" (LOV-2009-05-08-27): the next instructions
        if bl[j][0] == 'd' and re.match(r'^I\s+(?:oppregningen|opplistingen)\s+i\s+§', bt):
            break  # "I oppregningen i § 196 ... føyes det til ...": an instruction for another provision
        if bl[j][0] in ('d', 'p') and is_instr(bt) and (bt.startswith('§') or bt.startswith('Ny') or bt.startswith('Nåværende') or bt.startswith('Overskrift')
                                                       or bt.startswith('Følgende') or bt.startswith('I lov ') or bt.startswith('Grunnloven')):
            break
        if bl[j][0] in ('d', 'p') and (is_target(bt) or bt.startswith('Nåværende') or SUBST_LIST.match(bt)
                                       or SUBST_INLINE.match(bt) or STRUCT.match(bt) or SUBST_VERB.match(bt) or SUBST_WORD_FIRST.match(bt)
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
    r'^(?:Nye\s+§§\s*%s\s+til\s+%s\s+skal\s+lyde|(?:Nytt|Ny|Nye)\s+kapit(?:tel|ler)\b|Kapittel\s+%s\s+(?:skal\s+lyde|oppheves)|Kapittel\s+\d+\s?[A-Z]?\s+med\s+§§[^:]*\sskal\s+lyde|Kapitlene\s|Lovens\s+\w+\s+del\s+skal\s+lyde'
    r'|(?:Etter\s+§\s*%s\s+skal\s+)?[Nn]y\s+(?:\w+\s+)?del\b.*lyde|(?:Ny\s+)?(?:[Oo]verskrift(?:en|a)?|Paragrafoverskrift(?:en|a)|Kapitteloverskrift(?:en|a))\s+(?:til|i|for)\s'
    r'|§§\s.*oppheves|I\s+(?:avsnitt\s+[IVXL]+\s+i\s+)?kapittel\s+%s\s+skal\s+ny\s+§|\w+\s+del\s+skal\s+lyde|(?:De delene av\s+)?§\s*%s\b[^:]*?\bblir\s+§\s*%s,?\s+og\s+skal\s+lyde'
    r'|I den alminnelige del(?:en)? fjernes alle punktum i paragrafoverskriftene'
    r'|(?:I\s+)?[Kk]apittel\s+\d+(?:\s?[A-Z])?\s+(?:skal\s+)?nytt\s+avsnitt\s|(?:Etter|Foran)\s+§\s*\d+(?:\s?[a-z])?\s+skal\s+nytt\s+avsnitt\s'
    r'|Nåværende\s+kapittel\s+\d+(?:\s?[A-Z])?\s+blir\s+(?:nytt\s+)?kapittel\s'
    r'|Kapittel\s+(?:[IVXL]+|\d+(?:\s?[A-Z](?![a-zæøå]))?)\s+[Oo]verskrift(?:en|a)\s+skal\s+lyde'
    r'|Nåværende\s+§\s*%s\s+blir\s+(?:ny\s+)?§\s*%s\.?$'
    r'|I\s+§\s*\d+(?:\s?[a-z])?\s+skal\s+(?:paragraf)?overskrift(?:en|a)\s+lyde'
    r'|I\s+kapittel\s+\d+(?:\s?[A-Z])?\s+avsnitt\s+[IVXL]+\s+skal\s+ny\s+§'
    r'|Nåværende\s+§\s*%s\s+blir\s+(?:ny\s+)?§\s*%s\b.*skal\s+lyde|§\s*%s\s+(?:[Pp]aragraf)?[Oo]verskrift(?:en|a)\s+skal\s+lyde)' % (NUM, NUM, NUM, NUM, NUM, NUM, NUM, NUM, NUM, NUM, NUM, NUM))


def move_pairs(t):
    """'Gjeldende §§ 8-14 og 8-15 blir § 8-15 og ny § 8-16.', 'Nåværende §§ 8-12 til 8-14 blir §§ 8-13 til ny 8-15.',
    'Nåværende § 7-11 til § 7-13 blir § 7-13 og ny § 7-14 og § 7-15.', 'Nåværende § 14-12 blir § 14-13, og nåværende
    § 14-13 blir ny § 14-14.' -> [(old, new), ...] (paragraphs moved to new numbers, their text unchanged), else None.
    Ranges are expanded only between plain numbers."""
    if not re.match(r'^(?:Nåværende|Gjeldende|Noverande)\s+§', t) or re.search(
            r'\b(?:ledd|punktum|bokstav|lyde|kapit\w*|nr\.?|del|avsnitt)\b', t):
        return None
    pairs = []
    for cl in re.split(r',?\s+og\s+(?=(?:nåværende|gjeldende|noverande)\s+§)', t.rstrip(' .')):
        m = re.match(r'^(?:Nåværende|Gjeldende|Noverande|nåværende|gjeldende|noverande)\s+(.*?)\s+(?:blir|vert)\s+(.*)$', cl)
        if not m:
            return None
        sides = []
        for side in m.groups():
            side = re.sub(r'§§?|\bnye?\b|\bnytt\b', ' ', side)
            nums = []
            for part in re.split(r'\s*,\s*|\s+og\s+', side.strip()):
                part = part.strip()
                r = re.match(r'^(\d+)\s+til\s+(\d+)$', part)
                if r and int(r.group(1)) < int(r.group(2)) and int(r.group(2)) - int(r.group(1)) < 50:
                    nums += [str(n) for n in range(int(r.group(1)), int(r.group(2)) + 1)]
                elif re.match(r'^%s$' % NUM, part):
                    nums.append(norm_num(part))
                else:
                    return None
            sides.append(nums)
        if len(sides[0]) != len(sides[1]) or not sides[0]:
            return None
        pairs += list(zip(*sides))
    return pairs


def struct_op(t):
    op = {'src': t, 'num': None, 'lang': None, 'act': 'struct'}
    if t.startswith('I den alminnelige del'):
        op.update(kind='strip_title_dots', key='del-1')
        return op
    # "§ 1-7 Overskriften skal lyde:" (LOV-2019-06-21-31), "I § 21-19 skal overskriften lyde:" (LOV-2017-02-10-4)
    m = (re.match(r'^§\s*(%s)\s+(?:[Pp]aragraf)?[Oo]verskrift(?:en|a)\s+skal\s+lyde' % NUM, t)
         or re.match(r'^I\s+§\s*(%s)\s+skal\s+(?:paragraf)?overskrift(?:en|a)\s+lyde' % NUM, t))
    if m:
        op.update(kind='para_title', num=norm_num(m.group(1)))
        return op
    m = re.match(r'^Kapittel\s+([IVXL]+|\d+(?:\s?[A-Z](?![a-zæøå]))?)\s+[Oo]verskrift(?:en|a)\s+skal\s+lyde', t)
    if m:  # "Kapittel VII Overskriften skal lyde:" (naturmangfoldloven), "Kapittel 6 overskriften skal lyde:" (barnevernsloven)
        op.update(kind='heading', key=L.head_key('Kapittel ' + m.group(1).replace(' ', '')))
        return op
    m = re.match(r'^Nåværende\s+§\s*(%s)\s+blir\s+(?:ny\s+)?§\s*(%s)\.?$' % (NUM, NUM), t)
    if m:
        # "Nåværende § 7-11 blir ny § 7-12.": the paragraph moves to the new number, its text unchanged
        op.update(kind='move_para', old=norm_num(m.group(1)), num=norm_num(m.group(2)))
        return op
    m = re.match(r'^(?:De delene av\s+|Nåværende\s+)?§\s*(%s)\b[^:]*?\bblir\s+(?:ny\s+)?§\s*(%s)\b.*?skal\s+lyde' % (NUM, NUM), t)
    if m:
        op.update(kind='renumber', old=norm_num(m.group(1)), num=norm_num(m.group(2)))
        return op
    m = re.match(r'^(\w+)\s+del\s+skal\s+lyde', t)
    if m and m.group(1).lower() in L.PART_ORD:
        op.update(kind='replace_part', key=L.head_key(m.group(1).capitalize() + ' del'))
        return op
    m = re.match(r'^I\s+(?:avsnitt\s+([IVXL]+)\s+i\s+)?kapittel\s+(%s)\s+skal\s+ny\s+§\s*(%s)\s+lyde' % (NUM, NUM), t)
    if m:
        chap = L.head_key('Kapittel ' + m.group(2).replace(' ', ''))
        if m.group(1) and chap:  # "I avsnitt II i kapittel 5 skal ny § 44 lyde:" (samvirkelova)
            chap += '-avsnitt-%02d' % L.roman(m.group(1))
        op.update(kind='para', chap=chap, num=norm_num(m.group(3)))
        return op
    m = re.match(r'^I\s+kapittel\s+(%s)\s+avsnitt\s+([IVXL]+)\s+skal\s+ny\s+§\s*(%s)\s+lyde' % (NUM, NUM), t)
    if m:  # "I kapittel 14 avsnitt III skal ny § 14-17 lyde:" (finansforetaksloven, LOV-2022-04-08-20)
        chap = L.head_key('Kapittel ' + m.group(1).replace(' ', ''))
        op.update(kind='para', chap=chap + '-avsnitt-%02d' % L.roman(m.group(2)) if chap else None,
                  num=norm_num(m.group(3)))
        return op
    m = re.match(r'^§§?\s+(.*?)\s+oppheves', t)
    if m:
        op.update(kind='del_paras', ranges=para_ranges(m.group(1)))
        return op
    m = re.match(r'^Kapittel\s+(%s)\s+oppheves' % NUM, t)
    if m:
        op.update(kind='del_chapter', key=L.head_key('Kapittel ' + m.group(1).replace(' ', '')))
        return op
    m = (re.match(r'^Kapittel\s+(%s)\s+skal\s+lyde' % NUM, t)
         # "Kapittel 2 A med §§ 2 A-1 til 2 A-4 og nye §§ 2 A-5 til 2 A-7 skal lyde:" (arbeidsmiljøloven 2019)
         or re.match(r'^Kapittel\s+(\d+(?:\s?[A-Z])?)\s+med\s+§§[^:]*\sskal\s+lyde', t))
    if m:
        op.update(kind='replace_chapter', key=L.head_key('Kapittel ' + m.group(1).replace(' ', '')))
        return op
    m = re.match(r'^Lovens\s+(\w+)\s+del\s+skal\s+lyde', t)
    if m:
        op.update(kind='replace_part', key=L.head_key(m.group(1).capitalize() + ' del'))
        return op
    m = re.match(r'^(?:Ny\s+)?(?:[Oo]verskrift(?:en|a)?|Paragrafoverskrift(?:en|a)|Kapitteloverskrift(?:en|a))\s+(?:til|i|for)\s+(?:nytt\s+|ny\s+)?(.*?)\s+skal\s+lyde', t)
    if m:
        what = m.group(1)
        pm = re.match(r'^§\s*(%s)$' % NUM, what)
        if pm:
            op.update(kind='para_title', num=norm_num(pm.group(1)))
            return op
        km = re.match(r'^(?:lovens\s+)?kapittel\s+([IVXL]+)$', what)  # "Overskriften i lovens kapittel III"
        if km:
            op.update(kind='heading', key=L.head_key('Kapittel ' + km.group(1)))
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
        km = re.match(r'^(?:lovens\s+)?(\w+)\s+del$', what)  # "Overskriften til lovens fjerde del" (LOV-2014-06-20-52)
        if km:
            op.update(kind='heading', key=L.head_key(km.group(1).capitalize() + ' del'))
            return op
        raise ReplayError('cannot read heading instruction: ' + t)
    m = (re.match(r'^Kapittel\s+(\d+(?:\s?[A-Z])?)\s+nytt\s+avsnitt\s+[IVXL]+(?:\s?[A-Z])?\b[^:]*?\s+skal\s+lyde', t)
         or re.match(r'^I\s+kapittel\s+(\d+(?:\s?[A-Z])?)\s+skal\s+nytt\s+avsnitt\s+[IVXL]+(?:\s?[A-Z])?\s+lyde', t))
    if m:  # "Kapittel 11 nytt avsnitt III med §§ 11-16 til 11-20 skal lyde:" (finansforetaksloven, LOV-2021-04-23-22),
        # "I kapittel 13 skal nytt avsnitt IV lyde:" (LOV-2019-12-06-77): a sub-section with its paragraphs
        op.update(kind='add', chapter=L.head_key('Kapittel ' + m.group(1).replace(' ', '')))
        return op
    m = re.match(r'^(Etter|Foran)\s+§\s*(%s)\s+skal\s+nytt\s+avsnitt\s+[IVXL]+(?:\s?[A-Z])?(?:\s+i\s+kapittel\s+\S+)?\s+lyde' % NUM, t)
    if m:  # "Etter § 20-31 skal nytt avsnitt VI A lyde:" + its heading only (LOV-2021-04-23-22), "Foran § 16-1 skal
        # nytt avsnitt I i kapittel 16 lyde:" (LOV-2021-12-22-163)
        op.update(kind='avsnitt_after', after=norm_num(m.group(2)), before=m.group(1) == 'Foran')
        return op
    m = re.match(r'^Nåværende\s+kapittel\s+(\d+(?:\s?[A-Z])?)\s+blir\s+(?:nytt\s+)?kapittel\s+(\d+(?:\s?[A-Z])?)\.?$', t)
    if m:  # "Nåværende kapittel 20 blir nytt kapittel 20A." (LOV-2018-03-23-2)
        op.update(kind='move_chapter', old=m.group(1), new=m.group(2))
        return op
    if re.match(r'^(?:Nytt|Ny|Nye)\s+kapit', t) or re.search(r'[Nn]y\s+(?:\w+\s+)?del\b', t):
        op.update(kind='add')
        return op
    m = re.match(r'^Nye\s+§§\s*(%s)\s+til\s+(%s)\s+skal\s+lyde' % (NUM, NUM), t)
    if m:  # "Nye §§ 13-3 til 13-5 skal lyde:" (opplæringslova, LOV-2024-06-14-36): new paragraphs, one after another
        op.update(kind='new_paras', lo=norm_num(m.group(1)), hi=norm_num(m.group(2)))
        return op
    # "Kapitlene 16-18 skal lyde:" (plan- og bygningsloven, LOV-2009-05-08-27); in an act numbered by chapter the
    # range reads as one token 9NNMMM
    m = (re.match(r'^Kapitlene\s+(\d+)\s*(?:-|–|til)\s*(\d+)\s+skal\s+lyde', t)
         or re.match(r'^Kapitlene\s+9(\d\d)(\d{3})\s+skal\s+lyde', t))
    if m and int(m.group(1)) < int(m.group(2)) <= int(m.group(1)) + 30:
        op.update(kind='replace_chapters', keys=['kapittel-%02d' % n for n in range(int(m.group(1)), int(m.group(2)) + 1)])
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
        elif b[0] == 'd' and b[2] == 'cont' and cur is not None and b[1] and cur['ledd'] and len(cur['ledd'][-1]) > 1:
            cur['ledd'][-1][0] = cur['ledd'][-1][0] + L.CONT + b[1]  # the ledd's words after its list (lovdata.CONT)
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
    elif kind == 'new_paras':
        items = payload_items(pl)
        lo, hi = _numkey(op['lo']), _numkey(op['hi'])
        if not items or any(it['t'] != 'p' for _, it in items) or _numkey(items[0][1]['num']) != lo \
                or _numkey(items[-1][1]['num']) != hi:
            raise ReplayError('payload is not §§ %s to %s: %s' % (op['lo'], op['hi'], op['src']))
        before = [k for k, v in state.items() if v['t'] == 'p' and k < items[0][0] and 'chap' in v]
        for k, it in items:
            if k in state:
                raise ReplayError('§ %s is already in the text (%s)' % (it['num'], op['src']))
            it['chap'] = state[max(before)]['chap'] if before else None
            state[k] = it
    elif kind == 'replace_chapters':
        # the chapters of the range, whichever exist, are replaced by the payload, which must hold exactly those
        # chapters (and may hold the part headings over them)
        items = payload_items(pl)
        got = [k for k, it in items if it['t'] == 'h' and k.startswith('kapittel-') and '-avsnitt-' not in k]
        if got != op['keys']:
            raise ReplayError('chapters %s, payload has %s: %s' % (op['keys'], got, op['src']))
        old = [k for k in op['keys'] if k in state]
        parent = state[old[0]].get('parent') if old else _guess_part(state, op['keys'][0])
        for c in old:
            for k in members(state, c) | {c}:
                state.pop(k, None)
        part = parent
        for k, it in items:
            if it['t'] == 'h':
                if k.startswith('del-'):
                    part = k
                    it['parent'] = None
                elif '-avsnitt-' in k:
                    it['parent'] = k.split('-avsnitt-')[0]
                else:
                    it['parent'] = part
            state[k] = it
    elif kind in ('replace_chapter', 'replace_part', 'add'):
        parent = None
        if kind in ('replace_chapter', 'replace_part'):
            if op['key'] not in state:
                raise ReplayError('no such chapter or part: ' + op['src'])
            parent = state[op['key']].get('parent')
            items = payload_items(pl)
            if kind == 'replace_chapter' and len(items) == 1 and items[0][0] == op['key'] and items[0][1]['t'] == 'h':
                # "Kapittel 7 skal lyde:" + only "Kapittel 7. Arbeidsmiljøutvalg": the chapter's heading (its
                # paragraphs are amended by the law's other instructions, arbeidsmiljøloven LOV-2006-12-15-69)
                it = items[0][1]
                it['parent'] = parent
                state[op['key']] = it
                return
            for k in members(state, op['key']) | {op['key']}:
                del state[k]
        part = parent
        for k, it in payload_items(pl, op.get('chapter')):
            if it['t'] == 'h':
                if k.startswith('del-'):
                    part = k
                    it['parent'] = None
                elif '-avsnitt-' in k:
                    it['parent'] = k.split('-avsnitt-')[0]
                else:
                    it['parent'] = part or _guess_part(state, k)
            state[k] = it
    elif kind == 'avsnitt_after':
        # a new sub-section heading after § N; the paragraphs after § N in the same sub-section now stand under it
        k0 = L.para_key(op['after'])
        if k0 not in state or not state[k0].get('chap'):
            raise ReplayError('§ %s is not in the text (%s)' % (op['after'], op['src']))
        chap = state[k0]['chap']
        items = payload_items(pl, chap)
        heads = [(k, it) for k, it in items if it['t'] == 'h']
        if len(heads) != 1 or '-avsnitt-' not in heads[0][0] or heads[0][0] in state:
            raise ReplayError('payload is not one new sub-section heading: ' + op['src'])
        hk, hit = heads[0]
        hit['parent'] = hk.split('-avsnitt-')[0]
        state[hk] = hit
        for k, v in list(state.items()):
            if v['t'] == 'p' and v.get('chap') == chap and (k >= k0 if op.get('before') else k > k0):
                state[k] = dict(v, chap=hk)
        for k, it in items:
            if it['t'] == 'p':
                it['chap'] = hk
                state[k] = it
    elif kind == 'move_chapter':
        # "Nåværende kapittel 20 blir nytt kapittel 20A.": the chapter, its sub-sections and paragraphs take the new
        # chapter number (the paragraphs' own numbers move by the law's next instruction)
        ok, nk = L.head_key('Kapittel ' + op['old'].replace(' ', '')), L.head_key('Kapittel ' + op['new'].replace(' ', ''))
        if not ok or not nk or ok not in state or nk in state:
            raise ReplayError('cannot move chapter %s to %s (%s)' % (op['old'], op['new'], op['src']))
        mem = members(state, ok)
        h = state.pop(ok)
        lab = re.sub(r'^(Kapit+el\s+)%s\b' % re.escape(op['old']), lambda mm: mm.group(1) + op['new'], h['label'])
        if lab == h['label']:
            raise ReplayError('cannot renumber the heading %r (%s)' % (h['label'], op['src']))
        state[nk] = dict(h, label=lab)
        for k in sorted(mem):
            v = state[k]
            if v['t'] == 'h':
                del state[k]
                state[nk + k[len(ok):]] = dict(v, parent=nk)
            else:
                c = v.get('chap')
                state[k] = dict(v, chap=nk + c[len(ok):] if c and c.startswith(ok) else c)
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
            # the new heading printed as an ordinary paragraph ("§ 25 overskrifta skal lyde:" + one line)
            ps = [b for b in pl if b[0] == 'p' and b[1]]
            if len(ps) == 1:
                txt = L.norm(ps[0][1][0] if isinstance(ps[0][1], list) else ps[0][1])
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
    elif kind == 'move_para':
        old = state.pop(L.para_key(op['old']), None)
        if old is None or L.para_key(op['num']) in state:
            raise ReplayError('cannot move § %s to § %s (%s)' % (op['old'], op['num'], op['src']))
        state[L.para_key(op['num'])] = dict(old, num=norm_num(op['num']))
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
    empty_head = None
    for b in pl:
        if b[0] == 'head' and not b[2] and not out:
            empty_head = b[1]
        if b[0] == 'p':
            out.append(list(b[1]))
        elif b[0] == 'd' and b[2] == 'cont' and b[1] and out and len(out[-1]) > 1:
            # as in the act's own text (lovdata.ledd_lines): the words after a list ride on the first line after CONT
            out[-1][0] = out[-1][0] + L.CONT + b[1]
        elif b[0] == 'd' and b[1] and b[1] != '–':
            out.append([b[1]])
        elif b[0] == 'head':
            title = b[2] or title
    if NUMBERED_LEDD[0] and len(out) == 1 and len(out[0]) > 1 and re.match(r'^1\)\s', out[0][0]):
        tops = [i for i, x in enumerate(out[0]) if re.match(r'^\d+\)\s', x)]
        if [int(re.match(r'^(\d+)', out[0][i]).group(1)) for i in tops] == list(range(1, len(tops) + 1)) and len(tops) > 1:
            # tvisteloven § 1-4 a (lov 16. juni 2017 nr. 63): the ledd printed as a list "1) ...", "2) ..."
            lines = out[0]
            out = [['(%d) %s' % (n + 1, re.sub(r'^\d+\)\s+', '', lines[a]))] + lines[a + 1:(tops[n + 1] if n + 1 < len(tops) else len(lines))]
                   for n, a in enumerate(tops)]
    if (empty_head and title is None and len(out) > 1 and len(out[0]) == 1 and len(out[0][0]) < 200
            and re.match(r'^[A-ZÆØÅ]', out[0][0]) and not re.search(r'[.:;,]$', out[0][0])):
        # "§ 2-13 skal lyde:" + "<h4>§ 2-13</h4><legalP>Myndighet til andre organer</legalP><legalP>Departementet
        # ...": the title printed as a first ledd (as lovdata.walk_act reads the act's own text)
        title, out = out[0][0], out[1:]
        NOTES.append((empty_head.replace('§', '').strip(), 'Norsk Lovtidend prints the title of the new text as a first '
                      'line of text after a heading that holds only the number; it is read as the title'))
    elif (NUMBERED_LEDD[0] and not empty_head and title is None and len(out) > 1 and len(out[0]) == 1
          and len(out[0][0]) < 200 and re.match(r'^[A-ZÆØÅ]', out[0][0]) and not re.search(r'[.:;,]$', out[0][0])
          and re.match(r'^\(1\)\s', out[1][0]) and pl and pl[0][0] == 'd'):
        # "§ 10-5 skal lyde:" + "Gjennomsnittsberegning av den alminnelige arbeidstid" + "(1) ..." (arbeidsmiljøloven,
        # lov 15. desember 2006 nr. 69): in an act that numbers its ledd, an unnumbered short first line before "(1)"
        # with no heading at all is the title
        title, out = out[0][0], out[1:]
        PAYLOAD_TITLE.append(title)
    return out, title


PAYLOAD_TITLE = []  # titles payload_ledd read from a first line before "(1)" (parse.py records them as decisions)


def apply_ops(state, ops, lang):
    """Apply one document's ops for one language ('bm' or 'nn'). Returns the set of keys changed."""
    changed = set()
    by_num = {}
    moved = []
    # "Nåværende § 45 oppheves." beside "Nåværende § 44 blir ny § 45.": the repeal names the current § 45, so it goes
    # before the move (samvirkelova, lov 28. mai 2021 nr. 51)
    if any(o['act'] == 'struct' and o.get('kind') == 'move_para' for o in ops):
        for op in [o for o in ops if o['act'] == 'del' and o['src'].startswith('Nåværende §') and o.get('ledd') is None
                   and o.get('pkt') is None and o.get('bokstav') is None and not (o['lang'] and o['lang'] != lang)]:
            if state.pop(L.para_key(op['num']), None) is None:
                raise ReplayError('§ %s is not in the text (%s)' % (op['num'], op['src']))
            changed.add(L.para_key(op['num']))
        ops = [o for o in ops if not (o['act'] == 'del' and o['src'].startswith('Nåværende §') and o.get('ledd') is None
                                      and o.get('pkt') is None and o.get('bokstav') is None)]
    # renumbering refers to the numbers before the amendment, so it goes before new chapters reuse them
    mv = [o for o in ops if o['act'] == 'struct' and o['kind'] == 'move_para' and not (o['lang'] and o['lang'] != lang)]
    if len(mv) > 1:
        # all moves name the numbers before the amendment: take every moved paragraph out first, then place them
        taken = []
        for op in mv:
            old = state.pop(L.para_key(op['old']), None)
            if old is None:
                raise ReplayError('cannot move § %s to § %s (%s)' % (op['old'], op['num'], op['src']))
            taken.append((op, old))
        for op, old in taken:
            if L.para_key(op['num']) in state:
                raise ReplayError('cannot move § %s to § %s (%s)' % (op['old'], op['num'], op['src']))
            state[L.para_key(op['num'])] = dict(old, num=norm_num(op['num']))
        ops = [o for o in ops if not any(o is x for x in mv)]
    for op in sorted([o for o in ops if o['act'] == 'struct'], key=lambda o: o['kind'] not in ('renumber', 'move_para')):
        if not (op['lang'] and op['lang'] != lang):
            apply_struct(state, op, lang)
    ops = [o for o in ops if o['act'] != 'struct']
    for op in [o for o in ops if o['act'] == 'subst_chap' and not (o['lang'] and o['lang'] != lang)]:
        # a word substitution in a chapter heading: the words after "Kapittel 7."
        key = L.chap_key(op['chapter'])
        if key not in state or state[key]['t'] != 'h':
            raise ReplayError('chapter %s is not in the text (%s)' % (op['chapter'], op['src'][:120]))
        lab = state[key]['label']
        mh = re.match(r'^(Kapit+el\s+\S+\.?\s+|\S+\.?\s+)(.*)$', lab)
        new = mh.group(1) + _subst_text(mh.group(2), op) if mh else lab
        if new == lab:
            WARN.append('substitution found nothing: kapittel %s %s' % (op['chapter'], op['src'][:120]))
        state[key] = dict(state[key], label=new)
        changed.add(key)
    ops = [o for o in ops if o['act'] != 'subst_chap']
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


def _ledd_reorder(item, ops, renums, lang, num):
    # "§ 10-11 tredje ledd skal lyde: ... Nåværende § 10-11 tredje ledd blir femte ledd. Nåværende § 10-11 femte til
    # åttende ledd blir sjette til niende ledd. § 10-11 niende ledd første punktum skal lyde: ..." (arbeidsmiljøloven,
    # lov 16. juni 2017 nr. 42): the old third ledd moves past the old fourth. Only when the renumbering changes the
    # order of the old ledd (otherwise the ordinary reading below applies): every position is built from the old ledd
    # (moved or kept), the ledd the law sets, and nothing else; sentence and letter edits then use the new numbers
    # where the number is a renumbering target. None when the law does not reorder or anything does not fit.
    n = len(item['ledd'])
    led = [r for r in renums if r['ledd'] is not None and r.get('pkt') is None and r.get('bokstav') is None
           and r.get('renum_to') and r['renum_to'][0] == 'ledd']
    if not led or len(led) != len(renums):
        return None
    mp = {}
    for r in led:
        a, b = r['ledd'], r.get('ledd_to') or r['ledd']
        for i in range(a, b + 1):
            mp[i] = r['renum_to'][1] + i - a
    order = sorted(range(1, n + 1), key=lambda i: mp.get(i, i))  # the old ledd by their new places
    if order == list(range(1, n + 1)) or any(i > n for i in mp):
        return None
    lev = [o for o in ops if o['act'] in ('set', 'del') and o['ledd'] is not None and o['pkt'] is None
           and o['bokstav'] is None and not o.get('intro') and o not in renums]
    other = [o for o in ops if o not in lev and o not in renums]
    final = {}
    for i in range(1, n + 1):
        if i not in mp:
            final[i] = item['ledd'][i - 1]
    for i, j in mp.items():
        if j in final:
            return None
        final[j] = item['ledd'][i - 1]
    for o in lev:
        if o['act'] == 'del':
            if o['ledd'] in mp or o['ledd'] not in final or o.get('ledd_to'):
                return None
            del final[o['ledd']]
            continue
        new = payload_ledd(o['payload'][lang])[0]
        if len(new) != (o.get('ledd_to') or o['ledd']) - o['ledd'] + 1:
            return None
        for j, ld in enumerate(new):
            p = o['ledd'] + j
            if p in mp.values():
                return None  # an old ledd moved here
            final[p] = ld
    if sorted(final) != list(range(1, len(final) + 1)):
        return None
    targets = set(mp.values())
    rest = []
    for o in other:
        if o['ledd'] is not None and o['ledd'] not in targets and o['ledd'] in mp:
            # an old number that moved: where it went
            o = dict(o, ledd=mp[o['ledd']])
        rest.append(o)
    out = dict(item)
    out['ledd'] = [list(final[p]) for p in sorted(final)]
    NOTES.append((num, 'the law moves ledd past one another (%s); the ledd are placed by their new '
                  'numbers, and its later instructions on them use the new numbers' % '; '.join(r['src'] for r in led)))
    return out, rest


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
        hit = 0
        for ld in item['ledd']:
            for j, line in enumerate(ld):
                if re.match(r'^%s[).]\s' % o['letter'], line) and line.endswith('.'):
                    if o.get('after') is not None:
                        # the full stop after the words named (a closing parenthesis may stand between)
                        if not re.search(re.escape(o['after']) + r'\)?\.$', line):
                            continue
                        ld[j] = line[:-1] + o['to']
                    else:
                        ld[j] = line[:-1] + ','
                    hit += 1
        if o.get('after') is not None and hit != 1:
            raise ReplayError('cannot find the full stop: ' + o['src'])
        state[key] = item
    ops = [o for o in ops if o['act'] != 'item_punct']
    for o in [o for o in ops if o['act'] == 'pkt_to_ledd']:
        if key not in state:
            raise ReplayError('§ %s is not in the text (%s)' % (num, o['src']))
        item = copy.deepcopy(state[key])
        x = o['ledd'] - 1
        if o['to_ledd'] != o['ledd'] + 1 or x >= len(item['ledd']):
            raise ReplayError('cannot move the sentence: ' + o['src'])
        ld = item['ledd'][x]
        sents = sentences(ld[0])
        if o['pkt'] != len(sents) or o['pkt'] < 2:
            raise ReplayError('the sentence moved is not the last of its ledd: ' + o['src'])
        # the last sentence goes with the list that follows it
        item['ledd'][x:x + 1] = [[' '.join(sents[:o['pkt'] - 1])], [sents[o['pkt'] - 1]] + list(ld[1:])]
        state[key] = item
    ops = [o for o in ops if o['act'] != 'pkt_to_ledd']
    for o in [o for o in ops if o['act'] == 'ledd_to_pkt']:
        if key not in state:
            raise ReplayError('§ %s is not in the text (%s)' % (num, o['src']))
        item = copy.deepcopy(state[key])
        x, z = o['ledd'] - 1, o['to_ledd'] - 1
        if z != x - 1 or x >= len(item['ledd']) or len(item['ledd'][x]) != 1:
            raise ReplayError('cannot join the ledd: ' + o['src'])
        ld = item['ledd'][z]
        n = len(sentences(ld[0].replace(L.CONT, ' ')))
        if o['pkt'] != n + 1:
            raise ReplayError('the ledd joined is not the next punktum: ' + o['src'])
        op = {'act': 'set', 'pkt': o['pkt'], 'pkt_new': True, 'semikolon': False, 'src': o['src'],
              'payload': {lang: [('p', [item['ledd'][x][0]], None)]}}
        item['ledd'][z] = [_apply_sentences(ld[0], [op], lang, num, len(ld) > 1)] + list(ld[1:])
        del item['ledd'][x]
        state[key] = item
    ops = [o for o in ops if o['act'] != 'ledd_to_pkt']
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

    def _last_pkt(o):
        # the number of sentences of the ledd, counted as _apply_sentences counts them (both sides of the list)
        k = (o['ledd'] or 1) - 1
        if k >= len(item['ledd']):
            raise ReplayError('no such ledd for: ' + o['src'])
        before, _, after = item['ledd'][k][0].partition(L.CONT)
        before = re.sub(r'^\(\d+\)\s+', '', before)
        n = len(sentences(before)) + (len(sentences(after)) if after else 0)
        return dict(o, pkt=n + 1 if o.get('pkt_new') else n, pkt_to=None, ledd=o['ledd'] or 1)
    ops = [_last_pkt(o) if o.get('last_pkt') else o for o in ops]
    for o in ops:
        if o['act'] == 'set' and re.search(r'\b(?:paragraf)?overskrift(?:en|a)?\s+og\s', o['src']):
            h = next((b[2] for b in o['payload'].get(lang, []) if b[0] == 'head' and b[2]), None)
            if h:
                item = dict(item, title=h)
    renums = [op for op in ops if op['act'] == 'renum']
    moved = _ledd_reorder(item, ops, renums, lang, num)
    if moved is not None:
        # the law moves ledd past one another: build the new order, then its sentence/letter edits on the new numbers
        new_item, rest = moved
        state[key] = new_item
        if rest:
            _apply_para(state, key, num, rest, lang)
        return
    # "andre ledd tredje punktum skal lyde: ..." with "Nåværende andre ledd tredje punktum blir nytt fjerde punktum"
    # in the same law: the new sentence is inserted, the old one moves on (as becomes_insert does for ledd)
    ops = [dict(o, pkt_new=True) if o['act'] == 'set' and o.get('pkt') is not None and not o.get('pkt_new')
           and any(r.get('pkt') == o['pkt'] and r['ledd'] == o['ledd'] and r.get('renum_to')
                   and r['renum_to'][0] == 'punktum' for r in renums) else o for o in ops]
    # "annet ledd nytt tredje og fjerde punktum skal lyde" with "Nåværende fjerde punktum blir nytt femte punktum":
    # two new sentences, but the old fourth moves on by one, so the old third is the one they replace
    def _replaced(o):
        if not (o['act'] == 'set' and o.get('pkt') is not None and o.get('pkt_new')):
            return o
        later = sorted((r['pkt'], r['renum_to'][1]) for r in renums if r['ledd'] == o['ledd'] and r.get('pkt')
                       and r.get('renum_to') and r['renum_to'][0] == 'punktum' and r['pkt'] > o['pkt'])
        if not later:
            return o
        n = (o.get('pkt_to') or o['pkt']) - o['pkt'] + 1
        gone = n - (later[0][1] - later[0][0])
        if gone <= 0 or o['pkt'] + gone > later[0][0]:
            return o
        return dict(o, pkt_new=False, pkt_to=(o['pkt'] + gone - 1) if gone > 1 else None)
    ops = [_replaced(o) for o in ops]

    # "første ledd første og andre punktum skal lyde" with "Nåværende andre til fjerde punktum blir tredje til femte
    # punktum" (plan- og bygningsloven § 32-9, LOV-2017-06-21-97): the old second sentence moves on, so the new text
    # replaces only the first; its second sentence is new
    def _shifted(o):
        if not (o['act'] == 'set' and o.get('pkt') is not None and o.get('pkt_to') and not o.get('pkt_new')):
            return o
        hit = [r for r in renums if r['ledd'] == o['ledd'] and r.get('pkt') and r.get('renum_to')
               and r['renum_to'][0] == 'punktum' and o['pkt'] < r['pkt'] <= o['pkt_to']
               and r['renum_to'][1] - r['pkt'] == o['pkt_to'] - r['pkt'] + 1]
        if len(hit) != 1:
            return o
        return dict(o, pkt_to=(hit[0]['pkt'] - 1) if hit[0]['pkt'] - 1 > o['pkt'] else None)
    ops = [_shifted(o) for o in ops]

    # "§ 15-7 andre ledd oppheves. / Nåværende tredje og fjerde ledd blir andre og tredje ledd. / § 15-7 tredje ledd
    # første punktum skal lyde: ..." (barnevernsloven, LOV-2025-06-20-39): an instruction printed after the law repeals
    # a ledd and renumbers the rest names the ledd by its new number
    gone = [o for o in ops if o['act'] == 'del' and o.get('ledd') and not o.get('ledd_to') and o.get('pkt') is None
            and o.get('bokstav') is None]

    def _after_renum(i, o):
        if not (gone and o['act'] == 'set' and o.get('ledd') and not o.get('ledd_new') and o.get('bokstav') is None
                and not o.get('ledd_to')):
            return o
        for r in renums:
            if not (r.get('renum_to') and r['renum_to'][0] == 'ledd' and r.get('pkt') is None and r.get('ledd')
                    and any(x is r for x in ops[:i])):
                continue
            lo, hi, to = r['ledd'], r.get('ledd_to') or r['ledd'], r['renum_to'][1]
            if to < lo and to <= o['ledd'] <= to + hi - lo:
                old = lo + o['ledd'] - to
                NOTES.append((num, 'the law repeals a ledd and renumbers the rest ("%s"); its instruction printed after '
                              'that ("%s") names the ledd by its new number, the old %s ledd' % (
                                  r['src'], o['src'], ORDN_EN.get(old, old))))
                return dict(o, ledd=old)
        return o
    ops = [_after_renum(i, o) for i, o in enumerate(ops)]
    relabel = {}
    for r in renums:
        m = re.search(r'bokstav\s+([a-z](?:\s*(?:,|og|til)\s*(?:ny\s+)?(?:bokstav\s+)?[a-z])*)\s+blir\s+.*?bokstav\s+'
                      r'([a-z](?:\s*(?:,|og|til)\s*(?:ny\s+)?(?:bokstav\s+)?[a-z])*)\.?$', r['src'])

        def _letters(x):
            x = re.sub(r'\b(?:ny|bokstav)\s+', '', x)
            out = []
            for part in re.split(r'\s*(?:,|\bog\b)\s*', x):
                ab = re.findall(r'\b[a-z]\b', part)
                if re.search(r'\btil\b', part) and len(ab) == 2:
                    out += [chr(c) for c in range(ord(ab[0]), ord(ab[1]) + 1)]
                else:
                    out += ab
            return out
        if m:
            old, new = _letters(m.group(1)), _letters(m.group(2))
            if len(old) != len(new):
                raise ReplayError('cannot read letter renumbering: ' + r['src'])
            relabel[id(r)] = (r['ledd'], dict(zip(old, new)))
    if relabel:
        # the letters a law deletes go first (old letters), then the renumbering, then the new texts (new letters)
        ops = ([o for o in ops if o['act'] == 'del' and o.get('bokstav') and o.get('pkt') is None]
               + [o for o in ops if id(o) in relabel]
               + [o for o in ops if not (o['act'] == 'del' and o.get('bokstav') and o.get('pkt') is None) and id(o) not in relabel])
    slots = [{'orig': i, 'ledd': l, 'dead': False} for i, l in enumerate(item['ledd'])]
    inserts = []
    for op in ops:
        if op['act'] == 'renum' and id(op) in relabel:
            ledd, mp = relabel[id(op)]
            has = [s for s in slots if not s['dead'] and (ledd is None or s['orig'] == ledd - 1)
                   and any(re.match(r'^%s[).]\s' % a, x) for x in s['ledd'][1:] for a in mp)]
            if len(has) != 1:
                raise ReplayError('no single list for: ' + op['src'])
            s = has[0]
            out = [s['ledd'][0]]
            for x in s['ledd'][1:]:
                m = re.match(r'^([a-z])([).]\s.*)$', x, re.S)
                if m and m.group(1) in mp:
                    out.append(mp[m.group(1)] + m.group(2))
                elif m and m.group(1) in mp.values():
                    continue  # its letter goes to another item and nothing takes its place: the old text is gone
                else:
                    out.append(x)
            s['ledd'] = out
            continue
        if op['act'] == 'renum':
            continue
        if op.get('intro') and op['act'] == 'set' and op['bokstav'] is None:
            # 'første ledd innledningen skal lyde:': the words before the list
            k = (op['ledd'] or 1) - 1
            tgt = [s for s in slots if s['orig'] == k]
            if not tgt:
                raise ReplayError('no such ledd for: ' + op['src'])
            txt = ' '.join(l for ld in payload_ledd(op['payload'][lang])[0] for l in ld)
            old0 = tgt[0]['ledd'][0]
            if L.CONT in old0:
                txt = txt + L.CONT + old0.split(L.CONT, 1)[1]  # the words after the list stay
            tgt[0]['ledd'] = [txt] + list(tgt[0]['ledd'][1:])
            continue
        if op['ledd'] is not None and op['pkt'] is None and op['bokstav'] is None:
            k = op['ledd'] - 1
            # (also inside a renumbered range: "Nåværende andre og tredje ledd blir fjerde og femte ledd" + "tredje ledd
            # skal lyde", eierseksjonsloven § 38), when no renumbered ledd lands on that number ("nåværende annet til
            # fjerde ledd blir tredje til nytt femte ledd" + "tredje ledd skal lyde" sets the old second, finansforetaksloven
            # § 20-25, lov 18. juni 2021 nr. 100)
            _rl = [r for r in renums if r['ledd'] is not None and r.get('renum_to') and r['renum_to'][0] == 'ledd']
            _lands = {r['renum_to'][1] + i for r in _rl for i in range((r.get('ledd_to') or r['ledd']) - r['ledd'] + 1)}
            becomes_insert = any(r['ledd'] == op['ledd'] for r in _rl) or (
                op['ledd'] not in _lands and any(r['ledd'] < op['ledd'] <= (r.get('ledd_to') or r['ledd']) for r in _rl))
            if op['act'] == 'set':
                one = payload_ledd(op['payload'][lang])[0]
                if op['ledd_to'] is None and len(one) == 2 and len(one[0]) > 1 and len(one[1]) == 1:
                    # one ledd set, printed as a list and then the words after it: those ride on the ledd's
                    # first line after CONT, as in the act's own text (lovdata.ledd_lines)
                    one = [[one[0][0] + L.CONT + one[1][0]] + one[0][1:]]
                    op = dict(op, payload={lang: [('p', one[0], None)]})
            if op['act'] == 'set' and op['ledd_new'] and op['ledd_to'] and not renums:
                new = payload_ledd(op['payload'][lang])[0]
                old = [s for s in slots if s['orig'] == k and not s['dead']]
                strip = lambda x: re.sub(r'^\(\d+\)\s+', '', x)
                if (len(new) == op['ledd_to'] - op['ledd'] + 1 and len(new) > 1 and old
                        and difflib.SequenceMatcher(None, strip(old[0]['ledd'][0]), strip(new[-1][0])).ratio() >= 0.6
                        and all(difflib.SequenceMatcher(None, strip(old[0]['ledd'][0]), strip(x[0])).ratio() < 0.6
                                for x in new[:-1])):
                    # "§ 10-2 nytt tredje og fjerde ledd skal lyde:" whose new fourth ledd revises the old third ledd
                    # (tvisteloven, lov 11. mai 2023 nr. 13): the old third ledd is the one the new fourth replaces
                    inserts.append((k, new[:-1]))
                    old[0]['ledd'] = list(new[-1])
                    NOTES.append((num, 'the instruction "%s" gives %d new ledd, the last a revision of the ledd now at '
                                       'that place; that ledd is replaced by it, as in the consolidated text of Lovdata'
                                  % (op['src'], len(new))))
                    continue
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
            listed = [o for o in s['pkt_ops'] if o['act'] == 'set' and len(payload_ledd(o['payload'][lang])[0]) == 1
                      and len(payload_ledd(o['payload'][lang])[0][0]) > 1]
            if len(listed) == 1:
                # "første ledd annet punktum skal lyde: ... om den" + "a) ...", "b) ...": the sentence goes into the
                # ledd's first line, the list replaces the ledd's items
                lines = payload_ledd(listed[0]['payload'][lang])[0][0]
                one = [dict(o, payload={lang: [('p', [lines[0]], None)]}) if o is listed[0] else o for o in s['pkt_ops']]
                s['ledd'][0] = _apply_sentences(s['ledd'][0], one, lang, num, len(lines) > 1)
                s['ledd'] = [s['ledd'][0]] + list(lines[1:])
            else:
                s['ledd'][0] = _apply_sentences(s['ledd'][0], s['pkt_ops'], lang, num, len(s['ledd']) > 1)
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
    if op.get('in_letter') and op['bokstav'].isdigit():
        # "bokstav b nytt nr. 4": the numbers nested under that letter; only when the letter has its own numbered list
        # lines (otherwise the numbers are found in the whole list, as before)
        at = [i for i, x in enumerate(items) if re.match(r'^%s[).]\s' % op['in_letter'], x)]
        if len(at) == 1:
            j = at[0] + 1
            while j < len(items) and re.match(r'^\d+[).]\s', items[j]):
                j += 1
            if j > at[0] + 1:
                sub = {'ledd': [items[at[0]]] + items[at[0] + 1:j]}
                _apply_item(sub, dict(op, in_letter=None), lang)
                slot['ledd'] = [lines[0]] + items[:at[0]] + sub['ledd'] + items[j:]
                return
    labels = [re.match(r'^([a-z]|\d+)([).])\s', x) for x in items]
    style = next((m.group(2) for m in labels if m), ')')
    letters = [(op['bokstav'], op['bokstav_new'])] + op.get('bokstav_more', [])
    top_digit = op['bokstav'].isdigit()

    def is_sub(x):
        # a line of an item's own nested list: labelled in the other kind ("f) ... verv som" + "1) statsoverhode")
        m = re.match(r'^([a-z]|\d+)[).]\s', x)
        return bool(m) and m.group(1).isdigit() != top_digit

    def find(letter):
        return [i for i, x in enumerate(items) if re.match(r'^%s[).]\s' % letter, x) and not is_sub(x)]

    def sub_end(i):
        j = i + 1
        while j < len(items) and is_sub(items[j]):
            j += 1
        return j
    if (op.get('pkt') is not None and len(letters) == 1 and not op['bokstav_new']
            and re.search(r'bokstav\s+[a-z]\)?\s+(?:nytt\s+)?(?:%s)(?:\s+og\s+(?:nytt\s+)?(?:%s))?\s+punktum' % (ORDRE, ORDRE), op['src'])):
        idx = find(op['bokstav'])
        if not idx:
            raise ReplayError('no bokstav ' + op['bokstav'] + ': ' + op['src'])
        m = re.match(r'^(%s[).]\s)(.*)$' % op['bokstav'], items[idx[0]], re.S)
        items[idx[0]] = m.group(1) + _apply_sentences(m.group(2), [dict(op, bokstav=None)], lang, op.get('num'))
        slot['ledd'] = [lines[0]] + items
        return
    if op['act'] == 'del':
        for letter, _ in letters:
            idx = find(letter)
            if not idx:
                raise ReplayError('no bokstav ' + letter + ': ' + op['src'])
            del items[idx[0]:sub_end(idx[0])]
    else:
        pl = payload_ledd(op['payload'][lang])[0]
        texts = [l for ld in pl for l in ld]
        subs = None
        if len(texts) > 1 and any(is_sub(t) for t in texts[1:]) and not is_sub(texts[0]):
            # the new item(s) carry their own nested list: each sub-line stays a line under its item
            groups = []
            for t in texts:
                if is_sub(t) and groups:
                    groups[-1][1].append(t)
                else:
                    groups.append([t, []])
            texts, subs = [g[0] for g in groups], [g[1] for g in groups]
        lab = [bool(re.match(r'^(?:[a-z]|\d+)[).]\s', t)) for t in texts]
        if texts and not lab[0] and any(lab) and all(lab[lab.index(True):]) and sum(lab) == len(letters):
            # the new text quotes the ledd's opening words before the letter(s) it sets: only the letters are new
            if subs is not None:
                subs = subs[lab.index(True):]
            texts = texts[lab.index(True):]
        texts = [re.sub(r'^(?:[a-z]|\d+)[).]\s+', '', t) for t in texts]
        if subs is not None and len(texts) != len(letters):
            raise ReplayError('%d letters, %d texts with nested lists: %s' % (len(letters), len(texts), op['src']))
        if subs is None:
            subs = [[] for _ in letters]
        if len(letters) == 1:
            texts = [' '.join(texts)]
            if re.search(r'bokstav\s+[a-z]\)?\s+nytt\s+siste\s+ledd', op['src']):
                idx = find(letters[0][0])
                if not idx:
                    raise ReplayError('no bokstav ' + letters[0][0] + ': ' + op['src'])
                items[idx[0]] = items[idx[0]] + ' ' + texts[0]
                slot['ledd'] = [lines[0]] + items
                return
        if len(texts) != len(letters):
            raise ReplayError('%d letters, %d texts: %s' % (len(letters), len(texts), op['src']))
        for (letter, is_new), txt, sub in zip(letters, texts, subs):
            new = letter + style + ' ' + txt
            idx = find(letter)
            if idx and not is_new:
                items[idx[0]:sub_end(idx[0])] = [new] + sub
            elif idx and is_new:
                # "ny bokstav j" where a j exists: the new letter takes its place and the old ones move on by one
                # (j becomes k ...), as when the law says "nåværende bokstav j blir ny bokstav k"
                for i in range(idx[0], len(items)):
                    m = re.match(r'^([a-z]|\d+)([).]\s.*)$', items[i], re.S)
                    if m and not is_sub(items[i]):
                        a = m.group(1)
                        items[i] = (str(int(a) + 1) if a.isdigit() else chr(ord(a) + 1)) + m.group(2)
                items[idx[0]:idx[0]] = [new] + sub
            else:
                def lab_lt(x):
                    m = re.match(r'^([a-z]|\d+)[).]\s', x)
                    if not m or is_sub(x):
                        return False
                    a = m.group(1)
                    return int(a) < int(letter) if a.isdigit() and letter.isdigit() else a < letter
                prev = str(int(letter) - 1) if letter.isdigit() else chr(ord(letter) - 1)
                after = find(re.escape(prev))
                if any(is_sub(x) for x in items):
                    smaller = [i for i, x in enumerate(items) if lab_lt(x)]
                    pos = sub_end(after[0]) if len(after) == 1 else (sub_end(smaller[-1]) if smaller else 0)
                else:
                    pos = after[0] + 1 if len(after) == 1 else len([x for x in items if lab_lt(x)])
                items[pos:pos] = [new] + sub
    slot['ledd'] = [lines[0]] + items


def _apply_sentences(line, ops, lang, num, has_list=False):
    # the ledd's words after its list (after lovdata.CONT) go on counting its punktum; each sentence keeps its side
    before, _, after = line.partition(L.CONT)
    # a numbered ledd ("(2) Vedtak i årsmøtet ..."): the number is not part of its first sentence (samvirkelova § 52,
    # "andre ledd nytt første punktum")
    lnum = re.match(r'^\(\d+\)\s+', before)
    if lnum:
        before = before[lnum.end():]
    sl = [{'orig': i, 's': s, 'dead': False, 'after': i >= len(sentences(before))}
          for i, s in enumerate(sentences(before) + (sentences(after) if after else []))]
    inserts = []
    for op in ops:
        if op['act'] == 'renum':
            continue
        k = op['pkt'] - 1
        if op['act'] == 'set':
            pl = payload_ledd(op['payload'][lang])[0]
            txt = ' '.join(l for ld in pl for l in ld)
            if lnum:
                txt = re.sub(r'^\(\d+\)\s+', '', txt)  # the new sentence printed with the ledd's number
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
                ps = sentences(txt)
                nxt = [s for s in sl if s['orig'] is not None and k < s['orig'] < k + len(ps)]
                if (len(ps) > 1 and not op.get('pkt_to') and not op.get('pkt_adds') and len(nxt) == len(ps) - 1
                        and all(difflib.SequenceMatcher(None, a['s'], b).ratio() >= 0.6 for a, b in zip(nxt, ps[1:]))):
                    # "første punktum skal lyde:" with two sentences, the second a revision of the old second sentence
                    # (samvirkelova § 27, lov 21. juni 2013 nr. 75): the old sentences it restates are replaced too
                    for s in nxt:
                        s['dead'] = True
                    NOTES.append((num, 'the instruction "%s" gives %d sentences, the later ones revising the sentences '
                                       'after the one it names; those are replaced too, as in the consolidated text of Lovdata'
                                  % (op['src'], len(ps))))
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
        at = min(k, len(live))
        # a new sentence after the words that introduce the list goes after the list, when the ledd has words there
        # (or, in a ledd with a list and no words after it, a sentence added at the end)
        side = at > 0 and ((bool(after) and (live[at - 1]['after'] or not any(not x['after'] for x in live[at:])))
                           or (has_list and not after and at == len(live)))
        live.insert(at, {'orig': None, 's': txt, 'dead': False, 'after': side})
    head = (lnum.group(0) if lnum else '') + ' '.join(s['s'] for s in live if not s['after'])
    tail = ' '.join(s['s'] for s in live if s['after'])
    return head + L.CONT + tail if tail else head
