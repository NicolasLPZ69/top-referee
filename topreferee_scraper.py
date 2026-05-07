"""
Top Referee — Scraper Ligue 1 (saison en cours)
Source : SofaScore API (publique non-officielle)

Sortie : ligue1_arbitrage_<saison>.csv
Une ligne par match avec les KPIs arbitrage de base.
"""

import urllib.request
import urllib.error
import json
import csv
import time
import sys
from datetime import datetime

BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
LIGUE1_TOURNAMENT_ID = 34
RATE_LIMIT_SECONDS = 1.5  # politesse — ne pas baisser

# ---------------------------------------------------------------------------

def get(url):
    """Appel HTTP simple, JSON parsé, rate limit intégré."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code} sur {url}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"  ! Réseau : {e.reason}", file=sys.stderr)
        raise
    time.sleep(RATE_LIMIT_SECONDS)
    return data


def get_current_season():
    """Retourne (season_id, label) de la saison Ligue 1 en cours."""
    data = get(f"{BASE}/unique-tournament/{LIGUE1_TOURNAMENT_ID}/seasons")
    season = data["seasons"][0]  # la plus récente est en premier
    return season["id"], season["year"]


def get_round_events(season_id, round_num):
    """Liste des matchs d'une journée."""
    url = f"{BASE}/unique-tournament/{LIGUE1_TOURNAMENT_ID}/season/{season_id}/events/round/{round_num}"
    return get(url).get("events", [])


def get_match_details(event_id):
    """Récupère event + incidents + statistiques d'un match."""
    event = get(f"{BASE}/event/{event_id}").get("event", {})
    incidents = get(f"{BASE}/event/{event_id}/incidents").get("incidents", [])
    try:
        stats = get(f"{BASE}/event/{event_id}/statistics").get("statistics", [])
    except urllib.error.HTTPError:
        stats = []
    return event, incidents, stats


def extract_fouls(stats):
    """Extrait les fautes domicile/extérieur depuis le bloc stats."""
    home, away = None, None
    for period in stats:
        if period.get("period") == "ALL":
            for group in period.get("groups", []):
                for item in group.get("statisticsItems", []):
                    if item.get("name") in ("Fouls", "Fautes"):
                        home = item.get("home")
                        away = item.get("away")
    return home, away


def parse_match(event, incidents, stats):
    """Transforme les données brutes en une ligne propre."""
    referee = event.get("referee") or {}
    home_team = event.get("homeTeam", {}).get("name")
    away_team = event.get("awayTeam", {}).get("name")

    yellow = sum(
        1 for i in incidents
        if i.get("incidentType") == "card" and i.get("incidentClass") in ("yellow", "yellowRed")
    )
    red = sum(
        1 for i in incidents
        if i.get("incidentType") == "card" and i.get("incidentClass") in ("red", "yellowRed")
    )
    var_decisions = [i for i in incidents if i.get("incidentType") == "varDecision"]
    var_count = len(var_decisions)
    var_overturns = sum(
        1 for v in var_decisions
        if v.get("decision") in ("overturned", "goalAwarded", "penaltyAwarded", "redCardGiven", "noPenalty", "goalNotAwarded")
    )

    fouls_home, fouls_away = extract_fouls(stats)

    return {
        "match_id": event.get("id"),
        "date": datetime.fromtimestamp(event["startTimestamp"]).date().isoformat() if event.get("startTimestamp") else None,
        "round": event.get("roundInfo", {}).get("round"),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": event.get("homeScore", {}).get("current"),
        "away_score": event.get("awayScore", {}).get("current"),
        "referee_id": referee.get("id"),
        "referee_name": referee.get("name"),
        "referee_country": (referee.get("country") or {}).get("name"),
        "yellow_cards": yellow,
        "red_cards": red,
        "var_decisions_total": var_count,
        "var_decisions_overturned": var_overturns,
        "fouls_home": fouls_home,
        "fouls_away": fouls_away,
    }


def main():
    season_id, year = get_current_season()
    print(f"Saison Ligue 1 {year} (id {season_id})")

    rows = []
    for round_num in range(1, 39):  # 38 journées max
        try:
            events = get_round_events(season_id, round_num)
        except urllib.error.HTTPError:
            break
        if not events:
            break

        finished = [e for e in events if e.get("status", {}).get("type") == "finished"]
        if not finished:
            print(f"  Journée {round_num} : pas encore jouée, on s'arrête.")
            break

        print(f"  Journée {round_num} : {len(finished)} match(s) terminé(s)")
        for event in finished:
            try:
                e, inc, st = get_match_details(event["id"])
                row = parse_match(e, inc, st)
                rows.append(row)
                print(f"    ✓ {row['home_team']} {row['home_score']}-{row['away_score']} {row['away_team']} "
                      f"(arbitre : {row['referee_name']})")
            except Exception as ex:
                print(f"    ✗ {event.get('id')} : {ex}")

    if not rows:
        print("Aucun match récupéré.")
        return

    out = f"ligue1_arbitrage_{year.replace('/', '_')}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n→ {len(rows)} matchs exportés dans {out}")


if __name__ == "__main__":
    main()
