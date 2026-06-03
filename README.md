<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-19-61dafb?style=for-the-badge&logo=react&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-Signal-8CAAE6?style=for-the-badge&logo=scipy)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

<br/>

# PrognoSense

**Plateforme Intelligente de Maintenance Prédictive Industrielle**

*Basée sur l'analyse vibratoire et l'intelligence artificielle*

</div>

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Différenciateurs](#2-différenciateurs)
3. [Fonctionnalités principales](#3-fonctionnalités-principales)
4. [Nouveautés v3 (industrialisation)](#4-nouveautés-v3-industrialisation)
5. [Datasets et défauts couverts](#5-datasets-et-défauts-couverts)
6. [Architecture](#6-architecture)
7. [Performances réelles](#7-performances-réelles)
8. [Installation](#8-installation)
9. [Utilisation](#9-utilisation)
10. [Spécifications techniques](#10-spécifications-techniques)
11. [Sécurité et conformité](#11-sécurité-et-conformité)
12. [Roadmap](#12-roadmap)

---

## 1. Vue d'ensemble

PrognoSense est une plateforme logicielle qui combine l'analyse de signaux vibratoires et des modèles d'intelligence artificielle pour détecter les dégradations d'équipements **avant la panne**, et faire basculer la maintenance d'une logique corrective ou calendaire vers une logique **prédictive**, fondée sur l'état réel de chaque machine.

Elle adresse un enjeu critique de l'industrie : la réduction des temps d'arrêt non planifiés, principale source de pertes. La solution est conçue pour être **accessible** à des ingénieurs de maintenance sans expertise en science des données, **ouverte** (connectable au parc existant) et **explicable**.

---

## 2. Différenciateurs

### Détection d'anomalies non supervisée
Un auto-encodeur (PyTorch) entraîné **uniquement sur des données saines** détecte les défauts **inconnus**, jamais vus à l'entraînement : quand une anomalie apparaît, l'erreur de reconstruction augmente brusquement. C'est une couche de protection contre les modes de défaillance rares, là où un classifieur supervisé reste aveugle.

### Health Index — fusion d'indicateurs
L'indice de santé (0–100 %) n'est pas une simple moyenne, mais une fusion pondérée de trois composantes :

- **Score d'anomalie** (40 %) — détection de déviation via l'auto-encodeur
- **Prédiction RUL** (40 %) — quantifie la dégradation anticipée
- **Variations vibratoires** (20 %) — RMS vs baseline, dérive progressive

### Benchmark dynamique de modèles
Cinq architectures sont comparées et conservées. Via l'interface **IA Lab**, le modèle actif d'un dataset se change **à chaud**, sans interruption de service.

### Copilot IA contextuel
Un assistant (LLM Mistral) a accès au contexte temps réel de la flotte et produit des **recommandations actionnables** (action, délai, justification), avec **citation des sources** normatives (RAG).

### Positionnement face aux solutions existantes

- **vs CMMS/EAM** (SAP, Maximo, Infor) — excellents en gestion administrative mais **passifs** : aucune capacité prédictive native.
- **vs monitoring IoT** (Thingworx, Azure IoT Hub) — ingestion et streaming, mais **aucune intelligence de domaine**.
- **vs solutions propriétaires** (Uptake, GE Digital) — prédictives mais **coût de licence élevé** et fermées. PrognoSense est **open-source** et sans lock-in.

---

## 3. Fonctionnalités principales

### Monitoring et diagnostic
Extraction automatique de **45 à 132 indicateurs** selon le dataset :

- **Temporels** — RMS, Kurtosis, Skewness, Peak, Peak-to-Peak, Crest Factor, Shape Factor, Impulse Factor, écart-type.
- **Fréquentiels** — FFT, entropie spectrale, fréquence dominante, énergies par bande (0–1 / 1–3 / 3–5 / 5–6,4 kHz).

Chaque machine reçoit un Health Index continu avec quatre seuils d'action :

- **SAIN** (HI > 70 %) — surveillance standard
- **SURVEILLANCE** (40–70 %) — inspection sous 2–4 semaines
- **ALERTE** (20–40 %) — intervention sous 48 h
- **CRITIQUE** (< 20 %) — arrêt immédiat

### Pronostic (RUL)
Prédiction du nombre de cycles avant défaillance, à partir de données de dégradation réelles (CMAPSS NASA, 21 capteurs), permettant de planifier pièces et interventions.

### Analyse spectrale
Identification des fréquences caractéristiques (BPFO, BPFI, BSF, FTF pour roulements, GMF pour engrenages) avec analyse d'enveloppe (Hilbert). Import d'un spectre externe possible.

### Simulation et injection de défauts
Module de simulation temps réel pour valider la détection et calibrer les seuils sans attendre une panne réelle.

### Multi-datasets
Gestion native de **cinq datasets de référence** + upload et configuration de datasets custom via YAML.

---

## 4. Nouveautés v3 (industrialisation)

Couche d'**industrialisation** et de **confiance** qui rapproche PrognoSense d'une solution de terrain.

### Connectivité industrielle
- **Ingestion universelle** (`POST /api/ingest/signal`) — tout capteur/passerelle pousse un signal réel dans le pipeline complet.
- **Connecteur OPC-UA** et **bridge MQTT**, activables par configuration.
- **Baseline propre à chaque machine** (non supervisé) — l'anomalie est mesurée par rapport à *cette* machine, sans historique de panne.

### Diagnostic normalisé
- **Sévérité ISO 10816 / 20816** — vitesse vibratoire en mm/s et zones A/B/C/D par classe de machine.

### Boucle fermée GMAO
- **Ordres de travail automatiques** sur état critique, **poussés vers la GMAO** (SAP PM / Maximo via webhook).
- **Notifications e-mail** (SMTP) sur alerte critique.

### Indicateurs de fiabilité réels
- **MTBF, MTTR, disponibilité, ROI** — *mesurés* à partir des événements de maintenance saisis (et non estimés).
- **Efficacité prédictive** — précision, rappel, lead-time, et **taux réel de fausses alarmes** validé par l'expert.

### Détection d'anomalie renforcée
- **Ensemble de 3 algorithmes** (Isolation Forest + Local Outlier Factor + Elliptic Envelope) à **vote majoritaire** — moins de fausses alertes.
- En complément de l'auto-encodeur et du baseline par machine.

### Confiance et gouvernance (MLOps)
- **Explicabilité** (SHAP), **calibration** des probabilités, **détection de dérive** (test de Kolmogorov-Smirnov).
- **Versioning des modèles** avec **rollback** en un clic.
- **Journal d'audit** horodaté (traçabilité, esprit ISO 13373).

### Interface
- Page **Audit Trail** — journal de traçabilité horodaté.
- Page **Maintenance** — saisie d'événements, panneaux KPIs réels & ROI, ordres de travail, réentraînement piloté.
- **IA Lab** — onglets Versions Modèle (rollback) et Ensemble d'anomalie.
- **Error boundary** global et **reconnexion WebSocket automatique**.

### Sécurité et scalabilité
- **Authentification JWT** avec rôles (admin / utilisateur), mots de passe chiffrés (bcrypt).
- Architecture **TimescaleDB-ready** — bascule par simple changement de `DATABASE_URL`.

---

## 5. Datasets et défauts couverts

| Dataset | Tâche | Fréq. éch. | Canaux | Fenêtres | Features |
|---|---|---|---|---|---|
| VBL-VA001 | Classification (4 cl.) | 20 kHz | 3 | 400 | 45 |
| CWRU | Classification (10 cl.) | 12 kHz | 1 | 12 627 | 15 |
| Mechanical Faults | Classification (4 cl.) | 25 kHz | 4 | 36 000 | 132 |
| CMAPSS FD001 | Régression (RUL) | cycles | 21 | 17 731 | 126 |
| MCC5-THU | Classification (8 cl.) | 12,8 kHz | 3 | — | CNN 1D |

Modes de défaillance diagnostiqués :

- **Balourd** (déséquilibre rotor)
- **Désalignement** (parallèle / angulaire)
- **Jeu mécanique** (desserrage)
- **Roulement** — bague externe / interne / bille, à 3 niveaux de sévérité (faible / moyen / grave)
- **Engrenage** — pitting, usure, dent cassée, fissurée, manquante, et défauts mixtes
- **Dégradation turbomoteur** — pronostic de durée de vie restante
- **Anomalie inconnue** — tout écart au régime sain (auto-encodeur)

---

## 6. Architecture

### Pile technologique

| Couche | Technologies |
|---|---|
| Backend | FastAPI, Uvicorn, Pydantic |
| Traitement signal | NumPy, SciPy (FFT, Hilbert, filtres) |
| IA | scikit-learn, XGBoost, PyTorch (auto-encodeur, CNN 1D) |
| Persistance | SQLAlchemy + SQLite (WAL), PostgreSQL/TimescaleDB-ready |
| Connectivité | OPC-UA (asyncua), MQTT (paho-mqtt), WebSocket |
| IA générative | API Mistral + recherche TF-IDF (RAG) |
| Sécurité | JWT (python-jose), bcrypt (passlib) |
| Frontend | React, Vite, Recharts |

### Conception
- Architecture en trois couches (frontend / backend / persistance), modules métier isolés.
- **WebSocket** pour le temps réel (pas de polling), avec reconnexion automatique.
- **Registre de modèles** centralisé et **gestionnaire de flotte** en mémoire.
- Fonctionnement **100 % local**, sans dépendance cloud obligatoire.

---

## 7. Performances réelles

Benchmark des modèles, avec **découpage par fichier source** (aucune fuite de données entre apprentissage et test) :

| Dataset | Tâche | Meilleur modèle | Performance |
|---|---|---|---|
| VBL-VA001 | Classification (4 cl.) | XGBoost | **100 %** |
| CWRU | Classification (10 cl.) | XGBoost | **97,6 %** |
| Mechanical Faults | Classification (4 cl.) | MLP | **89,6 %** |
| CMAPSS FD001 | Régression RUL | XGBoost | **MAE 9,61 cycles · R² 0,90** |

---

## 8. Installation

### Prérequis
- Python 3.10+
- Node.js 18+
- Git

### Procédure

```bash
# 1. Cloner le dépôt
git clone <repo>
cd Projet

# 2. Backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r backend/requirements.txt

# 3. Frontend
cd frontend
npm install
cd ..

# 4. Lancer (deux terminaux)
uvicorn backend.main:app --reload --port 8000     # backend
cd frontend && npm run dev                         # frontend
```

- **Dashboard** : `http://localhost:5173`
- **API Docs** : `http://localhost:8000/docs`

### Configuration
- **Copilot IA** : définir `MISTRAL_API_KEY` (clé sur console.mistral.ai).
- **Notifications e-mail** : définir `SMTP_SENDER` et `SMTP_PASSWORD`.
- **GMAO externe** : définir `CMMS_WEBHOOK_URL`.
- **Base PostgreSQL/Timescale** : définir `DATABASE_URL`.

---

## 9. Utilisation

### Workflow type
L'ingénieur ouvre la **Vue Globale** : la flotte est triée par criticité. Un clic sur une machine en alerte lance sa surveillance temps réel ; les courbes montrent la dégradation, et le **Copilot** propose une action datée. L'événement de maintenance est ensuite saisi, alimentant les KPIs de fiabilité, et un **ordre de travail** est généré.

### IA Lab
Comparaison des cinq modèles par dataset, sélection du modèle actif à chaud, suivi de la fiabilité (drift, calibration), explicabilité (SHAP) et gestion des versions (rollback).

---

## 10. Spécifications techniques

### Performance
- Latence de prédiction : < 200 ms (CPU)
- Streaming WebSocket temps réel
- Conçu pour une flotte de plusieurs dizaines à centaines de machines

### Formats et prétraitement
- Entrées : CSV, MAT, TXT, ZIP, YAML custom.
- Prétraitement : rééchantillonnage à 12,8 kHz, normalisation Z-score, fenêtrage glissant (1024 pts, recouvrement 50 %).

### API et intégration
API REST documentée (Swagger) + WebSocket. Exemples :

```bash
# Prédiction
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"dataset":"CWRU","machine_id":"M01","features":[[...]],"rul":45.5}'

# Sélection du modèle actif
curl -X POST "http://localhost:8000/api/model/select?dataset=CWRU&model_name=XGBoost"

# Ingestion d'un signal réel (OPC-UA/MQTT/edge)
curl -X POST http://localhost:8000/api/ingest/signal \
  -H "Content-Type: application/json" \
  -d '{"machine_id":"POMPE_01","signal":[...],"fs":12800,"machine_class":"II"}'
```

---

## 11. Sécurité et conformité

- **Données locales** — pas d'exfiltration ; secrets en variables d'environnement (`.env` non versionné).
- **Authentification JWT** + rôles ; mots de passe chiffrés (bcrypt).
- **Validation Pydantic** de toutes les entrées de l'API.
- **Journal d'audit** complet et horodaté.
- Inspiré des normes **ISO 10816, ISO 13373, ISO 13374**.

---

## 12. Roadmap

### Réalisé (v3)
- ✅ Authentification multi-rôles (JWT + bcrypt)
- ✅ Intégration OPC-UA / MQTT (IIoT natif)
- ✅ Intégration GMAO / ERP (SAP PM, Maximo via webhook)
- ✅ Sévérité normalisée ISO 10816/20816
- ✅ Versioning des modèles + rollback (MLOps)
- ✅ Réentraînement piloté depuis l'UI
- ✅ Copilot RAG ancré sur les normes
- ✅ Indicateurs de fiabilité réels (MTBF/MTTR/dispo/ROI) + taux de fausses alarmes

### À venir
- 🔜 RBAC fin + SSO/LDAP, durcissement IEC 62443
- 🔜 Modèles physics-informed (hybrides physique + données)
- 🔜 Apprentissage fédéré multi-sites
- 🔜 Clustering automatique des anomalies
- 🔜 Application mobile (React Native), export Grafana/Prometheus
- 🔜 Multi-langue (FR / EN / العربية)

---

<div align="center">

**PrognoSense** — *Surveiller. Diagnostiquer. Anticiper. Agir.*

Développé à l'ENSAM-Meknès · Licence MIT

</div>
