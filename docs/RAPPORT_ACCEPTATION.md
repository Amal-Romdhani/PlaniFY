# Rapport d'acceptation des scénarios

| Critère §13.3 | Résultat attendu | Résultat mesuré |
|---|---:|---:|
| Détection correcte des conflits | 100 % | 100.0% |
| Aucun appel LLM sans conflit | 100 % | 100.0% |
| Réponses validées par le garde-fou | 100 % | 100.0% |
| Propositions cohérentes avec les résultats d'outils | 100 % | 100.0% |
| Recalcul CPM pour 50 tâches | < 2 s | 0.0005 s |
| Écritures planning avant validation | 0 | 0 |
| Motif d'absence transmis au LLM | 0 occurrence | Vérifié par le test RGPD global |
| Cycle déclaration -> agent -> acceptation -> historique | Fonctionnel | Vérifié par le test E2E |

## Mesures détaillées

| Mesure | Résultat | Seuil |
|---|---:|---:|
| Détection correcte des conflits | 100.0% | 100% |
| Absence d'appel LLM sans conflit | 100.0% | 100% |
| Réponses validées par le garde-fou | 100.0% | 100% |
| Propositions cohérentes avec les outils | 100.0% | 100% |
| Recalcul CPM pour 50 tâches | 0.0005 s | < 2 s |
| Écritures planning avant validation | 0 | 0 |
