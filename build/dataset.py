#!/usr/bin/env python3
"""
Turn the raw extraction into the dataset the app ships.

  - merges the parsed green-page medicines with the book's own medicine
    index, so every medicine is reachable even where the dosage table
    did not parse
  - builds the symptom index by matching a curated symptom vocabulary
    against each topic's own Signs list, weighting by the book's own
    hedge words (sometimes / may / often)
  - carries the twenty danger signs
  - keeps every page's full text, so nothing in either book is unreachable
"""
import re, json, unicodedata
from collections import OrderedDict

raw = json.load(open('build/dataset.raw.json'))

# ------------------------------------------------- symptom vocabulary
# The one part the books cannot supply: how people actually say things.
SYMPTOMS = {
 'fever':         ('Fever',               ['fever','feverish','temperature','hot body','homa','high temperature']),
 'high fever':    ('High fever',           ['high fever','very high fever','fever 39','fever 40','homa kali']),
 'chills':        ('Chills or shivering',  ['chills','shivering','shaking with cold','rigors']),
 'sweating':      ('Night sweats',         ['night sweat','sweats at night','sweating at night']),
 'cough':         ('Cough',                ['cough','coughing','kikohozi','kukohoa']),
 'bloody cough':  ('Coughing blood',       ['coughing up blood','blood in the mucus','bloody mucus','spitting blood']),
 'fast breathing':('Fast breathing',       ['rapid breathing','fast breathing','shallow breathing','breathing fast','short of breath','difficulty breathing','kuhema haraka']),
 'wheezing':      ('Wheezing',             ['wheezing','whistling in the chest']),
 'chest pain':    ('Chest pain',           ['chest pain','pain in the chest','kifua']),
 'headache':      ('Headache',             ['headache','head pain','kuumwa kichwa','migraine']),
 'stiff neck':    ('Stiff neck',           ['stiff neck','neck is stiff','arched back','shingo ngumu']),
 'convulsions':   ('Fits or convulsions',  ['convulsion','seizure','fits','degedege']),
 'unconscious':   ('Not waking',           ['unconscious','cannot be wakened','loss of consciousness','coma']),
 'vomiting':      ('Vomiting',             ['vomiting','vomits','throwing up','kutapika','nausea']),
 'diarrhoea':     ('Diarrhoea',            ['diarrhea','diarrhoea','loose stool','running stomach','kuhara','kuharisha']),
 'watery stools': ('Watery stools',        ['watery diarrhea','watery stool','rice water','watery']),
 'blood in stool':('Blood in the stool',   ['blood in the stool','bloody stool','dysentery','black stool','tarry stool']),
 'belly pain':    ('Belly pain',           ['belly pain','stomach pain','pain in the belly','cramps','maumivu ya tumbo']),
 'no appetite':   ('No appetite',          ['loses appetite','no appetite','does not want to eat','refusing food','hataki kula']),
 'weight loss':   ('Losing weight',        ['weight loss','losing weight','loses weight','getting thin']),
 'weakness':      ('Weakness',             ['very weak','weakness','no energy','tired','kuchoka','feels weak']),
 'thirst':        ('Thirst',               ['thirst','thirsty','dry mouth','kiu']),
 'sunken eyes':   ('Sunken eyes',          ['sunken eyes','tearless','no tears','sunken, tearless']),
 'no urine':      ('Little or no urine',   ['little or no urine','cannot urinate','not passing urine','no urine']),
 'dark urine':    ('Dark urine',           ['dark urine','urine is dark','orange urine','brown urine']),
 'blood in urine':('Blood in the urine',   ['blood in the urine','bloody urine']),
 'yellow eyes':   ('Yellow eyes',           ['jaundice','yellow eyes','eyes turn yellow','turn yellow','yellow skin','macho ya njano']),
 'pale':          ('Paleness',             ['pale','paleness','anemia','anaemia']),
 'rash':          ('Rash',                 ['rash','spots on the skin','red patches']),
 'itching':       ('Itching',              ['itching','itchy','itches']),
 'sores':         ('Sores',                ['sore','sores','ulcer on the skin','open sore']),
 'swelling':      ('Swelling',             ['swelling','swollen','puffiness','kuvimba']),
 'lump':          ('A lump',               ['lump','growth','a mass','tumor','tumour']),
 'joint pain':    ('Joint or bone pain',   ['joint pain','pain in the joints','bone pain','aching bones','arthritis']),
 'back pain':     ('Back pain',            ['back pain','pain in the back','backache']),
 'sore throat':   ('Sore throat',          ['sore throat','painful throat','throat hurts','koo']),
 'earache':       ('Earache',              ['earache','ear pain','pain in the ear','ear infection']),
 'toothache':     ('Toothache',            ['toothache','tooth pain','tooth hurts','pain in the tooth']),
 'bleeding gums': ('Bleeding gums',        ['bleeding gums','gums bleed','gums that bleed','sore bleeding gums']),
 'sore gums':     ('Sore gums',            ['sore gums','gums are sore','swollen gums','painful gums']),
 'loose tooth':   ('Loose tooth',          ['loose tooth','tooth is loose','loose teeth']),
 'mouth sores':   ('Sores in the mouth',   ['sores in the mouth','canker sore','mouth ulcer','fever blister','cold sore']),
 'white patches': ('White patches in mouth',['white patch','white patches','thrush']),
 'bad breath':    ('Bad breath',           ['bad breath','foul smell from the mouth','bad smell in the mouth']),
 'dizzy':         ('Dizziness',            ['dizzy','dizziness','light-headed','faint']),
 'blurred vision':('Trouble seeing',       ['trouble seeing','blurred','cannot see well','poor vision','night blindness']),
 'red eyes':      ('Red or painful eyes',  ['red eyes','painful eyes','red, painful eye','pink eye']),
 'discharge':     ('Discharge',            ['discharge','pus','drainage']),
 'bleeding':      ('Bleeding',             ['bleeding','loss of blood','hemorrhage','haemorrhage']),
 'burn':          ('Burn',                 ['burn','burns','scald']),
 'bite':          ('Bite or sting',        ['snakebite','bite','sting','bitten']),
 'cannot drink':  ('Cannot drink',         ['cannot drink','will not drink','refuses to drink','unable to drink']),
 'not feeding':   ('Baby not feeding',     ['stops sucking','will not suck','not feeding','refuses the breast']),
 'slow growth':   ('Child not growing',    ['not growing','slow growth','poor growth','малnutrition','malnutrition']),
 'constipation':  ('Constipation',         ['constipation','cannot pass stool','hard stool']),
 'blue lips':     ('Blue lips or nails',   ['blueness of lips','blue lips','bluish skin','blue nails']),
 'swollen face':  ('Swollen face',         ['swollen face','face is swollen','swelling of the face']),
 'bulging soft spot':('Bulging soft spot', ['bulging soft spot','soft spot bulges','fontanel']),
 'sunken soft spot':('Sunken soft spot',   ['sagging in of the soft spot','sunken soft spot','sunken fontanel']),
}

