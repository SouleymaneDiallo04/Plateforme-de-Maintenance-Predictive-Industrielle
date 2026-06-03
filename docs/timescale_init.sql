-- Initialisation TimescaleDB pour PrognoSense.
-- Exécuté automatiquement au premier démarrage du conteneur.
-- (Les tables elles-mêmes sont créées par l'application via SQLAlchemy ;
--  ce script ne fait qu'activer l'extension. La conversion en hypertable
--  se fait APRÈS le premier démarrage de l'app — voir docs/SCALING.md.)

CREATE EXTENSION IF NOT EXISTS timescaledb;
