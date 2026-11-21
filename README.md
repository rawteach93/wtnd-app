# Where There Is No Doctor — offline handbook

Both Hesperian village-health handbooks as one offline-first web app:
symptom search, danger-sign triage, the green-pages medicines, the
vocabulary, both indexes, and every page of both books in full.

| | |
|---|---|
| Pages (full text) | 678 — 457 Doctor, 221 Dentist |
| Subjects parsed | 595, of which 192 are clean enough for search |
| Symptom terms | 58, linked to subjects 651 ways |
| Medicines | 378 green-page entries, 48 with a parsed dose table |
| Vocabulary | 520 terms |
| Index entries | 1,605 |
| Danger signs | 20, hand-checked against p. 42 |
| Payload | ~2.5 MB JSON, ~600 KB over the wire gzipped |

## Deploying to Vercel

No build step. These are static files.

```bash
git init && git add . && git commit -m "Where There Is No Doctor — offline handbook"
gh repo create wtnd-app --private --source=. --push
```

Then import the repo at vercel.com/new, or:

```bash
vercel --prod
```

`vercel.json` sets long cache headers on `data.json` and no-cache on
`sw.js`, which is the combination that lets the service worker update
itself without stranding people on an old dataset.

## What is in here

```
index.html              the whole app — no framework, no build
data.json               both books, extracted and structured
sw.js                   precaches everything on install
manifest.webmanifest    installable to a home screen
vercel.json             cache headers
icon-192.png
icon-512.png
```

The service worker caches every asset on first visit, so after one load
the app needs no network at all. That is the point of it: the person who
most needs this book is the one with no bundle left.

## How the search works

1. **Term extraction** — a dictionary match, not a model. Symptom words
   plus a Kiswahili and lay-English synonym layer (*homa*, *kuhara*,
   *kukohoa*, *degedege*, *running stomach*).
2. **Danger check** — the twenty signs from p. 42 split into *hard*
   (stating it is already the danger: stiff neck, coughing blood) and
   *soft* (needs a qualifier the book names: a duration, a count). Hard
   signs take over the screen. Soft ones become a follow-up question.
3. **Ranking** — each subject scores by how strongly its own Signs list
   carries the terms. The three weights come from the book's own hedging:
   plainly stated, *often*, *sometimes*.
4. **Full text** — when the structured layer finds little, the app
   searches all 678 pages. Anything the parser missed is still reachable.

## Regenerating the dataset

```bash
python3 build/extract.py     # PDFs text -> build/dataset.raw.json
python3 build/dataset.py     # -> app/data.json
```

`extract.py` anchors on the page footers, uses the Doctor book's bullet
(•) and diamond (♦) glyphs to tell signs from treatment — they survive
the PDF's column reflow, which heading order does not — and the Dentist
book's `SIGNS:` / `TREATMENT:` headings.

## Known limits — read before trusting a dose

- The text came out of the published PDFs **automatically and has not been
  checked page by page**. Column reflow can reorder lines.
- Only 48 of the green-page medicines produced a clean dose table. The
  rest link to their page text. **Check every dose against the printed
  book** — page numbers are kept on every screen for exactly that.
- Werner's illustrations are not included. They carry real instructional
  weight and the finished app needs them; ask Hesperian for the artwork.
- A few subjects (Measles, Whooping cough, Polio) did not parse into
  their own entry and are reachable only through full-text search.

## Copyright

*Where There Is No Doctor* © David Werner, Carol Thuman, Jane Maxwell.
*Where There Is No Dentist* © Murray Dickson. Both published by
**Hesperian Health Guides**, Berkeley, California.

Hesperian's open copyright policy permits copying and adapting any part
of these books, including the illustrations, for **non-commercial**
purposes with credit. For an adaptation like this one they ask to be
contacted first: **permissions@hesperian.org**. Do that before this goes
anywhere public — they have supported volunteer digital projects for
years and may supply cleaner source text and the artwork.
