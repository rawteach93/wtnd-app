#!/usr/bin/env python3
"""
Extract Where There Is No Doctor + Where There Is No Dentist into a
structured dataset for the app.

Two layers:
  1. pages[]  - every page's full text, lossless. Nothing from either book
                is dropped, whatever the structured parse makes of it.
  2. topics[] - headings with Signs / Treatment / Prevention split out,
                each carrying its page so any screen can be checked.
Plus glossary, index, and the green-pages medicines.

Signals the books actually give us:
  * Doctor book marks signs with a bullet and treatment with a diamond.
    That glyph survives the PDF's column reflow; heading order does not.
  * Dentist book uses SIGNS: / TREATMENT: headings and one bullet glyph.
  * Body pages print the page number after the footer, green pages before it.
"""
import re, json, unicodedata, sys
from collections import OrderedDict

SRC = {
    'doctor':  ('/mnt/user-data/uploads/16bd7dcc-14.DavidWerner-WhereThereIsNoDoctor.pdf.txt',
                r'(?:Green Pages[ \t]*)?Where There Is No Doctor \d{4}(?:[ \t]*Green Pages)?'),
    'dentist': ('/mnt/user-data/uploads/c3a5ae03-Where_there_is_no_Dentist_-_Murray_Dickson.pdf.txt',
                r'Where There Is No Dentist \d{4}'),
}

BOOK_META = {
    'doctor':  {'title': 'Where There Is No Doctor', 'short': 'Doctor',
                'author': 'David Werner, with Carol Thuman and Jane Maxwell',
                'edition': 'Revised edition 1992, 2010 printing'},
    'dentist': {'title': 'Where There Is No Dentist', 'short': 'Dentist',
                'author': 'Murray Dickson', 'edition': 'Updated edition 2012'},
}

SIGN_GLYPH  = '•●·'
TREAT_GLYPH = '♦♪♥♣'
ALL_GLYPH   = SIGN_GLYPH + TREAT_GLYPH + '*-–—'


def clean(s):
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = unicodedata.normalize('NFKC', s)
    for a, b in (('’', "'"), ('‘', "'"), ('“', '"'), ('”', '"'),
                 ('ﬁ', 'fi'), ('ﬂ', 'fl')):
        s = s.replace(a, b)
    return re.sub(r'[ \t]+', ' ', s)


# ------------------------------------------------------------------ pages
def split_pages(text, marker, book):
    """Body pages print the number after the footer; green pages before it."""
    chunks = re.split(marker, text)
    pages, carried = [], None
    for ch in chunks:
        lines = [l.rstrip() for l in ch.split('\n')]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        lead = None
        if lines and re.fullmatch(r'w?\d{1,3}', lines[0].strip()):
            lead = lines[0].strip()
            lines = lines[1:]
        trail = None
        if lines and re.fullmatch(r'w?\d{1,3}', lines[-1].strip()):
            trail = lines[-1].strip()
            lines = lines[:-1]

        body = '\n'.join(l for l in lines if l.strip()).strip()
        page = lead or carried or trail
        carried = trail if lead else None
        if body:
            pages.append({'book': book, 'page': page, 'text': clean(body)})
    return pages


# ---------------------------------------------------- heading detection
FURNITURE = re.compile(
    r'^(THANKS|CONTENTS|INDEX|VOCABULARY|INTRODUCTION|CHAPTER|PART|APPENDI|'
    r'TANZANIA|INDIA|MALAWI|CAMBODIA|LEBANON|PAKISTAN|UNITED|SPANISH|ARABIC|'
    r'HINDI|CHICHEWA|KHMER|PORTUGUESE|URDU|HAITIAN|SWAHILI|GERMAN|FRENCH|'
    r'WHERE THERE IS NO|ISBN|COPYRIGHT|NOTE|IMPORTANT|CAUTION|WARNING|'
    r'SIGNS|TREATMENT|PREVENTION|DOSAGE|PAGE|NAME|PRICE|PRINTED|PUBLISHED)\b', re.I)


def is_heading(line):
    s = line.strip()
    if not (3 < len(s) <= 62):
        return False
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9 \-',\(\)/\.&]+", s):
        return False
    if len([c for c in s if c.isalpha()]) < 3:
        return False
    if FURNITURE.match(s) or re.fullmatch(r'[\d \-\.,]+', s):
        return False
    return True


