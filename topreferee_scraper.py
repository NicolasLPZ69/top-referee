"""
Top Referee — Scraper SofaScore via RapidAPI (apidojo)
"""

import os
import urllib.request
import urllib.error
import json
import csv
import time
import sys

API_KEY = os.environ.get("RAPIDAPI_KEY")
if not API_KEY:
    print("ERROR: variable d'environnement RAPIDAPI_KEY manquante", file=sys.stderr)
    sys.exit(1)

HOST = "sofascore.p.rapidapi.com"
BASE = f"https://{HOST}"
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
    "Accept": "application/json",
}
LIGUE1_TOURNAMENT_ID = 34
RATE_LIMIT_S = 0.5


def call(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"  ! HTTP {e.code} sur {path} : {body}", file=sys.stderr)
        raise
    time.sleep(RATE_LIMIT_S)
    return data


def get_current_season():
    data = call(f"/tournaments/get-seasons?tournamentId={LIGUE1_TOURNAMENT_ID}")
    seasons = data.get("seasons", []) or []
    if not seasons:
        raise RuntimeError("Aucune saison retournee par l'API")
    s = seasons[0]
    return s["id"], s.get("year", "?")


def get_last_round(season_id):
    data = call(
        f"/tournaments/get-rounds?tournamentId={LIGUE1_TOURNAMENT_ID}&seasonId={season_id}"
    )
    rounds = data.get("rounds", []) or []
    if not rounds:
        return 1
    return rounds[-1].get("round", 1)


def get_round_events(season_id, round_num):
    data = call(
        f"/tournaments/get-events?tournamentId={LIGUE1_TOURNAMENT_ID}"
        f"&seasonId={season_id}&round={round_num}"
    )
    return data.get("events", []) or []


def get_match_data(match_id):
    detail = call(f"/matches/get-detail?matchId={match_id}")
    incidents = call(f"/matches/get-incidents?matchId={match_id}")
    try:
        stats = call(f"/matches/get-statistics?matchId={match_id}")
    except urllib.error.HTTPError:
        stats = {"statistics": []}
    return detail, incidents, stats


def parse(detail, incidents_raw, stats_raw):
    event = detail.get("event") or detail.get("match") or {}
    referee = event.get("referee") or {}
    home = (event.get("homeTeam") or {}).get("name")
    away = (event.get("awayTeam") or {}).get("name")

    incidents = incidents_raw.get("incidents", []) or []
    yellow = sum(
        1 for i in incidents
        if i.get("incidentType") == "card"
        and i.get("incidentClass") in ("yellow", "yellowRed")
    )
    red = sum(
        1 for i in incidents
        if i.get("incidentType") == "card"
        and i.get("incidentClass") in ("red", "yellowRed")
    )
    var_decisions = [i for i in incidents if i.get("incidentType") == "varDecision"]

    fouls_home = fouls_away = None
    for period in (stats_raw.get("statistics") or []):
        if period.get("period") == "ALL":
            for group in period.get("groups", []):
                for item in group.get("statisticsItems", []):
                    if item.get("name") in ("Fouls", "Fautes"):
                        fouls_home = item.get("home")
                        fouls_away = item.get("away")

    return {
        "match_id": event.get("id"),
        "home_team": home,
        "away_team": away,
        "score_home": (event.get("homeScore") or {}).get("current"),
        "score_away": (event.get("awayScore") or {}).get("current"),
        "referee_id": referee.get("id"),
        "referee_name": referee.get("name"),
        "referee_country": (referee.get("country") or {}).get("name"),
        "yellow_cards": yellow,
        "red_cards": red,
        "var_decisions": len(var_decisions),
        "fouls_home": fouls_home,
        "fouls_away": fouls_away,
    }


def main():
    season_id, year = get_current_season()
    print(f"Saison Ligue 1 {year} (id={season_id})")

    round_num = get_last_round(season_id)
    print(f"Derniere journee disponible : {round_num}")

    events = get_round_events(season_id, round_num)
    print(f"  {len(events)} matchs trouves")

    rows = []
    for ev in events:
        status_type = (ev.get("status") or {}).get("type")
        if status_type != "finished":
            continue
        match_id = ev.get("id")
        try:
            d, i, s = get_match_data(match_id)
            row = parse(d, i, s)
            rows.append(row)
            print(
                f"  OK {row['home_team']} {row['score_home']}-{row['score_away']} "
                f"{row['away_team']} | arbitre : {row['referee_name']} "
                f"| J:{row['yellow_cards']} R:{row['red_cards']} VAR:{row['var_decisions']}"
            )
        except Exception as e:
            print(f"  KO {match_id} : {e}")

    if not rows:
        print("Aucune donnee extraite.")
        sys.exit(1)

    out = "ligue1_arbitrage_test.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n=> {len(rows)} matchs exportes dans {out}")


if __name__ == "__main__":
    main()
