# Instructions permanentes PlaniFY

- Stack : Python 3.12, FastAPI, SQLAlchemy 2.0 (sync, endpoints en `def`), Alembic, Pydantic v2, PostgreSQL 16, pytest ; React + Vite + TypeScript + Tailwind + Frappe Gantt + Recharts ; Anthropic SDK Python.
- Architecture en couches strictes : `api` (routers) -> `services` (logique métier) -> `repositories` (accès données). Les routers n'accèdent jamais directement à la DB.
- Les calculs de planning (chemin critique, marges, sur-allocation, dates) sont toujours déterministes dans `backend/app/services`, jamais dans le LLM et jamais dans le frontend.
- L'agent IA appelle uniquement des outils qui appellent les services.
- Le motif d'indisponibilité (congé/maladie) n'est jamais transmis au LLM.
- Toute action de l'agent est enregistrée dans la table `agent_actions` avec statut `EN_ATTENTE` tant que le chef de projet n'a pas validé.
- Type hints partout, docstrings courtes en français, noms de code en anglais, interface utilisateur en français.
- Chaque fonction de calcul a des tests pytest.
- Secrets uniquement via des variables d'environnement, jamais en dur.

