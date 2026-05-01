#!/bin/bash

# PostgreSQL initialization script for trading system
# This script creates the database and extensions

set -e

echo "Initializing PostgreSQL database..."

# Create extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOF
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create trading schema
CREATE SCHEMA IF NOT EXISTS trading;

-- Set search path
ALTER DATABASE "$POSTGRES_DB" SET search_path TO trading, public;

EOF

echo "PostgreSQL database initialized successfully!"
