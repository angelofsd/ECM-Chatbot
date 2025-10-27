-- Initialize database with proper authentication
-- This runs automatically via Docker's /docker-entrypoint-initdb.d/

-- Ensure the postgres user password is set correctly
ALTER USER postgres WITH PASSWORD 'postgres';

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE ecm_rag TO postgres;
