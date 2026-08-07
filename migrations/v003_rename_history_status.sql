-- v003: Add status column to Rename_History (issue #90)
--
-- Background: RenameQueryService.get_pending_rename_diff queries Rename_History.status, but the
-- column never existed (v001 schema omitted it). RenameService.generate_rename_diff writes
-- {"status": "pending"} to a dict that is never persisted, and RenameService.apply_rename_diff
-- returns {"status": "applied"|"multi_status"} transiently. No row ever carries a status value.
--
-- This migration adds the column with a default so existing rows become "pending" (they were
-- generated but never applied). Future writes will set status explicitly at INSERT and UPDATE.
--
-- DEC-05: this SQL lives in a standalone migration file, applied once via PRAGMA user_version.

ALTER TABLE Rename_History ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
