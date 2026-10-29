"""Build corpus.json for Norway from the cache only (no network).

Sources (all from Lovdata's public data, NLOD 2.0):
  - Norsk Lovtidend avd. I 2001-2026: the full text of each act as promulgated, and every amending
    document (endringslov, kunngjøring av grunnlovsvedtak), each with Lovdata's 'I kraft fra' field.
  - gjeldende-lover: today's consolidated text, its per-provision amendment notes ('ikr.' dates),
    and the end-to-end check of every replay.

    python -X utf8 parse.py            # writes corpus.json (atomically) and parse.log
"""
import hashlib, json, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lovdata as L
import replay as R

LOG = []
PENDING = []  # (act, law, provisions): passed, not yet in force
NOT_APPLIED = []  # (act, law, instruction, reason)


def log(*a):
    LOG.append(' '.join(str(x) for x in a))


MONTHS = {'januar': 1, 'februar': 2, 'mars': 3, 'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
          'september': 9, 'oktober': 10, 'november': 11, 'desember': 12}
MSHORT = {'jan': 1, 'feb': 2, 'mars': 3, 'april': 4, 'apr': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'aug': 8,
          'sep': 9, 'sept': 9, 'okt': 10, 'nov': 11, 'des': 12}
MNAME = {v: k for k, v in MONTHS.items()}


def nodate(iso):
    y, m, d = map(int, iso.split('-'))
    return '%d. %s %d' % (d, MNAME[m], y)


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- load the cache
def load():
    gj = L.read_tar(L.GJ, lambda n: n.startswith('nl/'))
    lt = {}
    for url in L.LT:
        for name, raw in L.read_tar(url).items():
            lt[name] = (url, raw)
    idx = {}
    for name, (url, raw) in lt.items():
        h = L.header(raw)
        lid = h.get('legacyID')
        if lid:
            idx[lid] = {'name': name, 'url': url, 'raw': raw, 'h': h}
    return gj, idx


def src_url(doc):
    return doc['url'] + '#' + doc['name']


def lovdata_page(lid):
    """FOR-2014-05-09-613 -> https://lovdata.no/LTI/forskrift/2014-05-09-613"""
    kind, rest = lid.split('-', 1)
    return 'https://lovdata.no/LTI/%s/%s' % ({'FOR': 'forskrift', 'LOV': 'lov'}[kind], rest)


def law_key(lid):
    return lid.lower()


# ---------------------------------------------------------------- Grunnloven full texts (613, 778)
def fulltext(raw):
    """A Lovtidend document holding whole chapters in both languages -> {'bm': state, 'nn': state}."""
    bl = R.blocks(raw)
    out = {'bm': {}, 'nn': {}}
    lang, cur, seen_e = None, None, 0
    for b in bl:
        kind = b[0]
        t = R._btext(b)
        if kind == 'title' and t.startswith('Kongeriket'):
            lang = 'bm' if lang is None else 'nn'
            cur = None
            continue
        if kind == 'title':
            lab = R.head_label(t)
            if lang is None or (lab.startswith('E.') and lang == 'bm' and any(k.startswith('kapittel-e') for k in out['bm']) and 'kapittel-f' in out['bm']):
                lang = 'bm' if lang is None else 'nn'
            out[lang][L.chap_key(lab)] = {'t': 'h', 'label': lab}
            cur = None
            continue
        if kind in ('d', 'head'):
            m = re.match(r'^§\s*(\d+(?:\s?[a-z])?)$', t if kind == 'd' else b[1])
            if m:
                num = R.norm_num(m.group(1))
                cur = L.para_key(num)
                out[lang][cur] = R.para(num, '', [])
                continue
            if cur and re.match(r'^\((Opphevet|Oppheva|Opphevd)', t):
                continue
            continue
        if kind == 'p' and cur:
            out[lang][cur]['ledd'].append(list(b[1]))
    for lg in out:
        for k in [k for k, v in out[lg].items() if v['t'] == 'p' and (not v['ledd'] or all(
                re.match(r'^\((Opphevet|Oppheva|Opphevd)\b', l[0]) for l in v['ledd']))]:
            del out[lg][k]  # repealed: only the "(Opphevet ...)" line was printed
    return out


