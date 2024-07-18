#!/bin/bash
set -e

# Wait for the database to become available if necessary
#/wait-for-it.sh mongodb:27016 --timeout=30
sleep 5;

# Durchführen der Alembic-Migrationen
#flask db upgrade

# Starten des Hauptprozesses (z.B. uWSGI)
exec "$@"
