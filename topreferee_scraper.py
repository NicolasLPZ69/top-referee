"""
Top Referee — Scraper FBref (Ligue 1, saison en cours)
Source : fbref.com — page officielle des arbitres

Sortie : ligue1_arbitres_fbref.csv
Une ligne par arbitre avec ses stats agrégées sur la saison.
"""

import urllib.request
import urllib.error
import csv
import sys
import re
from io import StringIO

URL = "https://fbref.com/fr/comps/13/officials/Statistiques-Ligue-1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main():
    print(f"Fetching {URL}")
    try:
        html = fetch(URL)
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code} : {e.reason}", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(html):,} bytes")

    # FBref encapsule certaines tables dans des commentaires HTML
    # pour limiter le scraping naïf. On les "déballe".
    html = html.replace("<!--", "").replace("-->", "")

    import pandas as pd

    tables = pd.read_html(StringIO(html))
    print(f"  {len(tables)} tables détectées")

    # Localiser la table arbitres (présence d'une colonne "Arbitre")
    target = None
    for i, t in enumerate(tables):
        cols = []
        for c in t.columns:
            if isinstance(c, tuple):
                cols.extend(str(x).lower() for x in c)
            else:
                cols.append(str(c).lower())
        if any("arbitre" in c for c in cols):
            target = t
            print(f"  → table arbitres trouvée (index {i}, {len(t)} lignes)")
            break

    if target is None:
        print("  ! Aucune table d'arbitres détectée", file=sys.stderr)
        for i, t in enumerate(tables[:5]):
            sample = list(t.columns)[:6]
            print(f"    table {i} : {sample}", file=sys.stderr)
        sys.exit(1)

    # Aplatir les en-têtes multi-niveaux
    if isinstance(target.columns, pd.MultiIndex):
        new_cols = []
        for c in target.columns:
            label = c[-1] if c[-1] and not c[-1].startswith("Unnamed") else c[-2]
            new_cols.append(label)
        target.columns = new_cols

    # Retirer les lignes vides / résumés
    target = target.dropna(how="all")
    if "Arbitre" in target.columns:
        target = target[target["Arbitre"].notna()]
        target = target[target["Arbitre"] != "Arbitre"]  # virer les ré-headers

    out = "ligue1_arbitres_fbref.csv"
    target.to_csv(out, index=False, encoding="utf-8")
    print(f"\n→ {len(target)} arbitres exportés dans {out}")
    print(f"  Colonnes : {list(target.columns)}")


if __name__ == "__main__":
    main()
