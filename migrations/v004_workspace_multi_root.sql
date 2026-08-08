-- v004: multi-folder workspace merging (issue #105)
--
-- "2개 이상 로컬 폴더 병합" is WS-CMD-01's own title and a PRD core feature, but v001 gave
-- Workspace_Meta a single `root_path TEXT NOT NULL UNIQUE` column. The service validated every
-- element of `root_paths` and then stored `validated_paths[0]`, so the remaining folders were
-- dropped with no error and no warning — their files never reached File_Meta.
--
-- Normalised child table rather than a `root_paths` JSON TEXT column:
--   * a JSON blob cannot carry UNIQUE(workspace_id, root_path), so the same folder could be
--     registered twice under one workspace and every file in it would be scanned twice;
--   * DEC-05 keeps SQL inside Repositories, and a child table is queried there with a plain
--     JOIN, whereas JSON would push list parsing into the Repository's row→DTO conversion;
--   * ON DELETE CASCADE (issue #105's own requirement) only exists for a real FK.
--
-- `Workspace_Meta.root_path` is DROPPED rather than kept as "the primary root". Keeping it
-- would leave two sources of truth for root #1 — exactly the drift DEC-09 forbids for vectors,
-- and the reason this bug survived a green test suite: a reader could satisfy itself from the
-- column and never notice the table.

CREATE TABLE IF NOT EXISTS Workspace_Root (
    root_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    root_path TEXT NOT NULL,
    -- Preserves the order the user picked the folders in, so the UI lists them back the same
    -- way. rowid would happen to match today but is not a documented ordering.
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(workspace_id, root_path)
);

CREATE INDEX IF NOT EXISTS idx_workspace_root_ws ON Workspace_Root(workspace_id, sort_order);

-- AC S3: carry every existing v001 root across before the column disappears.
--
-- Not re-runnable, and cannot be: the DROP below removes the column this SELECT reads. That is
-- the same property every migration here has — db.py gates on `PRAGMA user_version` and only a
-- crash between executescript's implicit commit and the version bump could re-enter it, which
-- would need manual repair regardless of what this file does. INSERT OR IGNORE is here for the
-- UNIQUE(workspace_id, root_path) constraint, not for replay.
-- root_id reuses workspace_id for the one legacy root. SQLite has no uuid4(), and
-- randomblob() would mint a different value on each run, defeating the idempotency the
-- UNIQUE clause relies on. workspace_id is already a DEC-11 UUID (36-char hyphenated
-- lowercase) and is unique, so it is unique here too — a legacy workspace has exactly one
-- root, so there is no second row to collide with. Roots created after this migration get
-- their own uuid4() from WorkspaceRepository.
INSERT OR IGNORE INTO Workspace_Root (root_id, workspace_id, root_path, sort_order)
SELECT workspace_id, workspace_id, root_path, 0 FROM Workspace_Meta;

-- SQLite cannot DROP a UNIQUE NOT NULL column in place, so rebuild the table following the
-- documented ALTER-TABLE procedure: build the replacement under a temporary name, copy, drop
-- the original, then rename.
--
-- Renaming the *original* out of the way first does not work: SQLite rewrites the FK clauses of
-- every child table to follow the rename, so File_Meta and friends would end up referencing
-- Workspace_Meta_v001 and lose their parent when it was dropped. (`PRAGMA legacy_alter_table`
-- does not suppress that here — it is not settable from inside executescript's implicit
-- statement batch.) Renaming the *new* table is safe because nothing references its temp name.
--
-- foreign_keys must be OFF for the DROP: with it on, dropping the parent counts as deleting
-- every row, which trips the child constraints on a populated database. db.py re-enables it on
-- every connection (DEC-05), and this migration runs in autocommit where the pragma is honoured.
PRAGMA foreign_keys = OFF;

CREATE TABLE Workspace_Meta_v004 (
    workspace_id TEXT PRIMARY KEY,
    workspace_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

INSERT INTO Workspace_Meta_v004 (workspace_id, workspace_name, created_at, updated_at)
SELECT workspace_id, workspace_name, created_at, updated_at FROM Workspace_Meta;

DROP TABLE Workspace_Meta;

ALTER TABLE Workspace_Meta_v004 RENAME TO Workspace_Meta;

PRAGMA foreign_keys = ON;
