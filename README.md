# Factures IA

Déposez des factures PDF : elles sont lues par une IA, **vérifiées automatiquement**, puis rangées dans PostgreSQL. Ce qui ne colle pas est signalé et se corrige à la main.

Exemple d'usage : un cabinet comptable reçoit 300 factures par mois et ne veut plus les saisir à la main.

## Ce que fait l'application

1. **Dépôt** : jusqu'à 50 PDF par envoi, 10 Mo maximum chacun. Le fichier est contrôlé (signature `%PDF`) puis stocké en base.
2. **Lecture** : [Docling](https://github.com/docling-project/docling) transforme le PDF en texte structuré, OCR compris pour les scans.
3. **Extraction** : Gemini 3.5 Flash-Lite renvoie fournisseur, numéro, date, HT, TVA, TTC et devise. Le format JSON est imposé par un schéma Pydantic.
4. **Vérifications**, dans [`app/services/checks.py`](backend/app/services/checks.py) :
   - HT + TVA = TTC, à 2 centimes près ;
   - champs obligatoires présents (fournisseur, date, TTC) ;
   - pas de doublon (même fournisseur et même numéro pour un même utilisateur) ;
   - pas de date dans le futur, pas de montant négatif.
5. **Statut** de chaque facture : `Validée`, `À vérifier`, `Illisible` ou `Erreur IA`, avec la raison en clair.
6. **Correction** à la main, après quoi les vérifications sont relancées. On peut aussi relancer la lecture par l'IA.
7. **Tableau de bord** : compteurs par statut et dépenses de l'année par fournisseur (factures validées uniquement).

Le traitement se fait en arrière-plan. L'interface se met à jour toute seule pendant la lecture.

## Qualité mesurée

`backend/scripts/evaluate.py` compare les réponses de l'IA à la vérité sur 12 factures générées par `backend/scripts/generate_invoices.py` :

| Champ | Exactitude |
|---|---|
| Fournisseur, numéro, date | 100 % |
| HT, TVA, TTC | 100 % |

Ces factures sont propres et générées par programme. Le vrai test, ce sont des scans réels : c'est le rôle des vérifications automatiques, qui attrapent les erreurs au lieu de les laisser passer en silence.

## Architecture

```
backend/app/
  api/routes/invoices.py   dépôt, liste, correction, relecture, PDF, totaux
  services/pdf_reader.py   PDF -> texte (Docling)
  services/extraction.py   texte -> champs (Gemini), interface commune pour changer de modèle
  services/checks.py       règles de vérification, sans base ni IA, testées seules
  services/processing.py   enchaîne lecture -> extraction -> vérifications, gère chaque erreur
frontend/src/
  routes/_layout/invoices.tsx   tableau des factures, filtres par statut
  components/Invoices/          dépôt, correction, actions
```

L'IA est isolée derrière deux interfaces (`PdfReader`, `InvoiceExtractor`). Les tests les remplacent par de fausses versions : ils tournent sans clé API et sans réseau.

## Stack

FastAPI, SQLModel, Pydantic, PostgreSQL, Alembic, Docling, Gemini (`google-genai`), React, Vite, TanStack Router et Query, Tailwind, shadcn/ui, Pytest, uv et bun.

## Lancer en local

Il faut Docker Desktop, [uv](https://docs.astral.sh/uv/) et [bun](https://bun.sh).

```bash
cp .env.example .env
```

Dans `.env`, mettez vos propres mots de passe et votre `GEMINI_API_KEY` ([Google AI Studio](https://aistudio.google.com)). Ensuite :

```bash
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head && uv run python app/initial_data.py
cd ../frontend && bun install && bun run build
cd ../backend && uv run fastapi dev
```

L'application est sur http://localhost:8000. Connectez-vous avec `FIRST_SUPERUSER` et `FIRST_SUPERUSER_PASSWORD`.

```bash
cd backend && uv run pytest
```

```bash
cd backend && uv run python scripts/evaluate.py
```

Sous Windows, préfixez les commandes `fastapi` par `PYTHONUTF8=1` si la console affiche une erreur d'encodage.

## Crédits et licence

Ce projet part du [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template) (MIT, voir `LICENSE-full-stack-fastapi-template`). L'organisation du traitement s'inspire de [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) et l'interface d'extraction de [sparrow](https://github.com/katanaml/sparrow).

Licence : GPL-3.0.
