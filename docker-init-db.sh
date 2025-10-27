#!/bin/bash
# Wait for PostgreSQL to be ready
until pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
done

# Update pg_hba.conf with md5 authentication
psql -U postgres -d postgres << SQL
ALTER USER postgres WITH PASSWORD 'postgres';
SQL
