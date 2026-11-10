# v0.1.0 → v1 candidate data migration and rollback

Stop all Clira terminals, servers and workers before upgrading or restoring. Use the same
`CLIRA_DATA_DIR` for terminal and website. The launcher defaults to a project-local `.clira` directory;
installed commands use the current directory unless you configure an absolute data directory.

Before upgrading, run the **old version**:

```bash
clira backup /safe/location/before-v1.sqlite3
```

Back up `.clira/assets` separately and protect `.clira/secrets` separately. A SQLite backup excludes
media and credentials. Never copy a live SQLite main file alone while WAL writers are active.

Migration 2 is additive: it creates `session_meta` and backfills titles/timestamps/activity for existing
conversations. The original four-column conversations table, channels, approvals, upload checkpoints
and jobs remain in place. The migration is idempotent and runs transactionally. Existing messages are
preserved. New conversations retain their complete saved text and tool receipts; the model sees only
recent context. A persisted per-session request lease prevents simultaneous CLI/web requests from
silently overwriting each other. An interrupted process's lease expires after ten minutes; cancelling
in the terminal marks that request failed without pretending completed drafts were undone.

Draft identities begin `workspace_`; they never masquerade as UC account IDs. Draft workspaces are
visible in both execution modes but cannot execute account writes. Switching demo/live never turns
a demo identity into a real account. Copying ideas/briefs/metadata to a connected account requires an
explicit exact-ID confirmation through `/api/workspaces/copy`; no credentials, sessions, approvals,
jobs or media files are transferred. Originals stay owned by the draft workspace. File references in
copied packages must be imported and reviewed in the target channel before uploading.

For rollback, stop the new version and install the previous release. Restore the pre-upgrade database
backup plus its corresponding assets/secrets if needed. Preserve the new database separately for
reconciliation. Never downgrade by deleting migration rows or truncating tables. Uploads/publications
already accepted by YouTube cannot be undone by restoring local files; inspect the remote account
before retrying. The tests verify migration/restart, backup integrity and use of the untouched v0.1
backup as the undo route. Published v0.1.0 assets/tags are unchanged.