HEDGE = re.compile(r'\b(sometimes|may |might|can be|occasionally|rarely|in some)\b', re.I)
STRONG = re.compile(r'\b(always|typical|characteristic|the first sign|most common)\b', re.I)


def weight_for(sentence, where, at=0):
    """Weight from the book's own hedging, but only when the hedge word
    actually qualifies the phrase we matched - not a parenthetical later
    in the same sentence."""
    if where == 'title':
        return 'd'
    if where == 'intro':
        return 's'
    window = sentence[max(0, at - 70): at + 24]
    if HEDGE.search(window):
        return 's'
    if STRONG.search(sentence):
        return 'd'
    return 'c'


# ------------------------------------------------------- topics -> app
def slug(s, n=0):
    b = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:46]
    return f'{b}-{n}' if n else b


# The PDF's column reflow turns some mid-sentence fragments into
# all-caps "headings". The book's own index is the authority on what is a
# real subject, so score against it and keep the fragments out of search.
INDEX_TERMS = {re.sub(r'[^a-z ]', '', i['term'].lower()).strip()
               for i in raw['index']}
# Conjunctions and prepositions only. "How To Control Bleeding From A Wound"
# is a real section heading; "Or Burning Of The Skin" is a broken line.
FRAGMENT = re.compile(
    r'^(that|or|and|but|because|after|before|while|then|also|these|those|'
    r'them|they|it|is|are|was|were|his|her|their|from|on|at|by|as|an|in|to|'
    r'for|with|may|which|into|about|over|under|until|unless|so|such)'
    r'(?=\s|$)', re.I)
INDEXLINE = re.compile(r',\s*\d|\.\s*\d{2,}|^[A-Z]\.[A-Z]\.')


def quality(t):
    title = t['title'].strip()
    bare = re.sub(r'[^a-z ]', '', title.lower()).strip()
    q = 0
    stem = re.sub(r'\s*\(.*$', '', bare).strip()
    parts = [stem] + [p.strip() for p in re.split(r' and | or |, ', stem) if len(p.strip()) > 4]
    if any(p in INDEX_TERMS for p in parts):
        q += 3
    elif any(x.startswith(stem) or stem.startswith(x)
             for x in INDEX_TERMS if len(x) > 6):
        q += 1
    if t['signs']:
        q += 2
    if t['treat']:
        q += 1
    if len(t['intro']) > 200:
        q += 1
    # a sentence fragment the reflow turned into a heading is never a
    # subject: keep it browsable, but never let it reach search
    if FRAGMENT.match(title) or title.rstrip().endswith(('.', ',', ';')):
        return 0
    if INDEXLINE.search(title):
        q -= 6
    # a short title is not a bad title: Noma, Shock, Boils are real subjects
    if len(title) < 4 or len(title.split()) > 8:
        q -= 2
    return q


