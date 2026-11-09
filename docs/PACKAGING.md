# Video packaging in the v1 candidate

Production keeps real imported files separate from metadata concepts. Copy files into the configured
imports directory shown on screen. Import your finished MP4 first. Technical QC does not establish
rights or creative quality.

1. Import JPEG/PNG or create an explicitly selected **deterministic local PNG template**. The template
   produces a real 1280×720 file and preview. It is not an image-model generation claim. Template text
   supports ASCII; use your own image for other scripts. Review the actual file, attest original/licensed
   rights with evidence and creative quality. Imported images receive the same review gates.
2. Import UTF-8 SRT or basic WebVTT, selecting the actual imported video to check duration. Preview
   timed cues, edit and save as a **new unreviewed file**, then review it again. Supported cues have
   explicit ordered, nonoverlapping times and plain text. VTT cue settings/markup/overlaps are rejected
   explicitly; Clira does not silently discard advanced formatting. Transcription is not configured.
3. Select thumbnail/captions in the MP4 package. Enter the factual title and description, a small relevant
   set of tags/hashtags, made-for-kids and altered/synthetic-media choices. Local title alternatives are
   templates, not factual verification or growth predictions. The owner chooses and edits the title.
4. Optional chapters require the actual imported video's duration, a first timestamp at 00:00, at least
   three chapters and at least ten seconds per chapter including the last. An eight-second fixture cannot
   have valid manual chapters. Valid chapter lines and hashtags are included in the description.
5. Prepare the **private video** approval. The preview binds exact metadata, video hash, packaging file
   IDs/hashes and rights evidence. Approve, then separately execute. Packaging files are rechecked before
   execution. They are not silently uploaded as a side effect of this approval.
6. Once the private video receipt exists, enter its exact owned video ID on each packaging card and
   prepare a **separate** thumbnail/caption upload approval. Inspect exact target, SHA-256, rights,
   language/name/draft status. Approve and execute separately in Approvals. Caption tracks default to
   draft; explicitly change the checkbox only when you intend a non-draft track.

CLI examples (replace IDs with actual records):

```bash
clira tool thumbnail_template --channel ID --json '{"text":"An original guide"}'
clira tool import_package_asset --channel ID --json @caption-import.json
clira tool review_package_asset --channel ID --json @exact-owner-review.json
clira tool edit_captions --channel ID --json @edited-timed-text.json
clira tool package_video --channel ID --json @metadata.json
clira tool prepare_attachment --channel ID --json @exact-attachment-target.json
clira approval show APPROVAL_ID --channel ID
clira approval approve APPROVAL_ID --channel ID
clira jobs run JOB_ID --channel ID
```

Use `clira tool` contracts from `/api/tools` for exact strict schemas. Rights review is excluded from
model declarations and also blocked for agent callers at the service boundary. No approval or job
execution tool is exposed to the model.

## Current documented limits and intentional app restrictions

Official docs rechecked during implementation on 9 November 2026:

- [thumbnails.set](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set):
  JPEG/PNG accepted; current API maximum 50 MB. Clira deliberately enforces a conservative **2 MiB**
  import limit, at least 640×360 and at most 7680×4320; long-form template is 1280×720. These are app
  constraints, not a claim that the API always requires precisely this size/aspect ratio. Accounts and
  Shorts can have additional eligibility/processing restrictions.
- [captions.insert](https://developers.google.com/youtube/data/reference/rest/v3/captions/insert):
  current API maximum 100 MB; Clira deliberately limits manual imports to **4 MiB**, 20,000 plain cues,
  UTF-8 SRT/VTT. Caption edits are capped at 200,000 characters. No deprecated automatic-sync flag is
  sent. Caption upload requires `youtube.force-ssl`; this implementation also conservatively requests
  that management scope for thumbnail writes, although the thumbnail API permits upload scope too.
- [manual chapters](https://support.google.com/youtube/answer/9884579?hl=en): first at zero, three or
  more ascending timestamps, minimum ten-second chapters. Platform feature eligibility still applies.

Thumbnail and caption adapters use official upload endpoints. Tests inspect actual HTTP wire bodies
through mock transports. An accepted API response is labelled **accepted**, never proof that the image
matches or captions play correctly. Owner playback/visual review and live account verification remain
required. A lost caption/thumbnail write outcome goes to RECOVERY_REQUIRED rather than blindly inserting
another track. Scheduling, publication and replies retain their own separate exact approvals.
