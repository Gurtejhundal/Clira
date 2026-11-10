"""Local creator planning. No Google identity or grant is fabricated."""

from datetime import UTC, datetime, timedelta

from .config import CliraError
from .storage import uid


def launch(service, interest, viewer, language, time, format):
    values = [interest, viewer, language, time, format]
    if any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in values):
        raise CliraError("LAUNCH_INPUT", "Complete all five short launch decisions (500 characters each).")
    channel_id = uid("workspace")
    name = f"{interest[:45]} · launch draft"
    service.store.add_channel(
        channel_id,
        name,
        "draft",
        {
            "niche": interest,
            "voice": "clear and practical",
            "language": language,
            "timezone": "UTC",
            "rules": f"Audience: {viewer}. Available time: {time}. Format: {format}.",
        },
    )
    plan = service.store.put(
        channel_id,
        "launch",
        {
            "decisions": dict(zip(["interest", "viewer", "language", "time", "format"], values)),
            "positioning": f"Explain {interest} for {viewer} in {language} through {format}.",
            "name_suggestions": [
                f"{interest[:35]} Explained",
                f"Inside {interest[:35]}",
                f"Everyday {interest[:35]}",
            ],
            "description": f"Practical {interest} stories for {viewer}. New {format} in {language}.",
            "brand_direction": "Ink and ivory, readable original artwork; owner selects final identity.",
            "source": "local",
            "evidence_status": "Offline starter templates; validate audience demand.",
            "channel_creation": "Manual: https://www.youtube.com/create_channel. This workspace is not a YouTube account.",
        },
    )
    for i, angle in enumerate(
        ["a beginner's first decision", "one common misconception", "a practical experiment"]
    ):
        idea = service.store.put(
            channel_id,
            "idea",
            {
                "title": f"{interest[:70]}: {angle}",
                "premise": f"Help {viewer} understand {angle}. Owner must check claims.",
                "format": "long" if format.lower() != "short" else "short",
                "sources": [],
                "evidence_status": "Local template; no trend claim",
            },
        )
        service.store.put(
            channel_id,
            "calendar",
            {
                "idea_id": idea["id"],
                "title": idea["title"],
                "at": (datetime.now(UTC) + timedelta(days=7 * (i + 1))).isoformat(),
                "status": "draft plan",
            },
        )
    service.store.audit(channel_id, "workspace.launch", "local_draft_created")
    return {"workspace": service.store.channel(channel_id), "plan": plan}


def copy_drafts(service, workspace_id, channel_id, confirmed):
    source = service.policy.channel(workspace_id)
    target = service.policy.channel(channel_id)
    if (
        source["mode"] != "draft"
        or target["mode"] != "live"
        or not target["connection"]
        or confirmed != channel_id
    ):
        raise CliraError("CONFIRM_CHANNEL", "Confirm the exact connected live channel ID to copy drafts.")
    # Never transfer grants, sessions, assets, approvals or jobs. Preserve source ownership.
    copied = []
    for kind in ["idea", "brief", "metadata"]:
        for record in service.store.list(workspace_id, kind):
            data = {k: v for k, v in record.items() if k not in {"id", "channel_id", "kind"}}
            copied.append(service.store.put(channel_id, kind, {**data, "copied_from": record["id"]}))
    service.store.audit(channel_id, "workspace.copy", "owner_confirmed", metadata={"source": workspace_id})
    return {"copied": copied, "original_workspace_preserved": True}
