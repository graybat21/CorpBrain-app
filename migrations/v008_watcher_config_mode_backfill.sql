-- v008: heal Watcher_Config.mode for databases created before it existed (issue #149)
--
-- Background (the DEC-05 violation this repairs): the `mode` column was added to Watcher_Config
-- by EDITING v001_initial_schema.sql (commit 02abae2), not by shipping a new migration. Because
-- v001 uses `CREATE TABLE IF NOT EXISTS` and db.py gates every migration on `PRAGMA user_version`,
-- a database created before that edit is stuck at:
--     Watcher_Config(workspace_id, is_enabled, debounce_ms, updated_at)   -- no `mode`
-- even though its user_version has since advanced (the real DB observed at user_version=7). Any
-- write to `mode` — WatcherService.update_config on enabling realtime/idle — then raised
--     sqlite3.OperationalError: table Watcher_Config has no column named mode   -> HTTP 500.
-- Fresh databases created after the edit already carry `mode` (from the edited v001), so the two
-- populations have DIVERGENT schemas at the same user_version.
--
-- Why a table REBUILD and not `ALTER TABLE ... ADD COLUMN mode`:
--   * a plain ADD COLUMN succeeds on the old DBs but FAILS on the fresh DBs with
--     "duplicate column name: mode", and db.py runs each migration via executescript() with no
--     way to branch on whether the column exists — SQLite has no `ADD COLUMN IF NOT EXISTS`.
--   * a rebuild whose `INSERT ... SELECT` never references the source `mode` column is safe for
--     BOTH populations: the old table (no mode) and the fresh table (has mode) both expose
--     {workspace_id, is_enabled, debounce_ms, updated_at}, so one statement converges them to the
--     single canonical schema below. This mirrors the documented ALTER-TABLE procedure already
--     used by v004.
--
-- Why NOT edit v001 to remove the stray `mode` line: DEC-05 makes shipped migrations immutable —
-- re-editing v001 is what caused this bug. A fresh DB's `mode` from v001 is harmless: this rebuild
-- reconstructs Watcher_Config identically for everyone, so the end state does not depend on whether
-- v001 supplied the column.
--
-- Cost, stated rather than hidden: because the SELECT cannot read a column that may not exist, a
-- fresh DB's existing `mode` value is not carried across verbatim — it is re-derived from
-- `is_enabled` to preserve the service invariant (`is_enabled = 1 <=> mode in {realtime, idle}`;
-- WatcherService.update_config). An enabled watcher that was set to 'idle' is reset to 'realtime'
-- (both enabled, so the watcher keeps running); a disabled one becomes 'manual'. `mode` was only
-- writable for the ~4 days between the v001 edit and this migration, so the affected set is
-- effectively dev/test databases, and the alternative — a migration that crashes on fresh DBs —
-- is strictly worse.

PRAGMA foreign_keys = OFF;

CREATE TABLE Watcher_Config_v008 (
    workspace_id TEXT PRIMARY KEY REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    debounce_ms INTEGER NOT NULL DEFAULT 500,
    mode TEXT NOT NULL DEFAULT 'realtime',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- `mode` is listed explicitly and filled from is_enabled, so this SELECT never reads a source
-- `mode` column — the one property that makes the statement valid on both the old (no mode) and
-- the fresh (has mode) schema.
INSERT INTO Watcher_Config_v008 (workspace_id, is_enabled, debounce_ms, mode, updated_at)
SELECT
    workspace_id,
    is_enabled,
    debounce_ms,
    CASE WHEN is_enabled = 1 THEN 'realtime' ELSE 'manual' END,
    updated_at
FROM Watcher_Config;

DROP TABLE Watcher_Config;

-- Nothing references Watcher_Config (it is a leaf child of Workspace_Meta), so renaming the new
-- table triggers no FK-clause rewrites in other tables.
ALTER TABLE Watcher_Config_v008 RENAME TO Watcher_Config;

PRAGMA foreign_keys = ON;
