#!/bin/bash
set -e

# Insert admin user using environment variables
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    INSERT INTO users (id, name, real_name, is_deleted, is_admin, is_ignore)
    VALUES (
        '$SLACK_ADMIN_ID',
        '$SLACK_ADMIN_NAME',
        '$SLACK_ADMIN_NAME',
        FALSE,
        TRUE,
        FALSE
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        real_name = EXCLUDED.real_name,
        is_admin = TRUE,
        is_deleted = FALSE;
    
    -- Confirm the admin user was created
    SELECT id, name, is_admin FROM users WHERE id = '$SLACK_ADMIN_ID';
EOSQL

echo "Admin user $SLACK_ADMIN_NAME ($SLACK_ADMIN_ID) has been created/updated successfully."