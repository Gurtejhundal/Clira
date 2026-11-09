# 08 — Research, Scripts, SEO and Editorial Intelligence

## Content planning
- Channel-specific themes, audience intent, language, prior successes and known exclusions.
- Suggestions grounded in public trends and/or owned analytics; label all source dates and uncertainty.
- Duplicate-topic detector comparing recent scripts/titles and semantic similarity; don't mass-produce near-identical videos.
- Format-specific briefs: Short (15–60 s), long-form explainer (5–7 min), music (rights verified), others as profile allows.

## Reuse the GitHub skill utilities carefully
Installed toolkit reference: https://github.com/Jakeschincariol/youtube-agent-skill
- `hookscore.py`: editorial critique of hook, **not** view predictor.
- `title.py`: title/thumbnail complement and cutoff heuristic.
- `deadair.py`: transcript-based editing suggestions.
- `chapters.py`: chapter format validation.
- `retention.py`: analyzes user-provided retention exports.
- `swipe.py`: public-video outlier comparison from collected data.

Wrap each utility as a deterministic tool with validated inputs, subprocess timeout, JSON output normalization and tests; avoid maintaining duplicate copies unless licensing/version pinning requires it.

## Research and fact-check
For each substantive factual assertion in scripts: evidence URL/document ID, retrieved date, exact claim, source quality and verification result. Prefer primary material. No fake quotations or figures. If an assertion is uncertain, revise/remove it.

## Brief format
```json
{
  "channel_id":"UC_EXAMPLE_ONLY",
  "format":"short",
  "working_title":"What happens when you delete a file?",
  "audience_promise":"Understand deletion vs storage erasure",
  "duration_target_seconds":45,
  "hook":"It vanished. But was it erased?",
  "beats":[{"seconds":"0-6","narration":"...","visual_intent":"..."}],
  "verified_claims":[{"claim":"...","source_url":"..."}],
  "asset_requirements":[],
  "rights_constraints":"original visuals, licensed audio only"
}
```

## Packaging
Generate 3–5 title directions, each with a thumbnail brief that does not merely duplicate title wording. Output descriptions, tags only if useful, correct disclosures, and chapter candidates validated on the real video. Never promise high CTR from a title score.

## Editorial feedback loop
Weekly: compare performance of actual released content, ask what caused outcomes, and preserve hypotheses separately from verified facts. Never optimize solely for retention at the expense of accuracy or viewer trust.
