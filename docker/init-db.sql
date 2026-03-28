-- ---------------------------------------------------------------
-- regulatory-agent-kit — Database Initialization
-- ---------------------------------------------------------------
-- This script runs once when the PostgreSQL container is first
-- created. The 'rak' database is created automatically by the
-- POSTGRES_DB environment variable in docker-compose.yml.
-- ---------------------------------------------------------------

-- Create additional databases for Temporal and MLflow
CREATE DATABASE temporal;
CREATE DATABASE mlflow;

-- ---------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------
-- rak_admin: full DDL privileges on the rak schema (used by Alembic migrations)
-- rak_app:   DML-only privileges on the rak schema (used by application)
-- ---------------------------------------------------------------

CREATE ROLE rak_admin WITH LOGIN PASSWORD 'rak_admin_dev_password';
CREATE ROLE rak_app WITH LOGIN PASSWORD 'rak_app_dev_password';

-- Grant rak_admin full access to rak database
GRANT ALL PRIVILEGES ON DATABASE rak TO rak_admin;

-- Grant rak_app connect and usage on rak database
GRANT CONNECT ON DATABASE rak TO rak_app;

-- Switch to rak database to set up schema-level permissions
\connect rak

-- Create the rak schema (Alembic will manage tables within it)
CREATE SCHEMA IF NOT EXISTS rak;

-- rak_admin owns the schema and can create/alter/drop objects
GRANT ALL PRIVILEGES ON SCHEMA rak TO rak_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA rak GRANT ALL ON TABLES TO rak_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA rak GRANT ALL ON SEQUENCES TO rak_admin;

-- rak_app can read/write data but not alter schema
GRANT USAGE ON SCHEMA rak TO rak_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA rak GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rak_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA rak GRANT USAGE, SELECT ON SEQUENCES TO rak_app;