BLOCK = re.compile(
    r'^(SIGNS?|TREATMENT|PREVENTION|Signs?|Treatment|Prevention|'
    r'Signs? (?:of|and) [a-z ]{3,30}|Analysis and treatment|What to do|'
    r'How to treat|To prevent[a-z :]{0,30}|Prevention and treatment)\s*:?\s*$')


def tidy(item):
    item = re.sub(r'^[' + re.escape(ALL_GLYPH) + r']\s*', '', item)
    item = re.sub(r'^\d{1,2}[\.\)]\s+', '', item)
    return item.strip()


def join_wrapped(lines):
    """PDF text wraps mid-sentence; rejoin a bullet with its continuation."""
    out = []
    for l in lines:
        if out and l and (l[0].islower() or l[0] in '(,') \
           and not out[-1].endswith(('.', ':', '!', '?')) and len(out[-1]) < 240:
            out[-1] += ' ' + l
        else:
            out.append(l)
    seen, keep = set(), []
    for o in out:
        o = o.strip()
        if len(o) < 4 or re.fullmatch(r'[\d \-\.,p]+', o) or o.lower() in seen:
            continue
        seen.add(o.lower())
        keep.append(o)
    return keep


def parse_blocks(body, book):
    out = {'signs': [], 'treat': [], 'prevent': [], 'intro': []}
    cur, open_block = 'intro', None
    for raw in body.split('\n'):
        line = raw.strip()
        if not line:
            continue
        m = BLOCK.match(line)
        if m:
            h = m.group(1).lower()
            cur = 'signs' if h.startswith('sign') else \
                  'prevent' if ('prevent' in h and 'treat' not in h) else 'treat'
            open_block = None
            continue
        if book == 'doctor':
            # the glyph beats heading order, which the column reflow scrambles
            if line[0] in SIGN_GLYPH:
                out['signs'].append(tidy(line)); open_block = 'signs'; continue
            if line[0] in TREAT_GLYPH:
                out['treat'].append(tidy(line)); open_block = 'treat'; continue
            # a bulleted item wraps onto following unmarked lines; those
            # belong to the bullet, not to the surrounding prose
            if open_block and out[open_block]:
                prev = out[open_block][-1]
                wraps = (line[0].islower() or line[0] in '(,'
                         or not prev.endswith(('.', ':', '!', '?')))
                if wraps and len(prev) < 260:
                    out[open_block][-1] = prev + ' ' + tidy(line)
                    continue
                open_block = None
        out[cur].append(tidy(line))
    return out


def build_topics(pages, book):
    """Build over the whole book's line stream, not page by page: a heading
    printed at the foot of a page carries its body onto the next one."""
    stream = []                       # (line, page)
    for pg in pages:
        if pg['book'] != book:
            continue
        for l in pg['text'].split('\n'):
            stream.append((l, pg['page']))

    def titlecase_heading(i):
        """Some sections (Measles, Mumps, Chickenpox) are set in Title Case,
        not caps. Accept one when a Signs/Treatment block follows close by."""
        s = stream[i][0].strip()
        if not (3 < len(s) <= 46) or s.endswith(('.', ',', ':', ';')):
            return False
        if not re.fullmatch(r"[A-Z][A-Za-z'\-]*(?: (?:[A-Z][A-Za-z'\-]*|of|the|and|or|in))*"
                            r"(?: \([A-Za-z '\-]{2,24}\))?", s):
            return False
        if FURNITURE.match(s) or len(s.split()) > 5:
            return False
        for j in range(i + 1, min(i + 14, len(stream))):
            nxt = stream[j][0].strip()
            if BLOCK.match(nxt) or (nxt and nxt[0] in SIGN_GLYPH + TREAT_GLYPH):
                return True
        return False

    heads = [i for i, (l, _) in enumerate(stream)
             if is_heading(l) or titlecase_heading(i)]
    topics = []
    for n, i in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(stream)
        end = min(end, i + 130)       # a subject does not run for pages
        body = '\n'.join(l for l, _ in stream[i + 1:end]).strip()
        if len(body) < 40:
            continue
        b = parse_blocks(body, book)
        topics.append({
            'book': book, 'page': stream[i][1],
            'title': stream[i][0].strip().title().replace("'S", "'s"),
            'intro': ' '.join(join_wrapped(b['intro']))[:1000],
            'signs': join_wrapped(b['signs'])[:16],
            'treat': join_wrapped(b['treat'])[:16],
            'prevent': join_wrapped(b['prevent'])[:12],
        })
    return topics


