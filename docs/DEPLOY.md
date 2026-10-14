# Déployer PlaniFY

Ce guide décrit un déploiement avec un service web backend, une base
PostgreSQL managée et un frontend statique. Les exemples utilisent Render,
mais les mêmes étapes s'appliquent à Railway.

## 1. Créer la base PostgreSQL

1. Créez une base PostgreSQL 16 sur Render ou Railway.
2. Copiez son URL de connexion interne dans `DATABASE_URL`.
3. Utilisez une URL compatible avec SQLAlchemy et psycopg, par exemple
   `postgresql+psycopg://utilisateur:mot-de-passe@hote:5432/base`.

## 2. Déployer le backend

Créez un service web depuis le dépôt Git :

1. Sélectionnez le runtime Docker.
2. Définissez le chemin du Dockerfile sur `backend/Dockerfile`.
3. Configurez le port `8000`.
4. Définissez la commande de démarrage :
   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`.
5. Ajoutez les variables suivantes :
   - `DATABASE_URL` : URL de la base PostgreSQL managée ;
   - `ANTHROPIC_API_KEY` : clé fournie par Anthropic ;
   - `ANTHROPIC_MODEL` : modèle Anthropic à utiliser ;
   - `JWT_SECRET` : secret aléatoire propre à l'environnement ;
   - `JWT_EXPIRE_MINUTES` : durée de vie des jetons ;
   - `CORS_ORIGINS` : URL(s) autorisée(s) du frontend, séparées par des virgules.

Ne placez aucune valeur secrète dans le dépôt. Utilisez uniquement les
variables secrètes du fournisseur.

Après le premier déploiement, appliquez les migrations si nécessaire :

```bash
alembic upgrade head
```

Pour créer les données de démonstration, exécutez ensuite `backend/scripts/seed.py`
dans un shell du service backend avec les mêmes variables d'environnement :

```bash
python scripts/seed.py
```

N'exécutez le seed qu'une seule fois sur une base vide ou après avoir vérifié
qu'il est idempotent pour l'environnement ciblé.

## 3. Déployer le frontend statique

Créez un site statique depuis le dossier `frontend` :

1. Installation : `npm ci`.
2. Build : `npm run build`.
3. Dossier publié : `dist`.
4. Variable `VITE_API_URL` : URL publique du backend, par exemple
   `https://planify-api.example.com`.

Pour un hébergement Docker du frontend, le Dockerfile accepte aussi :

```bash
docker build \
  --build-arg VITE_API_URL=https://planify-api.example.com \
  -t planify-frontend frontend
```

## 4. Finaliser CORS

Après avoir obtenu l'URL publique du frontend, mettez à jour `CORS_ORIGINS`
dans le service backend avec cette origine exacte, sans chemin final :

```text
CORS_ORIGINS=https://planify-frontend.example.com
```

Pour plusieurs origines, séparez-les par des virgules :

```text
CORS_ORIGINS=https://planify-frontend.example.com,http://localhost:5173
```

Redéployez le backend après cette modification, puis vérifiez `/health`, la
connexion et les appels API depuis le frontend.
