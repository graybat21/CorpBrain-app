-- Initial Schema for CorpBrain (v001)
-- Spec: SRS v1.1 §6.2, DEC-01~DEC-22 compliant

CREATE TABLE IF NOT EXISTS Workspace_Meta (
    workspace_id TEXT PRIMARY KEY,
    workspace_name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS File_Meta (
    file_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    current_path TEXT NOT NULL,
    original_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    last_modified REAL NOT NULL,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    importance_score INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(workspace_id, current_path)
);

CREATE INDEX IF NOT EXISTS idx_file_meta_current_path ON File_Meta(current_path);
CREATE INDEX IF NOT EXISTS idx_file_meta_ws_status ON File_Meta(workspace_id, parse_status);

CREATE TABLE IF NOT EXISTS Wiki_Content (
    wiki_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    folder_1depth TEXT NOT NULL,
    markdown_content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(workspace_id, folder_1depth)
);

CREATE TABLE IF NOT EXISTS Rename_History (
    history_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    old_paths TEXT NOT NULL,
    new_paths TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS Analytics_Log (
    log_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    file_id TEXT REFERENCES File_Meta(file_id) ON DELETE SET NULL,
    wiki_id TEXT REFERENCES Wiki_Content(wiki_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_analytics_file_id ON Analytics_Log(file_id);
CREATE INDEX IF NOT EXISTS idx_analytics_wiki_id ON Analytics_Log(wiki_id);

CREATE TABLE IF NOT EXISTS Watcher_Config (
    workspace_id TEXT PRIMARY KEY REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    debounce_ms INTEGER NOT NULL DEFAULT 500,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS App_Config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS Async_Task (
    task_id TEXT PRIMARY KEY,
    workspace_id TEXT REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    processed_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_async_task_status ON Async_Task(status);
CREATE INDEX IF NOT EXISTS idx_async_task_ws_type ON Async_Task(workspace_id, task_type);
