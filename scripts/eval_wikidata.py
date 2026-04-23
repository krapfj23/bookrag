"""Evaluate BookRAG extraction against Wikidata ground truth.

Pulls characters/locations known to appear in a given work from Wikidata
(via P1441 "present in work" and P674 "characters") and compares the set
to the Character/Location DataPoints BookRAG extracted into
`data/processed/{book_id}/batches/*/extracted_datapoints.json`.

Usage:
    python scripts/eval_wikidata.py <book_id> <wikidata_qid>
    python scripts/eval_wikidata.py red_rising_5740dde8 Q18393778
    python scripts/eval_wikidata.py christmas_carol_e6ddcd76 Q62879

Coverage caveat: most modern/genre fiction has thin Wikidata entity lists.
A low overlap doesn't mean BookRAG extraction is bad — it often means
Wikidata is empty. Print-all-sides output so you can judge.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
UA = "BookRAG-eval/0.1"


def _sparql(query: str) -> list[dict]:
    params = urlencode({"query": query, "format": "json"})
    req = Request(
        f"https://query.wikidata.org/sparql?{params}",
        headers={"Accept": "application/sparql-results+json", "User-Agent": UA},
    )
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())["results"]["bindings"]


def fetch_wikidata(qid: str) -> dict[str, set[str]]:
    """Return {'characters': set, 'locations': set} for the given work qid."""
    # Characters via P674 (characters) OR P1441 (present-in-work) on the work.
    q_chars = f"""
SELECT DISTINCT ?c ?cLabel WHERE {{
  {{ wd:{qid} wdt:P674 ?c . }}
  UNION
  {{ ?c wdt:P1441 wd:{qid} . ?c wdt:P31/wdt:P279* wd:Q95074 . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}"""
    # Locations: fictional settings / locations mentioned in the work.
    q_locs = f"""
SELECT DISTINCT ?l ?lLabel WHERE {{
  {{ wd:{qid} wdt:P840 ?l . }}
  UNION
  {{ ?l wdt:P1441 wd:{qid} . ?l wdt:P31/wdt:P279* wd:Q17334923 . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}"""
    chars = {b["cLabel"]["value"] for b in _sparql(q_chars)}
    locs = {b["lLabel"]["value"] for b in _sparql(q_locs)}
    return {"characters": chars, "locations": locs}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().strip().strip(".,;:\"' ")


def _aliases(name: str) -> set[str]:
    """Conservative alias set — full name, last word, hyphen/apostrophe stripped."""
    n = _norm(name)
    out = {n}
    for w in n.replace("-", " ").replace("'", " ").split():
        if len(w) >= 4:
            out.add(w)
    return out


def fetch_bookrag(book_id: str) -> dict[str, set[str]]:
    """Collapse extracted DataPoints across all batches into {type: set(name)}."""
    base = ROOT / "data" / "processed" / book_id / "batches"
    if not base.exists():
        sys.exit(f"No batches/ dir for {book_id} at {base}")
    out: dict[str, set[str]] = {"Character": set(), "Location": set(), "Faction": set()}
    for f in sorted(base.glob("*/extracted_datapoints.json")):
        data = json.loads(f.read_text())
        items = data if isinstance(data, list) else [
            {**v, "type": k[:-1] if k.endswith("s") else k} for k, lst in data.items() for v in (lst if isinstance(lst, list) else [])
        ]
        for item in items:
            t = item.get("type") or item.get("_type") or item.get("__class__")
            name = item.get("name") or item.get("label")
            if t in out and name:
                out[t].add(name)
    return out


def match(wikidata: set[str], bookrag: set[str]) -> tuple[set[str], set[str], set[str]]:
    """Return (matched_wd, matched_br, missed_wd)."""
    br_aliases = {a: name for name in bookrag for a in _aliases(name)}
    matched_wd, matched_br = set(), set()
    for wd_name in wikidata:
        hit = False
        for alias in _aliases(wd_name):
            if alias in br_aliases:
                matched_wd.add(wd_name)
                matched_br.add(br_aliases[alias])
                hit = True
                break
    return matched_wd, matched_br, wikidata - matched_wd


def report(book_id: str, qid: str) -> None:
    print(f"=== BookRAG vs Wikidata — {book_id} (wd:{qid}) ===\n")
    wd = fetch_wikidata(qid)
    br = fetch_bookrag(book_id)
    print(f"Wikidata:  characters={len(wd['characters'])}  locations={len(wd['locations'])}")
    print(f"BookRAG:   characters={len(br['Character'])}  locations={len(br['Location'])}  factions={len(br['Faction'])}\n")

    m_wd, m_br, miss = match(wd["characters"], br["Character"])
    recall = len(m_wd) / len(wd["characters"]) if wd["characters"] else float("nan")
    print(f"--- CHARACTERS ---  recall (Wikidata coverage by BookRAG): {recall:.0%}  ({len(m_wd)}/{len(wd['characters'])})")
    for name in sorted(m_wd):
        print(f"  MATCH   {name}")
    for name in sorted(miss):
        print(f"  MISSED  {name}")
    extra_br = br["Character"] - m_br
    print(f"\n  BookRAG-only characters ({len(extra_br)}):")
    for name in sorted(extra_br)[:40]:
        print(f"    + {name}")
    if len(extra_br) > 40:
        print(f"    … and {len(extra_br) - 40} more")

    m_wd, m_br, miss = match(wd["locations"], br["Location"])
    recall = len(m_wd) / len(wd["locations"]) if wd["locations"] else float("nan")
    print(f"\n--- LOCATIONS ---  recall: {recall:.0%}  ({len(m_wd)}/{len(wd['locations'])})")
    for name in sorted(m_wd):
        print(f"  MATCH   {name}")
    for name in sorted(miss):
        print(f"  MISSED  {name}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: eval_wikidata.py <book_id> <wikidata_qid>")
    report(sys.argv[1], sys.argv[2])
