# Live account setup

Use the local demo before connecting. It demonstrates the workflow without an API key or account.
No live test was performed during development; Google credentials and channel consent are missing.

1. In Google Cloud, enable **YouTube Data API v3** and **YouTube Analytics API**.
2. Configure Google Auth Platform's consent screen. If the app is in testing, add your Google
   identity as a test user. Verification/testing-mode limits are controlled by Google.
3. Create a **Desktop app** OAuth client and save its JSON outside the project.
4. In a terminal at the Clira project directory:

   ```bash
   export CLIRA_GOOGLE_CLIENT_FILE=/absolute/path/to/client.json
   ./run.sh --mode live connect
   ```

5. Complete Google sign-in in the browser. Select the intended YouTube/brand account. Back in
   the terminal, inspect the returned channel title and type its exact immutable channel ID.
   If it is wrong, do not confirm; reconnect with the intended account.
6. Run `./run.sh --mode live channels`, then a read:

   ```bash
   ./run.sh --mode live chat --channel UC_ACTUAL_ID 'Show my latest five uploads'
   ./run.sh --mode live analytics --channel UC_ACTUAL_ID --days 28
   ```

7. Set `CLIRA_MODEL=gemini`, supply `GEMINI_API_KEY` privately, and set
   `CLIRA_ALLOW_MODEL_CALLS=1` when ready to authorize your own model requests. Set a suitable
   request cap and provider billing limit. Restart `./run.sh --mode live serve`.
8. Set the channel niche, voice and rules in Settings. Keep channel identity and profiles separate.

For upload access, reconnect with `--capability upload`; for account-management/public actions,
reconnect with `--capability manage`. These grants include the needed read/analytics scopes too.
Desktop app grants are requested afresh rather than assuming incremental consent. Public actions
still require an exact owner approval. Set `CLIRA_ENABLE_WRITES=1` only when ready to use them.

The first approved upload must be an original or properly licensed file, explicitly PRIVATE, with
an exact target-channel preview. An API project's restrictions can prevent public release even
when private upload works. Test live reads first; do not interpret mock tests as account verification.

Credentials are stored as owner-only JSON secret files, not encrypted at rest. Use an encrypted
disk/OS account protections as appropriate. If the selected filesystem cannot enforce owner-only
permissions, Clira refuses the secret directory; choose `CLIRA_DATA_DIR` on a supported filesystem.
No keyring integration or hosted multi-user authentication is included.

If a token expires/revokes, reconnect. Prerequisite failures before a write can pause a job; resume
after fixing consent. Never replace a `RECOVERY_REQUIRED` job with a fresh upload without inspecting
the remote state. An uploaded video ID saved in the job is the primary reconciliation receipt.

To disconnect locally: `./run.sh --mode live disconnect --channel UC_ACTUAL_ID`.
To revoke at Google: [account permissions](https://myaccount.google.com/permissions).
Remove or change any existing scheduled publication in YouTube Studio; local pause/disconnect does
not cancel a schedule that Google has already accepted.


## v1 candidate: terminal and website share one workspace

Run `uv run clira` to open the interactive terminal, or `uv run clira serve` for the local website.
Use an absolute `CLIRA_DATA_DIR` in every shell to share data across working directories. First run
lets you start a local launch workspace, connect an existing channel, or explore synthetic demo data.
Five launch decisions produce starter drafts without Google sign-in. These are offline templates;
open-ended writing needs an explicitly enabled model.

In live website Settings, **Start read-only Google sign-in** opens the existing Desktop OAuth flow.
Configure the client JSON privately before starting the server. After Google authorization, review
actual channel name/ID and type the exact ID; credentials are saved only after that confirmation.
Demo refuses this flow. A missing client produces a helpful error, never a token-entry form.
The current flow expires if authorization/confirmation is not completed; retry from Settings.

Use Saved conversations to resume/rename/search. The website shows the implemented terminal resume
command. `/web` in the terminal checks the matching store's loopback server before opening its session.
`/clear` clears display only. Ctrl+J inserts a newline; Enter sends. NO_COLOR and --no-logo are supported.
No terminal history file containing secrets is created; saved conversational text stays in SQLite.

For real packaging files and separate upload approvals see [Packaging](PACKAGING.md).
Before upgrading/restoring, follow [Migration and rollback](MIGRATIONS.md).
Stable release is blocked until the live gates in [candidate verification](VERIFICATION_V1_RC.md) pass.