# --------------------------------------------------------------- glossary
GLOSS_RE = re.compile(r"^\*?([A-Z][A-Za-z'\-, ]{2,44}?)\s+((?:[A-Z(]|See\b).{18,})$")


def build_glossary(text, book):
    m = re.search(r'\n *(?:Vocabulary|VOCABULARY) *\n', text)
    if not m:
        return []
    chunk = text[m.end(): m.end() + 140000]
    stop = re.search(r'\n *(?:Index|INDEX|ADDRESSES FOR TEACHING|Other Books)[^\n]{0,24}\n', chunk)
    if stop:
        chunk = chunk[:stop.start()]
    entries, cur = [], None
    for raw in chunk.split('\n'):
        line = raw.strip()
        if not line or re.fullmatch(r'(?:[A-Z] ?)+', line) or 'Where There Is No' in line:
            continue
        g = GLOSS_RE.match(line)
        if g and len(g.group(1).split()) <= 4:
            if cur:
                entries.append(cur)
            cur = {'book': book, 'term': g.group(1).strip(' ,'), 'def': g.group(2).strip()}
        elif cur:
            cur['def'] += ' ' + line
    if cur:
        entries.append(cur)
    out, seen = [], set()
    for e in entries:
        e['def'] = re.sub(r'\s+', ' ', e['def']).strip()[:430]
        k = e['term'].lower()
        if len(e['def']) > 18 and k not in seen:
            seen.add(k)
            out.append(e)
    return out


# ------------------------------------------------------------------ index
IDX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9'\-\(\),\. ]{1,46}?),\s*([\d–\-,\s]{1,40})$")


def build_index(text, book, label):
    m = re.search(r'\n *' + label + r' *\n', text)
    if not m:
        return []
    out, seen = [], set()
    for raw in text[m.end():].split('\n'):
        g = IDX_RE.match(raw.strip())
        if not g:
            continue
        term = g.group(1).strip()
        pages = [p for p in re.split(r'[,\s]+', g.group(2)) if
                 re.fullmatch(r'\d{1,3}(?:[–\-]\d{1,3})?', p)]
        if len(term) < 3 or term.lower() in seen or not pages:
            continue
        seen.add(term.lower())
        out.append({'book': book, 'term': term, 'pages': pages[:6]})
    return out


# -------------------------------------------------------------- medicines
DOSE_BAND = re.compile(
    r'^(adults?[^:]{0,44}|children[^:]{0,44}|babies[^:]{0,44}|persons[^:]{0,38}|'
    r'pregnant[^:]{0,38}|newborns?[^:]{0,34}|older[^:]{0,34}|infants?[^:]{0,34})'
    r'\s*:\s*(.+)$', re.I)

NAME_RE = re.compile(
    r"^([A-Z][A-Za-z'\-]{2,}(?:[ \-](?:[A-Z]{1,3}|[a-z]{2,14}))*)"
    r"\s*(?:\(([^)]{2,46})\))?\s*(?:[—–-]+\s*(?:for |to )?(.{3,80}))?$")

GROUP_RE = re.compile(r"^(FOR [A-Z][A-Z ,'\-/]{3,56})$")

# a green-page entry opens with its name, then one of these labels
ANCHOR = ('Name:', 'Price:', 'Often comes in', 'Often comes as',
          'Comes as', 'Comes in')


def looks_like_name(cand):
    """A green-page entry name: a few words, no sentence punctuation."""
    if not cand or len(cand) > 86 or cand.endswith(('.', ':', ';', ',')):
        return None
    nm = NAME_RE.match(cand)
    if not nm or len(nm.group(1).split()) > 5 or re.search(r'\d', nm.group(1)):
        return None
    return nm


