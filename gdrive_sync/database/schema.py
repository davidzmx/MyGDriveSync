"""
SQLite schema definitions for gdrive-sync state storage.
"""

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
-- General configuration / key-value storage
CREATE TABLE IF NOT EXISTS app_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

-- Selective sync folder rules
CREATE TABLE IF NOT EXISTS sync_folders (
    drive_id TEXT PRIMARY KEY,
    rel_path TEXT UNIQUE NOT NULL,
    is_synced INTEGER NOT NULL DEFAULT 1,
    last_scanned REAL DEFAULT 0.0
);

-- Tracked files and folders
CREATE TABLE IF NOT EXISTS sync_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_path TEXT UNIQUE NOT NULL,
    drive_id TEXT,
    item_type TEXT NOT NULL,
    size INTEGER DEFAULT 0,
    mtime_local REAL DEFAULT 0.0,
    mtime_remote TEXT,
    md5_checksum TEXT,
    status TEXT NOT NULL DEFAULT 'synced',
    error_message TEXT,
    parent_drive_id TEXT,
    updated_at REAL NOT NULL
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_sync_items_drive_id ON sync_items(drive_id);
CREATE INDEX IF NOT EXISTS idx_sync_items_status ON sync_items(status);
CREATE INDEX IF NOT EXISTS idx_sync_folders_path ON sync_folders(rel_path);
"""
