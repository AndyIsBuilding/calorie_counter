#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Default database path
DB_PATH="${SCRIPT_DIR}/food_tracker_prod.db"

# Check if a custom path was provided
if [ "$#" -eq 1 ]; then
    DB_PATH="$1"
fi

echo "Running migration on database: ${DB_PATH}"

# Run the migration script
python3 "${SCRIPT_DIR}/migrate_db.py" "${DB_PATH}"

# Check if the migration was successful
if [ $? -eq 0 ]; then
    echo "Migration completed successfully!"
else
    echo "Migration failed!"
    exit 1
fi 