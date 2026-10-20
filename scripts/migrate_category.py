"""
SplitSmart Database Schema Migration:
Ensures `category` column exists on `groups` table.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from db import get_db_cursor

def run_migration():
    with get_db_cursor() as (cur, conn):
        cur.execute("SHOW COLUMNS FROM `groups` LIKE 'category'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE `groups` ADD COLUMN category VARCHAR(50) NOT NULL DEFAULT 'Other' AFTER description")
            conn.commit()
            print("Successfully added 'category' column to `groups` table.")
        else:
            print("'category' column already exists on `groups` table.")

if __name__ == "__main__":
    run_migration()