topics, used = [], {}
for t in raw['topics']:
    if not (t['signs'] or t['treat'] or t['prevent'] or len(t['intro']) > 120):
        continue
    s = slug(f"{t['book']}-{t['title']}")
    used[s] = used.get(s, 0) + 1
    topics.append({
        'id': s if used[s] == 1 else f'{s}-{used[s]}',
        'b': t['book'], 'p': t['page'], 'n': t['title'], 'q': quality(t),
        'i': t['intro'], 's': t['signs'], 't': t['treat'], 'v': t['prevent'],
    })

# symptom index, built from each topic's own words
sym_hits = {k: {} for k in SYMPTOMS}
for t in topics:
    if t['q'] < 2 or not (t['s'] or t['t'] or t['v']):
        continue
    title_l = t['n'].lower()
    intro_l = t['i'].lower()
    for key, (label, phrases) in SYMPTOMS.items():
        best = None
        # token fallback: the book words the same sign many ways, so also
        # accept a sign that carries every word of the canonical label
        toks = [w for w in re.split(r'[^a-z]+', label.lower())
                if len(w) > 2 and w not in ('the', 'and', 'for', 'with', 'baby', 'little')]
        if toks:
            for sign in t['s']:
                sl = sign.lower()
                if all(w in sl for w in toks):
                    at = sl.find(toks[0])
                    w2 = weight_for(sign, 'sign', at)
                    rank = {'s': 0, 'c': 1, 'd': 2}
                    if best is None or rank[w2] > rank[best]:
                        best = w2
        for ph in phrases:
            if ph in title_l:
                best = 'd'; break
            for sign in t['s']:
                at = sign.lower().find(ph)
                if at >= 0:
                    w = weight_for(sign, 'sign', at)
                    rank = {'s': 0, 'c': 1, 'd': 2}
                    if best is None or rank[w] > rank[best]:
                        best = w
            if best is None and ph in intro_l:
                best = 's'
        if best:
            sym_hits[key][t['id']] = best

symptoms = {k: {'label': v[0], 'syn': v[1], 'hits': sym_hits[k]}
            for k, v in SYMPTOMS.items() if sym_hits[k]}

# ----------------------------------------------------------- medicines
meds, seen = [], set()
for m in raw['medicines']:
    k = m['name'].lower()
    if k in seen or m['name'] in ('Cough', 'Comes as pamoate or embonate'):
        continue
    seen.add(k)
    meds.append({'id': slug(m['name']), 'n': m['name'], 'aka': m['aka'],
                 'use': m['use'], 'g': m.get('group', ''), 'p': m['page'],
                 'comes': m['comes'], 'c': m['cautions'], 'd': m['doses'],
                 'x': m['text']})

# anything the book's own medicine index lists in the green-page range
BAD = re.compile(r'^(For |Infections|Cortico$|Medicines|Other |Where |Dosage|List|'
                 r'Mixed|Note|Important|Caution|Warning|Price|Name|Also|Some|Many|'
                 r'This|That|These|When|How|What|Use )', re.I)
for m in raw.get('med_index', []):
    try:
        pg = int(m['page'])
    except ValueError:
        continue
    if not (339 <= pg <= 398):
        continue
    nm = re.sub(r'\s*\(.*$', '', m['name']).strip()
    if len(nm) < 4 or BAD.match(nm) or nm.lower() in seen:
        continue
    seen.add(nm.lower())
    meds.append({'id': slug(nm), 'n': nm, 'aka': '', 'use': m['use'], 'g': '',
                 'p': m['page'], 'comes': '', 'c': [], 'd': [], 'x': '',
                 'stub': 1})

# --------------------------------------------------------- danger signs
DANGER = json.load(open('build/danger.json'))

# ---------------------------------------------------------------- write
pages = [{'b': p['book'], 'p': p['page'], 'x': p['text']} for p in raw['pages']]
gloss = [{'b': g['book'], 't': g['term'], 'd': g['def']} for g in raw['glossary']]
index = [{'b': i['book'], 't': i['term'], 'p': i['pages']} for i in raw['index']]

out = {'books': raw['books'], 'pages': pages, 'topics': topics,
       'glossary': gloss, 'index': index, 'medicines': meds,
       'symptoms': symptoms, 'danger': DANGER}

json.dump(out, open('app/data.json', 'w'), ensure_ascii=False, separators=(',', ':'))

import os
print(json.dumps({
    'pages': len(pages), 'topics': len(topics), 'glossary': len(gloss),
    'index': len(index), 'medicines': len(meds),
    'medicines_with_doses': sum(1 for m in meds if m['d']),
    'symptoms': len(symptoms),
    'search_quality_topics': sum(1 for t in topics if t['q'] >= 2 and (t['s'] or t['t'] or t['v'])),
    'symptom_links': sum(len(s['hits']) for s in symptoms.values()),
    'bytes': os.path.getsize('app/data.json'),
}, indent=1))
