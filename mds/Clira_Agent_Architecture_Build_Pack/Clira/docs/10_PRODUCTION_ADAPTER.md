# 10 — Video Production Boundary (Lemo Is External)

## Guiding rule
The **agent manages YouTube**. It does not render animation itself. A production provider can be Lemo-Opuscar, a future third-party system, or a manual import. Neither the core agent nor YouTube API layer imports internals from Lemo directly.

## Interface
```python
class ProductionProvider:
    def submit(self, brief: dict) -> dict: ...    # returns external_job_id
    def status(self, external_job_id: str) -> dict: ...
    def collect(self, external_job_id: str) -> dict: ... # asset manifest
    def cancel(self, external_job_id: str) -> dict: ...
```

## Provider-neutral handoff
```json
{
  "brief_version": 1,
  "channel_id": "UC_EXAMPLE_ONLY",
  "format": "short",
  "aspect_ratio": "9:16",
  "duration_target_seconds": 40,
  "script_uri": "workspace://briefs/123/script.json",
  "creative_direction": "warm 2D explainer, no sci-fi HUD",
  "storyboard_uri": "workspace://briefs/123/storyboard.json",
  "quality_preset": "preview",
  "rights_constraints": {"allow_copyrighted_music": false}
}
```

## Asset manifest returned by provider
```json
{
  "external_job_id":"external_123",
  "status":"completed",
  "assets":[
    {"kind":"video","path":"/workspace/exports/video.mp4","sha256":"..."},
    {"kind":"captions","path":"/workspace/exports/captions.srt","sha256":"..."},
    {"kind":"thumbnail","path":"/workspace/exports/thumb.png","sha256":"..."}
  ],
  "rights_evidence":[],
  "notes":"Human visual review still required"
}
```

## Local ingest gate
1. Confirm file exists in approved import directory.
2. Hash content, inspect ffprobe streams, check audio/captions/thumbnail.
3. Run technical QC; generate contact sheet and short playback sample.
4. Require human creative/rights review unless an explicitly scoped policy says otherwise.
5. Create private-upload draft; never publish simply because provider reports `completed`.

## Optional Lemo adapter
Find actual Lemo CLI/docs/version installed; use an allowlisted command with fixed options. Do not assume Lemo has a stable programmatic API. If the existing studio has a reliable production command, wrap that command instead of editing its internals.

## Copyright
Sourced music requires evidence of license or platform-authorized music usage; direct upload of a commercial master may be claimed, blocked or monetization-ineligible.
