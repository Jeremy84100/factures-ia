# Factures IA

Déposez des factures PDF : elles sont lues par une IA, **vérifiées automatiquement**, puis rangées dans PostgreSQL. Ce qui ne colle pas est signalé et se corrige à la main.

Exemple d'usage : un cabinet comptable reçoit 300 factures par mois et ne veut plus les saisir à la main.

**En ligne : https://factures-ia.vercel.app**. Créez un compte, puis déposez une des factures d'exemple de [`backend/tests/fixtures/invoices`](backend/tests/fixtures/invoices).

## Ce que fait l'application

1. **Dépôt** : jusqu'à 50 PDF par envoi, 10 Mo maximum chacun. Le fichier est contrôlé (signature `%PDF`) puis stocké en base.
2. **Lecture** : [Docling](https://github.com/docling-project/docling) transforme le PDF en texte structuré, tableaux compris. Son OCR est coupé : il faisait monter la mémoire à 2,5 Go, au-delà des 2 Go de Vercel, et Gemini lit déjà les scans à partir du PDF (10 scans sur 10 justes sans lui).
3. **Extraction** : Gemini 3.5 Flash-Lite reçoit le PDF lui-même **et** le texte Docling. Il voit ainsi les logos et la mise en page, et le texte l'aide à lire les chiffres. Il renvoie fournisseur, numéro, date, HT, TVA, TTC et devise, dans un JSON imposé par un schéma Pydantic.
4. **Vérifications**, dans [`app/services/checks.py`](backend/app/services/checks.py) :
   - HT + TVA = TTC, à 2 centimes près ;
   - champs obligatoires présents (fournisseur, date, TTC) ;
   - pas de doublon (même fournisseur et même numéro pour un même utilisateur) ;
   - pas de date dans le futur ;
   - montant négatif accepté seulement sur un avoir ; les avoirs sont comptés en négatif, même quand ils sont écrits en positif comme le prévoit la norme EN 16931 ;
   - TVA à 0 acceptée seulement avec une mention d'exonération (article 262 du CGI, autoliquidation…), obligatoire sur une facture française ;
   - même numéro qu'une autre facture du même fournisseur : « doublon » si le montant est identique, « même numéro mais un autre montant » sinon (un numéro de facture ne se réutilise pas) ;
   - date américaine ambiguë (06/02 : 6 février ou 2 juin ?) signalée si l'IA l'a lue à l'européenne.
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

Ces factures sont propres et générées par programme. Le vrai test a été fait sur **42 factures publiques** : exemples officiels Factur-X de la FNFE, factures réelles d'AWS, Free, Coolblue, Hetzner ou Flipkart ([invoice2data](https://github.com/invoice-x/invoice2data), [ZUGFeRD corpus](https://github.com/ZUGFeRD/corpus)), et 10 scans sans texte ([jeu de données de sparrow](https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1)).

| | Texte seul | PDF + texte et règle des dates |
|---|---|---|
| Fournisseur faux ou introuvable | 4 | **0** |
| Date américaine inversée | 3, passées **en silence** | 3, **toutes signalées** |
| Erreur de montant non signalée | 0 | 0 |

Ce qui n'a pas marché, et a été retiré :
- préciser le format des dates dans la consigne : Gemini inverse toujours les dates américaines, seule la règle dans le code les attrape ;
- demander à l'IA sa confiance pour chaque champ : elle se donne 100 % même sur une date fausse.

Les règles « avoir » et « TVA à 0 » ont été vérifiées sur les mêmes 42 factures : les 3 avoirs et les 4 factures exonérées passent sans fausse alerte, et les 3 factures sans TVA ni mention (AWS, QualityHosting, une facture de test) sont signalées.

D'où le principe du projet : **l'IA lit, le code vérifie.**

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

## Mise en ligne

Vercel (fonction Python, région Francfort) et PostgreSQL chez Neon. [`backend/scripts/vercel-build.sh`](backend/scripts/vercel-build.sh) construit l'interface, télécharge les modèles Docling et applique les migrations à chaque déploiement. PyTorch est installé en version CPU pour garder la fonction sous la limite de taille.

## Lancer en local

Il faut Docker Desktop, [uv](https://docs.astral.sh/uv/) et [bun](https://bun.sh).

```bash
cp .env.example .env
```

Dans `.env`, mettez votre propre `SECRET_KEY`, le mot de passe Postgres et votre `GEMINI_API_KEY` ([Google AI Studio](https://aistudio.google.com)). Ensuite :

```bash
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head && uv run python scripts/create_admin.py
cd ../frontend && bun install && bun run build
cd ../backend && uv run fastapi dev
```

`create_admin.py` demande l'e-mail et le mot de passe de l'administrateur au clavier : ils ne sont écrits dans aucun fichier. L'application est sur http://localhost:8000.

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
