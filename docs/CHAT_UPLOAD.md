# Upload from chat

## Website

1. Start Clira in live mode with an upload-capable channel grant and approved writes enabled.
2. Select the connected channel in **Talk to Clira**.
3. Click **Attach MP4**, select a finished video (up to 256 MiB), and send “Upload this video.”
4. Clira validates and stores an immutable copy, samples three frames, and asks the configured Gemini model for a title, description, relevant tags, summary and suggested script outline.
5. The chat displays the exact video player and editable package. Review rights/evidence, made-for-kids and realistic synthetic-media choices, then approve privately.
6. **Approve & upload privately** binds that package to the active channel and hashed bytes, records exact owner approval, executes the existing durable upload job, verifies the receipt and returns its URL. You do not need to switch to Production or Approvals.

Gemini calls require the existing explicit provider enablement and count against the daily request cap.
The attachment hint discloses that sampled frames are sent to the configured AI provider.
Creator profile sharing still follows its saved consent. Video samples are not stored in conversations.

## Terminal

Use `/upload /absolute/path/in/the/imports/folder/video.mp4`. The preview appears in the conversation.
Then `/upload-approve UPLOAD_DRAFT_ID` asks for owner rights/disclosure review and the exact phrase
`APPROVE PRIVATE UPLOAD`, and runs the same approval and execution path. `/help` lists both commands.
Existing `/approve` still only approves; its behavior has not changed.

## Boundaries

This flow accepts finished videos; it does not rewrite or render the video itself. The script outline
is an editorial draft, not an audio transcript. Only three sampled frames are analyzed; spoken audio,
full motion, factual accuracy and licensing require review. Offline mode produces an explicitly
labeled template, not AI content analysis. No invented speech captions or chapter timings are generated.
Thumbnail and caption uploads remain separate exact approved actions through existing packaging tools.
The upload is always private; public publication needs its own approval.

Interrupted approval/execute or repeated clicks do not restart the preview. Inspect the saved job in
Operations, especially for `RECOVERY_REQUIRED`. A prior same-byte upload is detected by the existing
idempotency key. Never create a duplicate upload to clear a UI error.

Tag verification treats tag ordering as irrelevant, while missing/added tags and all other snippet
changes still trigger reconciliation. This fixes YouTube reordering identical tags after upload.
