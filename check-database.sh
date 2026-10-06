#!/bin/sh
# Taki - show which database is in use and test that it answers:  sh check-database.sh
cd "$(dirname "$0")" || exit 1
exec sh start.sh check-db