def diff_keys(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def changes(prev, cur):
    """{key: unit or None} for every unit that differs."""
    return {k: cur.get(k) for k in diff_keys(prev, cur)}


# ---------------------------------------------------------------- Grunnloven
GRL = 'lov/1814-05-17'


def grunnloven(gj, idx, laws):
    docs = sorted([d for d in idx.values() if GRL in d['h'].get('changes', []) and d['h'].get('dateInForce', '') >= '2014-05-06'],
                  key=lambda d: (d['h']['dateInForce'], d['h']['legacyID']))
    log('Grunnloven: %d announcements from 2014-05-06' % len(docs))
    base = idx['FOR-2014-05-09-613']
    ft = fulltext(base['raw'])
    ef = fulltext(idx['FOR-2014-06-20-778']['raw'])
    st = {'bm': ft['bm'], 'nn': ft['nn']}
    vers = {'bm': [], 'nn': []}
    for lg in st:
        vers[lg].append({'from': base['h']['dateInForce'], 'source_url': src_url(base), 'sha256': sha(base['raw']),
                         'units': R.units_of(st[lg]),
                         'note': 'Text as revised in language by the grunnlovsvedtak of 6 May 2014, announced by res. 9 May 2014 no. 613 (Norsk Lovtidend avd. I 2014 hefte 6 s 903), as corrected by Lovdata on 2014-05-30.'})
    for d in docs:
        lid = d['h']['legacyID']
        day = d['h']['dateInForce']
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', day):
            raise SystemExit('Grunnloven: no single in-force day for ' + lid)
        key = law_key(lid)
        pub = d['h'].get('dateOfPublication', '')[:10]
        vm = re.search(r'vedtak (\d+)\. (\w+) (\d{4})', d['h']['title'])
        same = [x for x in docs if x['h']['dateInForce'] == day]
        label = 'Grunnlovsvedtak %s' % nodate(day) + (' (nr. %s)' % lid.rsplit('-', 1)[1] if len(same) > 1 else '')
        laws[key] = {'label': label, 'title': d['h']['title'], 'kind': 'law', 'enacted': day, 'published': pub,
                     'url': lovdata_page(lid), 'temporary_until': None, 'restores': None, 'note': None}
        if lid == 'FOR-2014-05-09-613':
            del laws[key]  # the base text: credited to the publisher as the oldest version available
            continue
        for lg in st:
            prev = R.units_of(st[lg])
            new = dict(st[lg])
            if lid == 'FOR-2014-05-14-628':
                ops = [o for o in R.doc_ops(d['raw']) if o['num'] == '49']
                R.apply_ops(new, ops, lg)
                for k in [k for k, v in new.items() if (v['t'] == 'p' and int(v['num'].split()[0]) >= 92) or k in ('kapittel-e', 'kapittel-f')]:
                    del new[k]
                new.update(ef[lg])
                new = dict(sorted(new.items(), key=lambda kv: _order(kv[0])))
            elif lid == 'FOR-2014-06-20-778':
                # an edited version of chapters E and F already used from 13 May 2014: words unchanged
                same = R.units_of(ef[lg])
                cur = R.units_of(new)
                diff = [k for k in same if cur.get(k) != same[k]]
                if diff:
                    raise SystemExit('778 differs from the 13 May text in ' + ', '.join(diff))
                vers[lg].append({'from': day, 'source_url': src_url(d), 'sha256': sha(d['raw']),
                                 'credits': {k: [key] for k in sorted(same)},
                                 'note': 'Stortinget adopted the edited (numbered) version of chapters E and F that the decision of 13 May 2014 called for; the words did not change.'})
                continue
            else:
                ops = R.doc_ops(d['raw'])
                R.apply_ops(new, ops, lg)
            st[lg] = new
            cur = R.units_of(new)
            ch = changes(prev, cur)
            if not ch:
                log('  %s %s %s: no change' % (lg, lid, day))
                continue
            log('  %s %s %s: %d units' % (lg, lid, day, len(ch)))
            v = {'from': day, 'source_url': src_url(d), 'sha256': sha(d['raw']), 'changes': ch,
                 'credits': {k: [key] for k in ch}}
            if vers[lg][-1]['from'] == day:
                v['same_day'] = True  # several decisions of one day, applied in the order of their announcement numbers
            vers[lg].append(v)
    acts = []
    for lg, fname, slug, title, short in (('bm', 'nl/nl-18140517-000.xml', 'grunnloven', 'Kongeriket Norges Grunnlov', 'Grl.'),
                                          ('nn', 'nl/nl-18140517-000-nn.xml', 'grunnlova', 'Kongeriket Noregs grunnlov', 'Grl. (nn)')):
        official = L.consolidated(gj[fname])
        final = R.units_of(st[lg])
        mism = diff_keys(final, official)
        log('Grunnloven %s: replay vs Lovdata consolidated (%s): %d mismatches' % (lg, fname, len(mism)))
        for k in mism:
            log('   MISMATCH %s\n     replay  : %r\n     official: %r' % (k, (final.get(k) or {}).get('text'), (official.get(k) or {}).get('text')))
        acts.append({'slug': slug, 'short': short, 'title': title, 'url': 'https://lovdata.no/dokument/NL/lov/1814-05-17' + ('/nn' if lg == 'nn' else ''),
                     'first_law': None, 'earlier_laws': [], 'versions': vers[lg], '_mismatch': mism, '_official': official, '_final': final})
    return acts


def _order(k):
    m = re.match(r'^(kapittel|paragraf)-(\w+)(?:-(\w))?$', k)
    return k


# ---------------------------------------------------------------- ordinary acts (personopplysningsloven)
def ikr_dates(note_list, lov_ref):
    """In-force days Lovdata's notes give for one amending law: 'lov 18 juni 2021 nr. 124 [lov/2021-06-18-124] (ikr. 1 jan 2022'."""
    out = set()
    for n in note_list:
        for m in re.finditer(re.escape('[' + lov_ref + ']') + r'\s*\((?:ikr\.|i kraft)\s*(\d+)\s+(\w+)\.?\s+(\d{4})', n):
            out.add('%04d-%02d-%02d' % (int(m.group(3)), MSHORT[m.group(2).lower()], int(m.group(1))))
    return out


def ordinary_act(gj, idx, laws, slug, short, ref, gj_name, lt_lid, amenders, target_re):
    """Act as promulgated (Lovtidend) then each amending law replayed; dates from Lovdata's ikr. notes."""
    base = idx[lt_lid]
    skipped = []
    st0 = units_struct(base['raw'], skipped)
    for k, v in st0.items():
        if v['t'] == 'p' and v['title'].startswith('Endringer i andre lover') and len(v['ledd']) > 1:
            # the amendments it made live on in the acts they amended; Lovdata keeps only the opening words
            log('  %s %s: kept the opening ledd only (%d ledd of amendments to other acts)' % (slug, k, len(v['ledd']) - 1))
            v['ledd'] = v['ledd'][:1]
    official_raw = gj[gj_name]
    oh = L.header(official_raw)
    notes = L.notes(official_raw)
    first_day = oh['dateInForce'][:10]
    laws[law_key(lt_lid)] = {'label': lov_label(lt_lid), 'title': base['h']['title'], 'kind': 'law',
                             'enacted': lt_lid[4:14], 'published': base['h'].get('dateOfPublication', '')[:10],
                             'url': lovdata_page(lt_lid), 'temporary_until': None, 'restores': None, 'note': None}
    if amenders is None:
        # every law Lovtidend records as changing the act, in promulgation order
        amenders = sorted([x['h']['legacyID'] for x in idx.values() if x['h'].get('legacyID', '').startswith('LOV-')
                           and any(c == ref or c.startswith(ref + '/') for c in x['h'].get('changes', []))],
                          key=lambda l: (l[4:14], int(l.rsplit('-', 1)[1])))
    noted = sorted({m for v in notes.values() for n in v for m in re.findall(r'\[(lov/[0-9-]+)\]', n)} - {ref})
    extra = [n for n in noted if 'LOV-' + n[4:] not in [re.sub(r'-0*(\d+)$', r'-\1', a) for a in amenders]]
    log('  %s: %d amending laws in Lovtidend; laws named in Lovdata notes but not among them: %s' % (slug, len(amenders), extra))
    for n in extra:
        y, mo, da, nr = n[4:].split('-')
        lid = 'LOV-%s-%s-%s-%s' % (y, mo, da, nr)
        if lid in idx:
            amenders.append(lid)
            log('  %s: added %s (named in Lovdata notes, not in Lovtidend\'s "Endrer" list)' % (slug, lid))
    amenders = sorted(set(amenders), key=lambda l: (l[4:14], int(l.rsplit('-', 1)[1])))
    vers = [{'from': first_day, 'source_url': src_url(base), 'sha256': sha(base['raw']), 'units': R.units_of(st0)}]
    st = st0
    events = []  # (day, order, lid, {key: unit or None})
    for order, lid in enumerate(amenders):
        d = idx[lid]
        ref_l = 'lov/' + re.sub(r'-0*(\d+)$', r'-\1', lid[4:])
        nw = len(R.WARN)
        ops = R.doc_ops(d['raw'], only=lambda o: bool(o.get('target') and re.search(target_re, o['target'])), single_lang='bm',
                        strict=False)
        for w in R.WARN[nw:]:
            NOT_APPLIED.append((slug, lid, w, 'not read'))
        prev = R.units_of(st)
        prev_state = dict(st)
        new = dict(st)
        try:
            R.apply_ops(new, ops, 'bm')
        except R.ReplayError as e:
            # apply what can be applied, one instruction at a time; each one left out is logged, and the
            # end-to-end comparison with today's text decides whether the act can be verified
            log('  %s %s: whole document failed (%s); applying instruction by instruction' % (slug, lid, e))
            new = dict(st)
            for op in ops:
                trial = dict(new)
                try:
                    R.apply_ops(trial, [op], 'bm')
                    new = trial
                except R.ReplayError as e2:
                    NOT_APPLIED.append((slug, lid, op['src'][:160], str(e2)[:160]))
                    log('    NOT APPLIED %s: %s' % (op['src'][:120], str(e2)[:120]))
        cur = R.units_of(new)
        ch = changes(prev, cur)
        laws[law_key(lid)] = {'label': lov_label(lid), 'title': d['h']['title'], 'kind': 'law', 'enacted': lid[4:14],
                              'published': d['h'].get('dateOfPublication', '')[:10], 'url': lovdata_page(lid),
                              'temporary_until': None, 'restores': None, 'note': None}
        st = new
        named = sorted(k for k, v in notes.items() if any('[' + ref_l + ']' in n for n in v))
        missed = [k for k in named if k not in ch]
        if missed:
            log('  %s %s: Lovdata notes name this law on %s, but the replay changed nothing there' % (slug, lid, missed))
        if not ch:
            log('  %s %s: no change to the act' % (slug, lid))
            continue
        pending = [k for k in ch if any(re.search(re.escape('[' + ref_l + ']') + r'\s*\(i kraft fra den tid Kongen bestemmer\)', n)
                                        for n in notes.get(k, []))]
        if pending:
            # passed but not yet in force: no in-force day exists, so the change is not in the history yet
            for k in pending:
                if k in prev_state:
                    st[k] = prev_state[k]
                else:
                    st.pop(k, None)
                del ch[k]
            PENDING.append((slug, lid, pending))
            log('  %s %s: not yet in force (Lovdata: "i kraft fra den tid Kongen bestemmer"), left out: %s' % (slug, lid, pending))
            if not ch:
                continue
        byday, undated = {}, []
        for k in ch:
            ds = ikr_dates(notes.get(k, []), ref_l)
            if len(ds) > 1:
                raise SystemExit('%s: %s has several in-force days for %s: %s' % (slug, k, lid, sorted(ds)))
            if ds:
                # an amendment of an act not yet in force takes effect with the act
                byday.setdefault(max(ds.pop(), first_day), {})[k] = ch[k]
            else:
                undated.append(k)
        if undated:
            # Lovdata's note gives no day when the change took effect on the law's own commencement day
            dif = re.findall(r'\d{4}-\d{2}-\d{2}', d['h'].get('dateInForce', ''))
            if lid[4:14] < first_day:
                day = first_day  # made before the act itself took effect: in force with it
            elif dif:
                day = max(dif[0], first_day)  # never before the act itself took effect
            elif len(byday) == 1:
                day = next(iter(byday))
            else:
                # the commencement resolution ("Ikraftsetting av lov ...") in Lovtidend, when it sets a single day
                named = lov_label(lid).lower()  # 'lov 5. mars 2021 nr. 6'
                res = [x for x in idx.values() if x['h'].get('legacyID', '').startswith('FOR-') and 'kraft' in x['h'].get('title', '').lower()
                       and (ref_l in x['h'].get('changes', []) or re.search(re.escape(named) + r'\b', x['h'].get('title', '').lower()))]
                rdays = sorted({dd for x in res for dd in re.findall(r'\d{4}-\d{2}-\d{2}', x['h'].get('dateInForce', ''))})
                if len(rdays) != 1:
                    raise SystemExit('%s: no in-force day for %s in %s (resolutions: %s)' % (slug, undated, lid, rdays))
                day = rdays[0]
                log('  %s %s: in-force day %s from %s' % (slug, lid, day, [x['h']['legacyID'] for x in res]))
            log('  %s %s: %s dated %s (no Lovdata note on the provision today)' % (slug, lid, undated, day))
            for k in undated:
                byday.setdefault(day, {})[k] = ch[k]
        for day, chg in byday.items():
            events.append((day, order, lid, d, chg))
    seen = {}
    for day, order, lid, d, chg in sorted(events, key=lambda e: (e[0], e[1])):
        for k in chg:
            if k in seen and seen[k] > order:
                raise SystemExit('%s: %s changed by %s after a later law took effect on it' % (slug, k, lid))
            seen[k] = order
        v = {'from': day, 'source_url': src_url(d), 'sha256': sha(d['raw']), 'changes': dict(sorted(chg.items())),
             'credits': {k: [law_key(lid)] for k in sorted(chg)}}
        if vers[-1]['from'] == day:
            v['same_day'] = True
        elif vers[-1]['from'] > day:
            raise SystemExit('%s: %s in force %s before the version of %s' % (slug, lid, day, vers[-1]['from']))
        vers.append(v)
        log('  %s %s in force %s: %d units' % (slug, lid, day, len(chg)))
    official = L.consolidated(official_raw, [])
    final = R.units_of(st)
    asof = gj_asof()
    final = state_on(vers, asof)
    if any(v['from'] > asof for v in vers):
        log('  %s: compared as of %s (the consolidated data set\'s date); later versions: %s' % (
            slug, asof, sorted({v['from'] for v in vers if v['from'] > asof})))
    mism = diff_keys(final, official)
    log('%s: replay vs Lovdata consolidated: %d mismatches; left out: %s' % (slug, len(mism), skipped))
    for k in mism:
        log('   MISMATCH %s\n     replay  : %r\n     official: %r' % (k, (final.get(k) or {}).get('text'), (official.get(k) or {}).get('text')))
    return {'slug': slug, 'short': short, 'title': base['h']['title'], 'url': 'https://lovdata.no/dokument/NL/' + ref,
            'first_law': law_key(lt_lid), 'earlier_laws': [], 'versions': vers, '_mismatch': mism, '_official': official, '_final': final,
            '_skipped': skipped}


def state_on(vers, day):
    """Units in force on `day`, from a list of versions (units / changes)."""
    cur = {}
    for v in vers:
        if v['from'] > day:
            break
        if 'units' in v:
            cur = dict(v['units'])
        for k, u in v.get('changes', {}).items():
            if u is None:
                cur.pop(k, None)
            else:
                cur[k] = u
    return cur


def gj_asof():
    """The day of the consolidated data set: its lastModified stamp in the cached data set list."""
    lst = json.loads(open(L.cpath(L.API + 'list'), encoding='utf-8').read())
    return [x for x in lst if x['filename'] == 'gjeldende-lover.tar.bz2'][0]['lastModified'][:10]


def lov_label(lid):
    y, m, d, n = lid[4:].split('-')
    return 'Lov %d. %s %s nr. %d' % (int(d), MNAME[int(m)], y, int(n))


def units_struct(raw, skipped):
    """Structured state (for replay) of an act's full text in Lovdata's article markup."""
    st = {}
    for kind, key, a, b, c, ctx in L.walk_act(raw, skipped):
        if kind == 'h':
            st[key] = {'t': 'h', 'label': a, 'parent': ctx}
        else:
            st[key] = R.para(a, b, c)
            st[key]['chap'] = ctx
    return st


# ---------------------------------------------------------------- main
def main():
    gj, idx = load()
    laws = {}
    acts = grunnloven(gj, idx, laws)
    acts.append(ordinary_act(gj, idx, laws, 'personopplysningsloven', 'popplyl.', 'lov/2018-06-15-38', 'nl/nl-20180615-038.xml',
                             'LOV-2018-06-15-38', None, r'lov 15\. juni 2018 nr\. 38'))
    acts.append(ordinary_act(gj, idx, laws, 'arveloven', 'arvel.', 'lov/2019-06-14-21', 'nl/nl-20190614-021.xml',
                             'LOV-2019-06-14-21', None, r'lov 14\. juni 2019 nr\. 21'))
    # straffeloven (work in progress): replayed for diagnostics; written as corpus.d/50-straffeloven.json only once its
    # replay matches today's official text in every unit. Until then nothing of it is published, not even to preview.
    slaws, strl = {}, None
    try:
        strl = ordinary_act(gj, idx, slaws, 'straffeloven', 'strl.', 'lov/2005-05-20-28', 'nl/nl-20050520-028.xml',
                            'LOV-2005-05-20-28', None, r'(?i)lov 20\. mai 2005 nr\. 28|^I straffeloven 2005\b')
    except (SystemExit, R.ReplayError) as e:
        log('straffeloven: replay stopped (%s); not written' % e)
    for w in R.WARN:
        log('  WARNING ' + w)
    report = {}
    for a in acts + ([strl] if strl else []):
        report[a['slug']] = {'versions': len(a['versions']), 'mismatches': len(a['_mismatch'])}
    open(os.path.join(HERE, 'parse.log'), 'w', encoding='utf-8', newline='\n').write('\n'.join(LOG) + '\n')
    json.dump(report, sys.stdout, ensure_ascii=False, indent=1)
    if any(a['_mismatch'] for a in acts):
        raise SystemExit('a verified act no longer matches the official text: see parse.log')
    for a in acts:
        a.pop('_official'); a.pop('_final'); a.pop('_skipped', None); a.pop('_mismatch')
    write_corpus(acts, laws)
    if strl and not strl['_mismatch']:
        strl.pop('_official'); strl.pop('_final'); strl.pop('_skipped', None); strl.pop('_mismatch')
        write_part('50-straffeloven', strl, slaws, [])


def write_part(name, act, laws, mism):
    d = os.path.join(HERE, 'corpus.d')
    os.makedirs(d, exist_ok=True)
    dec = ['straffeloven: replayed from the act as promulgated (LOV-2005-05-20-28) through every amending law in Lovtidend; '
           'replay against Lovdata\'s consolidated text: %d of %d units differ%s.' % (
               len(mism), len(act['versions'][-1].get('units', {})) or 0, (': ' + ', '.join(mism)) if mism else '')]
    dec += ['straffeloven: instruction not applied: %s (%s): %s' % (lid, why, src) for s, lid, src, why in NOT_APPLIED if s == act['slug']]
    part = {'acts': [act], 'laws': dict(sorted(laws.items())), 'decisions': dec}
    p = os.path.join(d, name + '.json')
    with open(p + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(part, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(p + '.tmp', p)


def write_corpus(acts, laws):
    corpus = {'country': COUNTRY, 'sources': sources(), 'laws': dict(sorted(laws.items())), 'acts': acts,
              'applies': [], 'decisions': DECISIONS, 'ai_use': AI_USE}
    p = os.path.join(HERE, 'corpus.json')
    with open(p + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(p + '.tmp', p)


NLOD = ('Contains data under the Norwegian licence for Open Government data (NLOD 2.0) distributed by Lovdata '
        '(Inneholder data under norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Lovdata). '
        'https://data.norge.no/nlod/no/2.0')

COUNTRY = {
    'code': 'NO', 'name': 'Norway', 'slug': 'norway', 'lang': 'nb',
    'tz': 'Europe/Oslo',
    'future_branch': 'fremtidig',
    'publisher': {'name': 'Lovdata (Norsk Lovtidend)', 'email': 'lovdata@lovdata.invalid'},
    'default_in_force_rule': {
        'text': ('Norway has no single default commencement rule in this record: each in-force day is the one Lovdata '
                 'records for the official Norsk Lovtidend document ("I kraft fra"; for a decision amending the Constitution, '
                 'the day of Stortinget\'s decision), and where a law leaves commencement to the King ("Kongen bestemmer"), '
                 'the day Lovdata\'s amendment note gives for that provision ("ikr. ... iflg. res. ...").'),
        'source': 'https://api.lovdata.no/xmldocs'},
    'licence_note': NLOD,
}


def sources():
    reqs = [json.loads(l) for l in open(os.path.join(L.CACHE, 'requests.jsonl'), encoding='utf-8') if l.strip()]
    ok = [r for r in reqs if r['status'] == '200']
    day = max(r['at'][:10] for r in ok)
    return [
        {'name': 'Norsk Lovtidend avd. I (Lovdata public data)', 'url': 'https://api.lovdata.no/publicData',
         'retrieved': day, 'requests': sum(1 for r in reqs if 'lovtidend' in r['url']),
         'licence': 'NLOD 2.0',
         'notes': ('lovtidend-avd1-2001-2025.tar.bz2 and lovtidend-avd1-2026.tar.bz2: every law, constitutional amendment '
                   'and central regulation as officially announced since 1 January 2001. Lovdata: "Norsk Lovtidend er den eneste '
                   'offisielle og autorative kilden til norske lover og regler." Every version in this record is built from these documents.')},
        {'name': 'Gjeldende lover (Lovdata public data)', 'url': 'https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2',
         'retrieved': day, 'requests': sum(1 for r in reqs if 'gjeldende-lover' in r['url']),
         'licence': 'NLOD 2.0',
         'notes': ('Lovdata\'s consolidated current text (not official; Norway has no official consolidations). Used to check '
                   'every replay end to end and for the in-force days in its amendment notes; no text is taken from it.')},
        {'name': 'Lovdata API description and data set list', 'url': 'https://api.lovdata.no/swagger/api.json',
         'retrieved': day, 'requests': sum(1 for r in reqs if 'swagger' in r['url'] or r['url'].endswith('/publicData')
                                           or r['url'].endswith('/list')),
         'licence': 'NLOD 2.0', 'notes': 'States "Public data released under the NLOD 2.0 license"; the list gives each archive\'s lastModified stamp.'},
    ]


DECISIONS = [
    'Text comes only from Norsk Lovtidend avd. I, the official announcement of Norwegian law; Lovdata\'s consolidated text (unofficial) is used only to check the replay and for in-force days of provisions whose law left commencement to the King.',
    'Grunnloven and Grunnlova are two acts: since 6 May 2014 the Constitution has official bokmål and nynorsk texts of equal standing, and every amendment is announced in both.',
    'Grunnloven starts on 2014-05-06 with the full text of the language revision announced by res. 9 May 2014 no. 613, as corrected by Lovdata on 2014-05-30 (bokmål §§ 2, 6, 53, 63, 92, 112). Earlier wording is in the old language and the full text before 2014 is not in the open archive, so this is the oldest version available (first_law null).',
    'The decision of 13 May 2014 (res. 14 May 2014 no. 628) moved provisions to a new chapter F "with a new paragraph number" it did not give. The 13 May version therefore uses the numbering and text of chapters E and F in the edited version Stortinget adopted on 27 May 2014 (res. 20 June 2014 no. 778), and the 27 May commit changes no words.',
    'Amendment instructions are applied by code (replay.py): ledd and punktum being replaced or repealed count the text as it read before; "nytt" ledd and punktum name the new position; list letters are addressed by letter. An instruction the code cannot read stops the build.',
    'Grunnloven: amendments of 2014-2024 are dated by Stortinget\'s decision, the "I kraft fra" day Lovdata gives each announcement.',
    'Repealed paragraphs are removed files; the editorial "(Opphevet ved ...)" lines Lovdata prints are not law text and are left out.',
    'Chapter headings are units of their own (kapittel-*.md).',
    'List items are written "a) text", in one form for both sources (Lovtidend prints "a)", the consolidated text "a.").',
    'Number ranges are written with a hyphen (§§ 77-79): Lovdata prints an en dash in some texts and a hyphen in others.',
    'personopplysningsloven § 34 (Endringer i andre lover) keeps only its opening sentence, as in Lovdata\'s consolidated text: the amendments it made live on in the acts they amended.',
    'personopplysningsloven: the annexed Norwegian text of the GDPR (EEA version), which § 1 makes law, is not included; only the act\'s own chapters 1-9 are.',
    'personopplysningsloven: both amending laws left commencement to the King; each change is dated by the in-force day in Lovdata\'s note for the provision (2018-12-20 for § 12 a, 2022-01-01 for § 3), which matches the commencement resolutions FOR-2018-12-20-2093 and FOR-2021-06-18-1967.',
    'Ordinary acts: the amending laws are every law Lovtidend\'s metadata ("Endrer") lists as changing the act, replayed in promulgation order; parse.log also lists any law Lovdata\'s notes name that is not among them (none).',
    'A change Lovdata\'s note gives no in-force day for took effect with the amending law itself: it is dated by the first day in that law\'s "I kraft fra" field, and never before the act itself took effect (arveloven: amendments of 18 December 2020 to the act that took effect on 1 January 2021 are same-day versions on that day).',
    'A change Lovdata marks "Endres ved lov ... (i kraft fra den tid Kongen bestemmer)" has no in-force day yet, so it is not in the history: arveloven § 103 and § 178 (lov 19. juni 2026 nr. 48).',
    'Word substitutions ("I følgende bestemmelser skal «fylkesmannen» endres til «statsforvalteren»") are applied to the paragraphs and ledd they name, in lower and capitalised form; inflected forms that contain the word (fylkesmannens) change with it.',
    'Lovdata\'s editorial mark ": – – –" after "gjøres følgende endringer i andre lover" is not compared.',
    'sha256 of a version is the sha256 of the single Lovtidend XML document (the tar member named after # in source_url) it was parsed from.',
]

AI_USE = [
    'Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py, lovdata.py, replay.py and parse.py and read sample documents to design them. No model wrote, edited or summarised legal text, and no model runs in parse.py or at git-build time.',
]

if __name__ == '__main__':
    try:
        main()
    finally:
        open(os.path.join(HERE, 'parse.log'), 'w', encoding='utf-8', newline='\n').write('\n'.join(LOG) + '\n')
