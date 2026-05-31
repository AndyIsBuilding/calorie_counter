#!/usr/bin/env python3
import sqlite3
import os
import sys

def migrate_database(db_path):
    """
    Migrate the database to the latest schema.
    
    This script adds:
    1. protein_goal column to daily_summary table
    2. calorie_goal and protein_goal columns to users table
    3. weight_goal and weight_unit columns to users table
    4. weight_logs table
    """
    print(f"Starting migration of database at {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Start a transaction
    c.execute("BEGIN TRANSACTION")
    
    try:
        # 1. Add protein_goal column to daily_summary if it doesn't exist
        try:
            c.execute("SELECT protein_goal FROM daily_summary LIMIT 1")
            print("protein_goal column already exists in daily_summary table")
        except sqlite3.OperationalError:
            print("Adding protein_goal column to daily_summary table")
            c.execute("ALTER TABLE daily_summary ADD COLUMN protein_goal INTEGER DEFAULT 100")
        
        # 2. Add calorie_goal and protein_goal columns to users table if they don't exist
        try:
            c.execute("SELECT calorie_goal FROM users LIMIT 1")
            print("calorie_goal column already exists in users table")
        except sqlite3.OperationalError:
            print("Adding calorie_goal column to users table")
            c.execute("ALTER TABLE users ADD COLUMN calorie_goal INTEGER DEFAULT 2000")
        
        try:
            c.execute("SELECT protein_goal FROM users LIMIT 1")
            print("protein_goal column already exists in users table")
        except sqlite3.OperationalError:
            print("Adding protein_goal column to users table")
            c.execute("ALTER TABLE users ADD COLUMN protein_goal INTEGER DEFAULT 100")
        
        # 3. Add weight_goal column to users table if it doesn't exist
        try:
            c.execute("SELECT weight_goal FROM users LIMIT 1")
            print("weight_goal column already exists in users table")
        except sqlite3.OperationalError:
            print("Adding weight_goal column to users table")
            c.execute("ALTER TABLE users ADD COLUMN weight_goal REAL DEFAULT NULL")
        
        # 4. Add weight_unit column to users table if it doesn't exist
        try:
            c.execute("SELECT weight_unit FROM users LIMIT 1")
            print("weight_unit column already exists in users table")
        except sqlite3.OperationalError:
            print("Adding weight_unit column to users table")
            c.execute("ALTER TABLE users ADD COLUMN weight_unit INTEGER DEFAULT 0")
        
        # 5. Create weight_logs table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS weight_logs
                     (id INTEGER PRIMARY KEY, date TEXT, weight REAL, user_id INTEGER,
                      FOREIGN KEY(user_id) REFERENCES users(id))''')
        print("Created weight_logs table if it didn't exist")

        # 6. Create poker_session_appearances table (permanent per-occupancy history)
        #    and backfill it from already-ended sessions so existing history still
        #    displays. Lifetime totals were already rolled up under the old code,
        #    so the backfill copies stats for display ONLY (no re-rollup).
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='poker_session_players'")
        has_poker = c.fetchone() is not None

        c.execute("""CREATE TABLE IF NOT EXISTS poker_session_appearances
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      session_id INTEGER NOT NULL,
                      seat_number INTEGER NOT NULL,
                      player_id INTEGER,
                      player_display_name TEXT NOT NULL,
                      session_hands INTEGER DEFAULT 0,
                      session_vpip INTEGER DEFAULT 0,
                      session_pfr INTEGER DEFAULT 0,
                      joined_at TEXT,
                      left_at TEXT,
                      FOREIGN KEY (session_id) REFERENCES poker_sessions(id),
                      FOREIGN KEY (player_id) REFERENCES poker_players(id))""")
        print("Created poker_session_appearances table if it didn't exist")

        # 7. Add joined_at columns (when a player sat down) to both poker tables.
        #    Older databases created the tables before this column existed.
        for table in ("poker_session_players", "poker_session_appearances"):
            try:
                c.execute(f"SELECT joined_at FROM {table} LIMIT 1")
                print(f"joined_at column already exists in {table}")
            except sqlite3.OperationalError:
                print(f"Adding joined_at column to {table}")
                c.execute(f"ALTER TABLE {table} ADD COLUMN joined_at TEXT")

        # Backfill only if the archive is empty (idempotent) and poker tables exist
        c.execute("SELECT COUNT(*) FROM poker_session_appearances")
        already_backfilled = c.fetchone()[0] > 0

        if has_poker and not already_backfilled:
            c.execute("""INSERT INTO poker_session_appearances
                            (session_id, seat_number, player_id, player_display_name,
                             session_hands, session_vpip, session_pfr, joined_at, left_at)
                         SELECT psp.session_id, psp.seat_number, psp.player_id,
                                psp.player_display_name, psp.session_hands,
                                psp.session_vpip, psp.session_pfr, ps.created_at, ps.ended_at
                         FROM poker_session_players psp
                         JOIN poker_sessions ps ON psp.session_id = ps.id
                         WHERE ps.is_active = 0 AND psp.session_hands > 0""")
            print(f"Backfilled {c.rowcount} appearance(s) from ended sessions")
        else:
            print("Skipped appearances backfill (already populated or no poker data)")

        # 7b. Add is_hero column to poker_players ("this player is me").
        if has_poker:
            try:
                c.execute("SELECT is_hero FROM poker_players LIMIT 1")
                print("is_hero column already exists in poker_players")
            except sqlite3.OperationalError:
                print("Adding is_hero column to poker_players")
                c.execute("ALTER TABLE poker_players ADD COLUMN is_hero INTEGER DEFAULT 0")

        # 8. Create poker_hands table (permanent raw hand history). No backfill
        #    is possible: under the old code each hand's actions were deleted on
        #    completion, so only hands recorded from now on will be stored.
        c.execute("""CREATE TABLE IF NOT EXISTS poker_hands
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      session_id INTEGER NOT NULL,
                      hand_number INTEGER,
                      button_position INTEGER,
                      has_btn_straddle INTEGER DEFAULT 0,
                      has_utg_straddle INTEGER DEFAULT 0,
                      dealt_in TEXT,
                      actions TEXT,
                      created_at TEXT NOT NULL,
                      FOREIGN KEY (session_id) REFERENCES poker_sessions(id))""")
        print("Created poker_hands table if it didn't exist")

        # Backfill joined_at for any existing rows that lack it, using the
        # table session's start time as a best-guess for the player's start.
        if has_poker:
            c.execute("""UPDATE poker_session_appearances
                         SET joined_at = (SELECT created_at FROM poker_sessions
                                          WHERE id = poker_session_appearances.session_id)
                         WHERE joined_at IS NULL""")
            c.execute("""UPDATE poker_session_players
                         SET joined_at = (SELECT created_at FROM poker_sessions
                                          WHERE id = poker_session_players.session_id)
                         WHERE joined_at IS NULL""")
            print("Backfilled joined_at where missing")

        # Commit the transaction
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        # Rollback in case of error
        conn.rollback()
        print(f"Error during migration: {e}")
        sys.exit(1)
    finally:
        # Close the connection
        conn.close()

if __name__ == "__main__":
    # Get the database path from command line argument or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default path for PythonAnywhere
        db_path = os.getenv('DB_PATH', 'food_tracker.db')
    
    migrate_database(db_path)
    print(f"Migration script completed for {db_path}") 