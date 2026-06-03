<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-19-61dafb?style=for-the-badge&logo=react&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-Signal-8CAAE6?style=for-the-badge&logo=scipy)
![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-00ACC1?style=for-the-badge&logo=websocket)
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
8. [Cas d'usage industriels](#8-cas-dusage-industriels)
9. [Installation](#9-installation)
10. [Utilisation](#10-utilisation)
11. [Spécifications techniques](#11-spécifications-techniques)
12. [Sécurité et conformité](#12-sécurité-et-conformité)
13. [Roadmap](#13-roadmap)

---

## 1. Vue d'ensemble

PrognoSense est une **plateforme logicielle innovante** qui apporte une transformation fondamentale à la maintenance industrielle. En combinant l'analyse avancée de signaux vibratoires avec des modèles d'intelligence artificielle sophistiqués, elle détecte les dégradations d'équipements **des mois à l'avance**, permettant aux organisations de basculer vers une **maintenance véritablement prédictive** basée sur l'état réel de chaque machine.

Cette plateforme adresse un enjeu critique de l'industrie manufacturière : la réduction des temps d'arrêt non planifiés qui représentent des **pertes économiques substantielles**. PrognoSense fournit une **solution globale** de surveillance prédictive accessible aux ingénieurs de maintenance **sans expertise en data science**.

---

## 2. Différenciateurs

PrognoSense ne se positionne pas comme un simple outil de monitoring. Elle représente un **changement de paradigme** dans la façon dont l'industrie approche la maintenance des équipements.

### Détection d'anomalies non supervisée
Contrairement aux approches traditionnelles basées sur la classification supervisée, PrognoSense intègre un **auto-encodeur PyTorch entraîné exclusivement sur des données de machines saines**. Cette approche permet de **détecter des défauts inconnus et inattendus**, jamais vus dans les données historiques.

C'est particulièrement critique car **30 à 40 % des pannes industrielles** sont dues à des modes de défaillance imprévisibles ou rares. Là où les solutions concurrentes restent limitées aux défauts qu'elles ont appris à reconnaître, PrognoSense offre une **couche de protection supplémentaire** pour l'inattendu : quand une anomalie apparaît, l'erreur de reconstruction augmente brusquement, signalant une déviation du régime normal. C'est comme avoir un **expert vibration qui surveille en continu**.

### Health Index — fusion intelligente d'indicateurs
Le Health Index n'est pas une simple moyenne, mais une **fusion sophistiquée** de trois composantes complémentaires :

- **Score d'anomalie** (40 %) — détection de déviation via l'auto-encodeur, capte l'imprévu
- **Prédiction RUL** (40 %) — issue de modèles régressifs, quantifie la dégradation anticipée
- **Variations vibratoires** (20 %) — RMS vs baseline, capture la dérive progressive

Cette approche **pondérée et adaptative** permet une évaluation holistique de l'état de santé qui dépasse les outils point-solution existants. Les poids peuvent être ajustés par secteur industriel.

### Benchmark dynamique de modèles
Plutôt que de forcer un unique modèle pour tous les cas d'usage, PrognoSense maintient un **benchmark continu** de cinq architectures. Via l'interface **IA Lab**, les responsables techniques visualisent les performances et **basculent instantanément** vers le meilleur modèle, sans interruption de service.

### Copilot IA contextuel
L'intégration du LLM **Mistral** n'est pas cosmétique. Le **Copilot** a accès au contexte complet de la flotte en temps réel et génère des **recommandations opérationnelles structurées** (actions concrètes, délais, justifications), en **citant ses sources** normatives (RAG). Aucune solution concurrente ne combine suivi prédictif et IA générative de cette manière.

### Positionnement face aux solutions existantes
- **vs CMMS/EAM traditionnelles** (SAP, Maximo, Infor) — excellentes en gestion administrative mais **passives** quant à la prédiction de pannes : aucune capacité prédictive native.
- **vs outils de monitoring IoT** (Thingworx, Azure IoT Hub) — assurent l'ingestion et le streaming, mais **aucune intelligence prédictive de domaine** : elles collectent, PrognoSense analyse avec une expertise mécanique intégrée.
- **vs solutions propriétaires** (Uptake, C3M, GE Digital) — capacités prédictives à **coût de licence très élevé** (6 chiffres/an). PrognoSense est **open-source**, déployable immédiatement et personnalisable. **Pas de lock-in.**

---

## 3. Fonctionnalités principales

### Monitoring et diagnostic avancé
PrognoSense transforme des **signaux vibratoires bruts en intelligence actionnelle**. La plateforme capture en continu les vibrations et en extrait automatiquement **45 à 132 indicateurs** selon le dataset.

- **Indicateurs temporels** — RMS, Kurtosis, Skewness, Peak, Peak-to-Peak, Crest Factor, Shape Factor, Impulse Factor, écart-type.
- **Indicateurs fréquentiels** — FFT, entropie spectrale, fréquence dominante, énergie par bande (0–1, 1–3, 3–5, 5–6,4 kHz), couvrant les signatures de défaillance typiques.

Chaque machine reçoit un **Health Index continu de 0 à 100 %** synthétisant son état de santé, avec quatre seuils sémantiques d'intervention :

- **SAIN** (HI > 70 %) — surveillance standard
- **SURVEILLANCE** (40–70 %) — inspection dans 2–4 semaines
- **ALERTE** (20–40 %) — intervention requise sous 48 h
- **CRITIQUE** (< 20 %) — arrêt et intervention immédiate

Ce système est **contextuellement intelligent** : si une machine présente une anomalie mais une RUL élevée, le Health Index le reflète — une nuance qui manque aux seuillages simples.

### Prédiction de durée de vie restante (RUL)
Le module RUL prédit le **nombre de cycles ou d'heures avant défaillance**. Basé sur des données de dégradation réelles (CMAPSS NASA, 21 capteurs), il capture les **patterns non linéaires** que les approches simples ne modélisent pas. Pour turbines ou réducteurs, cela permet un **ordonnancement optimisé** : planifier les pièces de rechange, coordonner les maintenances, minimiser les ruptures de production.

### Analyse spectrale et diagnostic pointu
La FFT identifie les fréquences caractéristiques de défaillance : BPFO pour roulements, GMF pour engrenages, fréquences de rotation pour turbines. L'interface permet d'**importer un signal brut et d'obtenir instantanément** l'analyse, avec zones de danger, fiches techniques et recommandations Copilot — un **diagnostic au niveau d'un expert**, accessible via une interface graphique.

### Simulation et injection de défauts
Pour valider la détection et tester les seuils avant déploiement, PrognoSense inclut un **module de simulation complet**. Injecter synthétiquement des défauts permet de **calibrer les seuils** à la sensibilité désirée sans attendre une panne réelle.

### Flexibilité multi-datasets
PrognoSense gère nativement **cinq datasets de référence** (VBL-VA001, CWRU, CMAPSS, MCC5-THU, Mechanical Faults) et permet aussi l'**upload et la configuration de datasets custom** via interface YAML. Ajouter un nouveau domaine prend **quelques minutes**.

---

## 4. Nouveautés v3 (industrialisation)

Couche d'**industrialisation** et de **confiance** qui rapproche PrognoSense d'une véritable solution de terrain, ouverte et explicable.

### Connectivité industrielle
- **Ingestion universelle** (`POST /api/ingest/signal`) — tout capteur ou passerelle pousse un signal réel dans le pipeline complet (features → ISO → anomalie → diagnostic → santé → persistance).
- **Connecteur OPC-UA** (standard de l'automatisme) et **bridge MQTT** (IIoT), activables par configuration — connectables au parc existant.
- **Baseline propre à chaque machine** (non supervisé) — l'anomalie est mesurée par rapport à *cette* machine, sans aucun historique de panne.

### Diagnostic normalisé
- **Sévérité ISO 10816 / 20816** — vitesse vibratoire en **mm/s** et **zones A/B/C/D** par classe de machine, pour un diagnostic comparable, normalisé et défendable.

### Boucle fermée GMAO
- **Ordres de travail automatiques** créés sur état critique, **poussés vers la GMAO** (SAP PM / Maximo via webhook).
- **Notifications e-mail** (SMTP) sur alerte critique.

### Indicateurs de fiabilité réels
- **MTBF, MTTR, disponibilité, ROI** — *mesurés* à partir des événements de maintenance saisis (et non estimés).
- **Efficacité prédictive** — précision, rappel, lead-time, et **taux réel de fausses alarmes** validé par l'expert (human-in-the-loop).

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
- Architecture **TimescaleDB-ready** — bascule par simple changement de `DATABASE_URL`, sans toucher au code.

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

### Conception modulaire et scalable
PrognoSense est architecturée en **trois couches** (frontend / backend / persistance), avec des modules métier isolés — chacun peut être **maintenu, testé ou remplacé indépendamment**. L'utilisation de **WebSocket** pour le streaming temps réel (plutôt que du polling) garantit la réactivité sans surcharge serveur, et un **caching intelligent** maintient une faible latence de prédiction.

### Modèles d'intelligence artificielle
Le portefeuille couvre le spectre des architectures classiques : **XGBoost** (équilibre optimal en classification), **Random Forest** (robustesse au bruit), **Huber Regressor** (RUL robuste aux outliers), **CNN 1D** (signaux bruts d'engrenage sans extraction manuelle) et **auto-encodeur PyTorch** (détection d'anomalie générique). Cette diversité n'est pas du sur-dimensionnement : **différents problèmes demandent différentes architectures**, et PrognoSense permet de sélectionner l'approche optimale par dataset.

### Déploiement et opérabilité
Tout ce que PrognoSense fait, elle le fait **localement, sans dépendance cloud obligatoire**. Les données restent dans votre infrastructure, SQLite assure la persistance, et les modèles sont préchargés en mémoire. **Même sans le LLM Mistral, la plateforme reste pleinement fonctionnelle** (seul le Copilot est désactivé).

---

## 7. Performances réelles

Benchmark des modèles, avec **découpage par fichier source** (aucune fuite de données entre apprentissage et test) :

| Dataset | Tâche | Meilleur modèle | Performance |
|---|---|---|---|
| VBL-VA001 | Classification (4 cl.) | XGBoost | **100 %** |
| CWRU | Classification (10 cl.) | XGBoost | **97,6 %** |
| Mechanical Faults | Classification (4 cl.) | MLP | **89,6 %** |
| CMAPSS FD001 | Régression RUL | XGBoost | **MAE 9,61 cycles · R² 0,90** |

L'analyse montre qu'**aucun modèle n'est universellement supérieur** : XGBoost domine sur les roulements (CWRU) et le pronostic (CMAPSS), tandis que le MLP s'impose nettement sur Mechanical Faults (89,6 % contre 75 % pour les arbres) grâce aux interactions non linéaires entre 132 features.

---

## 8. Cas d'usage industriels

### Maintenance prédictive de machines tournantes
Dans une usine, les roulements sont un **point critique** : une défaillance surprise coûte des centaines de milliers d'euros. PrognoSense **détecte les anomalies de roulement 1 à 6 mois avant la panne**.

Workflow concret : l'auto-encodeur détecte une micro-anomalie → le HI descend à 65 % (surveillance) → semaine 4, HI à 45 % (alerte jaune, inspection) → semaine 6, HI à 25 % (alerte rouge, 48 h) → intervention planifiée **avant** la panne.

> **Comparaison** : une panne surprise coûte ~250 k€ ; l'intervention planifiée avec PrognoSense ~15 k€.

### Gestion de flotte de moteurs
Avec PrognoSense, on visualise **100+ moteurs en temps réel** sur un seul tableau de bord. Ceux approchant la fin de vie sont signalés, ceux montrant une dégradation accélérée sont remontés pour expertise, et ceux restant sains suivent une surveillance de routine : c'est une **maintenance différenciée, pilotée par les données**.

### Optimisation des coûts d'exploitation
Pour une aciérie de 500 machines : avant PrognoSense, maintenance calendaire (intervention tous les 6 mois ≈ 83/mois) ; après, seules 60 % requièrent une intervention (≈ 50/mois) et 40 % attendent 9–12 mois.

> **Résultats typiques visés** : coûts de maintenance **−15 à −25 %**, pannes non planifiées **−40 %**, disponibilité **+8 à +12 %**.

---

## 9. Installation

### Prérequis
- Python 3.10+
- Node.js 18+
- Git
- (Optionnel) CUDA 12+ pour le support GPU

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
- **API Docs (Swagger)** : `http://localhost:8000/docs`

### Configuration
- **Copilot IA** : définir `MISTRAL_API_KEY` (clé sur console.mistral.ai).
- **Notifications e-mail** : définir `SMTP_SENDER` et `SMTP_PASSWORD`.
- **GMAO externe** : définir `CMMS_WEBHOOK_URL`.
- **Base PostgreSQL/Timescale** : définir `DATABASE_URL`.
- **Seuils personnalisés** : via la section Configuration du dashboard.

---

## 10. Utilisation

### Workflow type d'un ingénieur de maintenance
Un ingénieur ouvre la **Vue Globale** le matin : 20 machines, 16 SAINES, 3 en SURVEILLANCE, 1 en ALERTE. Il clique sur l'alerte → les courbes montrent une élévation progressive du RMS et une dégradation accélérée depuis 3 jours. Le **Copilot recommande** : *« Roulement usé probable (87 % de confiance). Intervenir sous 48 h. Pièce SKF-6309 en stock. »*

L'intervention a lieu jeudi, 2 jours avant la panne. Après remplacement, les métriques reviennent au niveau baseline, la machine repasse SAINE, et l'événement est **journalisé automatiquement**.

### Optimisation des modèles via IA Lab
On évalue les cinq modèles sur CWRU, on compare exactitude et latence, puis on **sélectionne le meilleur modèle** : instantanément, tous les signaux du dataset l'utilisent — sans redéploiement ni interruption.

---

## 11. Spécifications techniques

### Performance
- **Latence de prédiction** — < 50 ms (GPU) / < 200 ms (CPU)
- **Streaming WebSocket** — temps réel, plusieurs mises à jour par seconde et par machine
- **Scalabilité** — plusieurs dizaines à centaines de machines
- **Mémoire** — < 2 Go (datasets + modèles)
- **Calcul FFT** — quelques millisecondes

### Formats et prétraitement
- **Entrées** — CSV (VBL, MCC5), MAT (CWRU), TXT (CMAPSS), ZIP, YAML custom.
- **Prétraitement** — rééchantillonnage à 12,8 kHz, normalisation Z-score, fenêtrage glissant (1024 points, recouvrement 50 %).

### API et intégration
API REST documentée (Swagger) + WebSocket, avec support CORS. Exemples :

```bash
# Prédiction
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"dataset":"CWRU","machine_id":"M01","features":[[...]],"rul":45.5}'

# Sélection du modèle actif
curl -X POST "http://localhost:8000/api/model/select?dataset=CWRU&model_name=XGBoost"

# Ingestion d'un signal réel (edge / OPC-UA / MQTT)
curl -X POST http://localhost:8000/api/ingest/signal \
  -H "Content-Type: application/json" \
  -d '{"machine_id":"POMPE_01","signal":[...],"fs":12800,"machine_class":"II"}'
```

```javascript
// Surveillance temps réel via WebSocket
const ws = new WebSocket('ws://localhost:8000/api/ws/simulation');
ws.send(JSON.stringify({ action: 'play' }));
ws.send(JSON.stringify({ action: 'set_machine', machine_id: 'M02', dataset: 'CWRU' }));
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  console.log(`HI=${msg.health_index}%, RUL=${msg.rul_pred}`);
};
```

---

## 12. Sécurité et conformité

- **Données locales** — pas d'exfiltration ; secrets en variables d'environnement (`.env` non versionné).
- **Authentification JWT** + rôles ; mots de passe chiffrés (bcrypt).
- **Validation Pydantic** de toutes les entrées de l'API (prévention des injections).
- **Journal d'audit** complet et horodaté pour la traçabilité.
- Inspiré des normes **ISO 10816/20816, ISO 13373 et ISO 13374**.

---

## 13. Roadmap

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
- 🔜 RBAC fin + SSO/LDAP, durcissement cybersécurité IEC 62443
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
