#!/bin/sh
# Taki - connect an online database (Supabase, Neon, ...):  sh connect-database.sh
cd "$(dirname "$0")" || exit 1
exec sh start.sh setup-db