def build_medicines(pages):
    """Anchored on the blank 'Name:' line every green-page entry carries.
    Walks backward for the name, because long names wrap across two lines."""
    entries, cur, group = [], None, ''

    def close(c):
        if not c:
            return
        prose = []
        for ln in c.pop('_body'):
            ln = ln.strip()
            if not ln or ln.startswith(('Name:', 'Price:', 'price:')):
                continue
            d = DOSE_BAND.match(ln)
            if d:
                c['doses'].append({'band': d.group(1).strip(' :'), 'v': d.group(2).strip()[:120]})
            elif re.match(r'^(CAUTION|WARNING|CAU TION|WARNIN G|IMPORTANT)', ln, re.I):
                c['cautions'].append(re.sub(r'^[A-Z ]+ ?:?\s*', '', ln)[:320])
            elif ln.lower().startswith(('often comes', 'also comes', 'comes as', 'comes in')):
                c['comes'] = (c['comes'] + ' ' + (ln.split(':', 1)[-1] if ':' in ln else ln)).strip()
            else:
                prose.append(ln)
        c['comes'] = c['comes'][:220]
        c['text'] = re.sub(r'\s+', ' ', ' '.join(join_wrapped(prose)))[:1600]
        if c['doses'] or len(c['text']) > 40:
            entries.append(c)

    for pg in pages:
        if pg['book'] != 'doctor':
            continue
        lines = pg['text'].split('\n')
        for i, raw in enumerate(lines):
            line = raw.strip()
            g = GROUP_RE.match(line)
            if g:
                group = g.group(1).title()
                continue
            if line.startswith(ANCHOR) and i > 0:
                cand = lines[i - 1].strip()
                nm = looks_like_name(cand)
                if not nm and i > 1:
                    joined = (lines[i - 2].strip() + ' ' + cand).strip()
                    nm = looks_like_name(joined)
                    if nm:
                        cand = joined
                if nm and not (cur and cur['name'] == nm.group(1).strip()):
                    close(cur)
                    cur = {'book': 'doctor', 'page': pg['page'], 'group': group,
                           'name': nm.group(1).strip(), 'aka': (nm.group(2) or '').strip(),
                           'use': (nm.group(3) or '').strip(' .'),
                           'comes': '', 'cautions': [], 'doses': [], '_body': []}
                    continue
            if cur:
                cur['_body'].append(line)
    close(cur)

    best = OrderedDict()
    for m in entries:
        k = m['name'].lower()
        score = (len(m['doses']), len(m['text']))
        if k not in best or score > (len(best[k]['doses']), len(best[k]['text'])):
            best[k] = m
    return list(best.values())


# -------------------------------------------------------------------- run
def main():
    data = {'books': BOOK_META, 'pages': [], 'topics': [],
            'glossary': [], 'index': [], 'medicines': []}
    raw = {}
    for book, (path, marker) in SRC.items():
        text = clean(open(path, encoding='utf-8', errors='replace').read())
        raw[book] = text
        pages = split_pages(text, marker, book)
        data['pages'] += pages
        data['topics'] += build_topics(pages, book)
        data['glossary'] += build_glossary(text, book)
        missing = sum(1 for p in pages if not p['page'])
        print(f'{book}: {len(pages)} pages ({missing} without a number)', file=sys.stderr)

    data['index'] = (build_index(raw['doctor'], 'doctor', 'Index')
                     + build_index(raw['dentist'], 'dentist', 'INDEX'))
    data['medicines'] = build_medicines(data['pages'])

    json.dump(data, open('build/dataset.raw.json', 'w'), ensure_ascii=False)
    print(json.dumps({k: len(v) for k, v in data.items() if isinstance(v, list)}, indent=1))


main()

# --------------------------------------- the book's own medicine index
MEDIDX = re.compile(r"^([A-Z][A-Za-z0-9'’\-\(\), ]{2,60}?)"
                    r"(?:[—–-]\s*(?:for |to )?([^.]{3,60}?))?\s*\.{3,}\s*(\d{1,3})\s*$")

def build_med_index(text):
    m = re.search(r'\n *List of Medicines in the Green Pages *\n', text)
    if not m:
        return []
    chunk = text[m.end(): m.end() + 60000]
    stop = re.search(r'\n *Information on Medicines *\n', chunk)
    if stop:
        chunk = chunk[:stop.start()]
    out, seen = [], set()
    for raw in chunk.split('\n'):
        g = MEDIDX.match(raw.strip())
        if not g:
            continue
        name = re.sub(r'\s+', ' ', g.group(1)).strip(' ,')
        if len(name) < 4 or name.lower() in seen or name.startswith('For '):
            continue
        seen.add(name.lower())
        out.append({'name': name, 'use': (g.group(2) or '').strip(),
                    'page': g.group(3)})
    return out

import io, contextlib
_d = json.load(open('build/dataset.raw.json'))
_txt = clean(open(SRC['doctor'][0], encoding='utf-8', errors='replace').read())
_d['med_index'] = build_med_index(_txt)
json.dump(_d, open('build/dataset.raw.json', 'w'), ensure_ascii=False)
print('med_index entries:', len(_d['med_index']))
print('sample:', [m['name'] for m in _d['med_index'][:14]])
