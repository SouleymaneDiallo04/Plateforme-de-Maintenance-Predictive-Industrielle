# Passage à l'échelle — TimescaleDB (time-series)

## Pourquoi
SQLite convient à une démo et à quelques dizaines de machines. Pour un parc
réel (centaines de machines échantillonnées en continu), il faut une base
**time-series** : écritures massives, requêtes par fenêtre temporelle,
agrégation rapide, compression et rétention automatiques.

**TimescaleDB** = PostgreSQL + extension time-series. Avantage clé pour ce
projet : **le code ne change pas**. L'application utilise SQLAlchemy ; seule la
variable `DATABASE_URL` change.

## Mise en place (3 étapes)

1. **Lancer la base**
   ```
   docker compose -f docker-compose.timescale.yml up -d
   ```

2. **Pointer l'application dessus** (variable d'environnement) :
   ```
   DATABASE_URL=postgresql://prognosense:prognosense@localhost:5432/prognosense
   ```
   Démarrer le backend → les tables sont créées automatiquement (SQLAlchemy).
   (Le pilote `psycopg2-binary` doit être installé : `pip install psycopg2-binary`.)

3. **Convertir la table d'états en hypertable** (une seule fois, après le 1er démarrage) :
   ```sql
   SELECT create_hypertable('machine_states', 'timestamp', migrate_data => true);
   -- Rétention automatique : garder 90 jours de données brutes
   SELECT add_retention_policy('machine_states', INTERVAL '90 days');
   -- Compression des données anciennes (gain ~10x)
   ALTER TABLE machine_states SET (timescaledb.compress);
   SELECT add_compression_policy('machine_states', INTERVAL '7 days');
   ```

## Lecture agrégée (déjà implémentée côté app)
L'endpoint `GET /api/machine/{id}/history/rollup?bucket=hour` renvoie des
moyennes par tranche de temps (downsampling) au lieu des points bruts.

- Sur SQLite : agrégation via `strftime` (déjà en place).
- Sur TimescaleDB : remplacer par la fonction native, bien plus rapide :
  ```sql
  SELECT time_bucket('1 hour', timestamp) AS bucket,
         avg(health_index), min(health_index), max(health_index), count(*)
  FROM machine_states
  WHERE machine_id = :id AND timestamp >= now() - interval '7 days'
  GROUP BY bucket ORDER BY bucket;
  ```

## Rétention
- Côté app (portable, déjà en place) : `POST /api/admin/retention/purge?keep_days=90`.
- Côté TimescaleDB (recommandé en prod) : `add_retention_policy` (automatique, ci-dessus).

## Résumé
| | SQLite (actuel) | TimescaleDB (prod) |
|---|---|---|
| Volume | démo / dizaines de machines | parc complet |
| Agrégation | `strftime` | `time_bucket` (natif) |
| Rétention | endpoint manuel | policy automatique |
| Compression | non | oui (~10x) |
| Changement de code | — | **aucun** (seul `DATABASE_URL` change) |
