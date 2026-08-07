-- v002: Async_Task.result_json
--
-- DEC-04 turns every long-running command into 202 + task_id, which means a task's outcome
-- has to be retrievable after the response is long gone. Two requirements need it:
--
--   * DEC-16 / DEC-03 — a partially failed batch must surface `data.failed[]`. Once
--     rename_apply returns 202 the per-file failure list has no other home; dropping it would
--     leave the user believing every file was renamed.
--   * DEC-13 — SRS §6.3.2 names `Async_Task.result_json.provision_mode` explicitly. The
--     column was specified there and simply missing from v001.
--
-- TEXT holding JSON rather than a normalised child table: the payload shape differs per
-- task_type (a failure list vs a provisioning mode) and nothing queries inside it — it is read
-- whole, by task_id.
--
-- Progress counters stay in their own columns. They are written on a hot path once per file,
-- and rewriting a JSON blob for each increment would turn an integer bump into a
-- read-modify-write (DEC-05 keeps write transactions short).

ALTER TABLE Async_Task ADD COLUMN result_json TEXT;
