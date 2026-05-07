# Top Referee

Agrégation de données sur l'arbitrage en Ligue 1 (saison en cours).

## Sources
- SofaScore API (publique non-officielle)
- *À venir* : LFP, FBref, Wikipedia

## Stack
- Python 3.11 (stdlib uniquement)
- GitHub Actions (orchestration hebdomadaire)

## Fonctionnement
Le workflow `.github/workflows/scrape.yml` se déclenche manuellement ou chaque lundi à 8h UTC. Il produit un CSV téléchargeable en artifact GitHub.
