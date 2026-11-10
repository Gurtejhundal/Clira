import json
import random
import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import httpx
from pydantic import ValidationError

from .config import CliraError, Config
from .contracts import TOOLS, ToolSuccess
from .media import editorial_lint, file_hash, import_video
from .policy import Policy
from .storage import SecretStore, Store, digest, encode, now
from .youtube import MANAGE_SCOPE, UPLOAD_SCOPE, DemoYouTube, GoogleYouTube

DEMO_CHANNEL = "DEMO_CHANNEL_TECH"


class Service:
    def __init__(self, config=None):
        self.config = config or Config()
        self.store = Store(self.config.data_dir / "clira.sqlite3")
        self.secrets = SecretStore(self.config.data_dir / "secrets")
        self.policy = Policy(self.config, self.store)
        if self.config.mode == "demo" and not self.store.rows(
            "SELECT id FROM channels WHERE id=?", (DEMO_CHANNEL,)
        ):
            self.store.add_channel(
                DEMO_CHANNEL,
                "Inside the everyday · Demo",
                "demo",
                {
                    "niche": "everyday technology explained",
                    "voice": "curious, clear and practical",
                    "language": "English",
                    "timezone": "Asia/Kolkata",
                    "rules": "Original explanations; no unsupported claims or licensed music assumptions.",
                },
            )

    def adapter(self, channel_id):
        channel = self.policy.channel(channel_id)
        if channel["mode"] == "draft":
            raise CliraError(
                "NOT_CONNECTED", "This is a local launch workspace. No YouTube account is connected."
            )
        return DemoYouTube(channel_id) if channel["mode"] == "demo" else GoogleYouTube(channel, self.secrets)

    def channels(self):
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "mode": c["mode"],
                "profile": json.loads(c["profile"]),
                "connected": bool(json.loads(c["connection"])),
            }
            for c in self.store.rows(
                "SELECT * FROM channels WHERE mode IN (?, 'draft') ORDER BY created_at", (self.config.mode,)
            )
        ]

    def tool(self, channel_id, name, arguments=None, actor="owner"):
        try:
            self.policy.channel(channel_id)
            if name not in TOOLS:
                raise CliraError(
                    "UNKNOWN_TOOL", "Tool not registered. The agent cannot grant itself new tools."
                )
            schema, permission, _ = TOOLS[name]
            try:
                args = schema.model_validate(arguments or {})
            except ValidationError as exc:
                # Exclude input values from diagnostics to avoid leaking paths or private text.
                errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
                raise CliraError("INVALID_INPUT", encode(errors)) from None
            if (
                name in {"import_video", "import_package_asset"}
                and actor != "owner"
                and (args.rights != "unreviewed" or args.creative_reviewed)
            ):
                raise CliraError(
                    "OWNER_REVIEW_REQUIRED", "The model cannot assert rights ownership or creative approval."
                )
            if name == "review_package_asset" and actor != "owner":
                raise CliraError(
                    "OWNER_REVIEW_REQUIRED", "Only the owner can attest packaging rights or creative review."
                )
            data = getattr(self, "tool_" + name)(channel_id, args)
            self.store.audit(channel_id, name, "completed", metadata={"permission": permission}, actor=actor)
            result = {
                "ok": True,
                "tool": name,
                "channel_id": channel_id,
                "observed_at": now(),
                "source": "mock"
                if self.store.channel(channel_id)["mode"] == "demo"
                and name
                in {
                    "channel_overview",
                    "list_videos",
                    "channel_report",
                    "weekly_digest",
                    "list_comments",
                    "research_videos",
                    "prepare_metadata",
                    "prepare_schedule",
                    "prepare_publish",
                }
                else (
                    "youtube_analytics_api"
                    if name in {"channel_report", "weekly_digest"}
                    else "youtube_data_api"
                    if name in {"list_videos", "list_comments", "channel_overview", "research_videos"}
                    else "local"
                ),
                "data": data,
                "warnings": ["Synthetic demo mode; no real account operations."]
                if self.store.channel(channel_id)["mode"] == "demo"
                else [],
            }
            return ToolSuccess.model_validate(result).model_dump()
        except CliraError as exc:
            self.store.audit(channel_id, name, "blocked", metadata={"code": exc.code}, actor=actor)
            return {**exc.envelope(), "tool": name, "channel_id": channel_id, "observed_at": now()}

    def tool_channel_overview(self, channel_id, args):
        channel = self.policy.channel(channel_id)
        actual = self.adapter(channel_id).verify()
        return {
            "channel_id": channel_id,
            "name": actual["snippet"]["title"],
            "profile": channel["profile"],
            "mode": channel["mode"],
            "writes_enabled": self.config.enable_writes,
            "paused": self.store.setting("paused", False),
        }

    def tool_list_videos(self, channel_id, args):
        videos = self.adapter(channel_id).list_videos(args.count)
        for video in videos:
            self.store.put(
                channel_id,
                "video_cache",
                {"video": video, "observed_at": now()},
                "vc_" + digest([channel_id, video["id"]]),
            )
        return {
            "videos": videos,
            "statistics_window": "lifetime",
            "freshness": "mock" if self.config.mode == "demo" else "fresh",
        }

    def tool_channel_report(self, channel_id, args):
        data = self.adapter(channel_id).report(args.days)
        self.store.put(
            channel_id,
            "analytics",
            {
                **data,
                "observed_at": now(),
                "source": "mock" if self.config.mode == "demo" else "youtube_analytics_api",
            },
        )
        return data

    def tool_list_ideas(self, channel_id, args):
        return {"ideas": self.store.list(channel_id, "idea")}

    def tool_research_videos(self, channel_id, args):
        if self.config.mode == "live":
            self.store.consume_budget(10, prefix="public_search_calls")
        result = self.adapter(channel_id).research(args.query, args.count)
        self.store.put(channel_id, "research", {**result, "observed_at": now()})
        return result

    def tool_weekly_digest(self, channel_id, args):
        adapter = self.adapter(channel_id)
        current, previous = adapter.report(7), adapter.report(7, offset_days=7)
        changes = {}
        for metric in ("views", "estimatedMinutesWatched", "subscribersGained"):
            a, b = current["metrics"].get(metric), previous["metrics"].get(metric)
            if a is not None and b is not None:
                changes[metric] = {
                    "absolute_change": a - b,
                    "percent_change": round((a - b) / b * 100, 2) if b else None,
                }
        result = {
            "current": current,
            "previous": previous,
            "changes": changes,
            "interpretation": "Descriptive comparison; reporting delays and sample size limit causal conclusions.",
            "observed_at": now(),
        }
        self.store.put(channel_id, "digest", result)
        return result

    @staticmethod
    def similar(a, b):
        a, b = re.sub(r"\W+", " ", a.lower()).strip(), re.sub(r"\W+", " ", b.lower()).strip()
        return SequenceMatcher(None, a, b).ratio() > 0.82

    def tool_save_idea(self, channel_id, args):
        titles = [i["title"] for i in self.store.list(channel_id, "idea")]
        titles += [v["video"]["snippet"]["title"] for v in self.store.list(channel_id, "video_cache")]
        if any(self.similar(args.title, title) for title in titles):
            raise CliraError(
                "DUPLICATE_TOPIC",
                "A similar topic is already in this channel's history. Choose another angle.",
            )
        for source in args.sources:
            if not source.startswith("https://"):
                raise CliraError("INVALID_SOURCE", "Evidence references must use HTTPS URLs.")
        return self.store.put(
            channel_id,
            "idea",
            {
                **args.model_dump(),
                "status": "proposed",
                "evidence_status": "source_links_unverified" if args.sources else "editorial_hypothesis",
            },
        )

    def tool_write_script(self, channel_id, args):
        idea = self.store.get(channel_id, args.idea_id, "idea")
        return self.store.put(
            channel_id,
            "brief",
            {
                **args.model_dump(),
                "title": idea["title"],
                "status": "draft_needs_fact_check",
                "evidence_status": "unverified",
                "version": 1,
                "hook_lint": editorial_lint("hook", args.hook),
                "production": {
                    "provider": "manual",
                    "status": "awaiting_manual_video",
                    "rights_constraints": "Original or licensed visuals and audio only.",
                },
            },
        )

    def tool_title_options(self, channel_id, args):
        return {
            "titles": [
                args.subject + ": a beginner's guide",
                "Understanding " + args.subject,
                args.subject + ": one decision explained",
            ],
            "source": "local",
            "status": "Offline templates; owner selects and checks every factual claim.",
        }

    def tool_import_package_asset(self, channel_id, args):
        from .packaging import import_asset

        return import_asset(self, channel_id, args)

    def tool_thumbnail_template(self, channel_id, args):
        from .packaging import template

        return template(self, channel_id, args)

    def tool_review_package_asset(self, channel_id, args):
        record = self.store.get(channel_id, args.package_asset_id, "package_asset")
        return self.store.put(
            channel_id,
            "package_asset",
            {
                **record,
                "rights": args.rights,
                "rights_evidence": args.rights_evidence,
                "creative_reviewed": args.creative_reviewed,
            },
            record["id"],
        )

    def tool_edit_captions(self, channel_id, args):
        from .packaging import captions, save_asset

        record = self.store.get(channel_id, args.package_asset_id, "package_asset")
        if record["type"] != "captions":
            raise CliraError("CAPTION_FORMAT", "Select a caption file.")
        asset = (
            self.store.get(channel_id, record["video_asset_id"], "asset")
            if record.get("video_asset_id")
            else None
        )
        data = captions(args.text, asset["qc"]["duration_seconds"] if asset else None)
        return save_asset(
            self,
            channel_id,
            data["text"].encode(),
            "." + data["format"],
            {
                **data,
                "type": "captions",
                "language": record["language"],
                "mime": "text/vtt" if data["format"] == "vtt" else "application/x-subrip",
                "video_asset_id": record.get("video_asset_id"),
                "edited_from": record["id"],
            },
            "unreviewed",
            "",
            False,
        )

    def tool_prepare_attachment(self, channel_id, args):
        from .packaging import verify_package_asset

        record = self.store.get(channel_id, args.package_asset_id, "package_asset")
        verify_package_asset(self, channel_id, record)
        video = self.adapter(channel_id).video(args.video_id)  # adapter enforces immutable ownership
        payload = {
            "video_id": args.video_id,
            "package_asset_id": record["id"],
            "sha256": record["sha256"],
            "destination_channel": channel_id,
            "visibility": video["status"]["privacyStatus"],
            "rights": record["rights"],
            "rights_evidence": record["rights_evidence"],
            "name": args.name,
            "is_draft": args.is_draft,
            "language": record.get("language"),
            "mime": record["mime"],
        }
        return self.policy.prepare(
            channel_id, "set_thumbnail" if record["type"] == "thumbnail" else "insert_captions", payload
        )

    def tool_package_video(self, channel_id, args):
        from .packaging import chapters, verify_package_asset

        if any(not re.fullmatch(r"#[\w]+", tag) for tag in args.hashtags):
            raise CliraError(
                "HASHTAGS",
                "Use at most five relevant hashtags, each beginning with # and containing no spaces.",
            )
        if any("<" in text or ">" in text for text in [args.title, args.description, *args.tags]):
            raise CliraError("METADATA", "Angle brackets are not supported in YouTube metadata.")
        if len(args.description.encode()) > 5000:
            raise CliraError("DESCRIPTION_LENGTH", "Description must fit 5000 UTF-8 bytes.")
        chapter_text = ""
        if args.chapters:
            if not args.asset_id:
                raise CliraError(
                    "VIDEO_REQUIRED", "Select the real imported video to validate chapter duration."
                )
            asset = self.store.get(channel_id, args.asset_id, "asset")
            chapter_text = chapters([c.model_dump() for c in args.chapters], asset["qc"]["duration_seconds"])
        manifest = []
        for rid, expected in [(args.thumbnail_id, "thumbnail"), (args.captions_id, "captions")]:
            if rid:
                item = self.store.get(channel_id, rid, "package_asset")
                if item["type"] != expected:
                    raise CliraError("PACKAGE_TYPE", "Select the correct packaging file type.")
                verify_package_asset(self, channel_id, item, reviewed=False)
                if expected == "captions" and item.get("video_asset_id") != args.asset_id:
                    raise CliraError(
                        "PACKAGE_VIDEO", "Caption file must be timed against this imported video."
                    )
                manifest.append(
                    {
                        "id": rid,
                        "type": expected,
                        "sha256": item["sha256"],
                        "rights": item["rights"],
                        "rights_evidence": item["rights_evidence"],
                        "creative_reviewed": item["creative_reviewed"],
                    }
                )
        description = "\n\n".join(t for t in [args.description, chapter_text, " ".join(args.hashtags)] if t)
        if len(description.encode()) > 5000:
            raise CliraError("DESCRIPTION_LENGTH", "Combined description exceeds 5000 UTF-8 bytes.")
        return self.store.put(
            channel_id,
            "metadata",
            {
                **args.model_dump(),
                "description": description,
                "packaging_manifest": manifest,
                "status": "draft",
                "lint": editorial_lint("title", args.title, args.thumbnail_text),
            },
        )

    def tool_calendar_add(self, channel_id, args):
        idea = self.store.get(channel_id, args.idea_id, "idea")
        return self.store.put(
            channel_id,
            "calendar",
            {
                "idea_id": args.idea_id,
                "title": idea["title"],
                "at": args.at,
                "status": "editorial_plan_only",
                "publishes": False,
            },
        )

    def tool_import_video(self, channel_id, args):
        return import_video(self.config, self.store, channel_id, args)

    def validate_asset(self, channel_id, asset):
        path = Path(asset["path"])
        root = self.config.data_dir / "assets" / channel_id
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise CliraError("ASSET_MISSING", "Managed asset is missing or outside channel storage.")
        if file_hash(path) != asset["sha256"]:
            raise CliraError("ASSET_CHANGED", "Asset bytes changed. Import again and review a fresh request.")
        if (
            asset["rights"] not in {"licensed", "original"}
            or not asset["rights_evidence"].strip()
            or not asset["creative_reviewed"]
        ):
            raise CliraError(
                "RIGHTS_REVIEW_REQUIRED",
                "Owner must review creative quality and document rights for video and audio.",
            )

    @staticmethod
    def metadata_body(metadata):
        return {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"],
                "categoryId": metadata["category_id"],
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": metadata["made_for_kids"],
                "containsSyntheticMedia": metadata["synthetic_media"],
            },
        }

    def tool_prepare_upload(self, channel_id, args):
        asset = self.store.get(channel_id, args.asset_id, "asset")
        self.validate_asset(channel_id, asset)
        metadata = self.store.get(channel_id, args.metadata_id, "metadata")
        if metadata.get("asset_id") and metadata["asset_id"] != args.asset_id:
            raise CliraError("PACKAGE_VIDEO", "Package belongs to another imported video.")
        manifest = metadata.get("packaging_manifest", [])
        from .packaging import verify_package_asset

        for item in manifest:
            record = self.store.get(channel_id, item["id"], "package_asset")
            verify_package_asset(self, channel_id, record)
            if any(
                record[k] != item[k] for k in ["sha256", "rights", "rights_evidence", "creative_reviewed"]
            ):
                raise CliraError("ASSET_CHANGED", "Packaging asset changed.")
        payload = {
            "packaging_manifest": manifest,
            "packaging_note": "Thumbnail and captions need separate approval and upload after the private video receipt.",
            "asset_id": args.asset_id,
            "asset_sha256": asset["sha256"],
            "filename": asset["filename"],
            "rights": asset["rights"],
            "rights_evidence": asset["rights_evidence"],
            "metadata_id": args.metadata_id,
            "body": self.metadata_body(metadata),
            "destination_channel": channel_id,
            "privacy": "private",
        }
        return self.policy.prepare(
            channel_id,
            "upload_private",
            payload,
            "upload:" + self.config.mode + ":" + channel_id + ":" + asset["sha256"],
        )

    def tool_prepare_metadata(self, channel_id, args):
        metadata = self.store.get(channel_id, args.metadata_id, "metadata")
        current = self.adapter(channel_id).video(args.video_id)
        writable = {
            key: value
            for key, value in current["snippet"].items()
            if key in {"title", "description", "tags", "categoryId", "defaultLanguage"}
        }
        writable.update(self.metadata_body(metadata)["snippet"])
        return self.policy.prepare(
            channel_id,
            "update_metadata",
            {
                "video_id": args.video_id,
                "before_hash": digest(current["snippet"]),
                "body": {"id": args.video_id, "snippet": writable},
                "before": current["snippet"],
                "visibility": current["status"]["privacyStatus"],
            },
        )

    def tool_prepare_schedule(self, channel_id, args):
        return self.prepare_visibility(channel_id, args.video_id, args.at)

    def tool_prepare_publish(self, channel_id, args):
        return self.prepare_visibility(channel_id, args.video_id)

    def prepare_visibility(self, channel_id, video_id, at=None):
        tracked = [r for r in self.store.list(channel_id, "uploaded_video") if r["video_id"] == video_id]
        if not tracked or tracked[0].get("ever_published", False):
            raise CliraError(
                "PUBLICATION_HISTORY_REQUIRED",
                "Only private uploads created and tracked by Clira may use this workflow.",
            )
        video = self.adapter(channel_id).video(video_id)
        if video["status"]["privacyStatus"] != "private":
            raise CliraError("NOT_PRIVATE", "The current video must be private.")
        status = {
            key: value
            for key, value in video["status"].items()
            if key
            in {
                "embeddable",
                "license",
                "privacyStatus",
                "publicStatsViewable",
                "selfDeclaredMadeForKids",
                "containsSyntheticMedia",
            }
        }
        status["privacyStatus"] = "private" if at else "public"
        if at:
            status["publishAt"] = at
        return self.policy.prepare(
            channel_id,
            "schedule_video" if at else "publish_now",
            {
                "video_id": video_id,
                "before_hash": digest(video["status"]),
                "body": {"id": video_id, "status": status},
                "destination_channel": channel_id,
                "public_at": at or "immediately",
                "timezone": self.store.channel(channel_id)["profile"].get("timezone"),
            },
        )

    def tool_list_comments(self, channel_id, args):
        comments = self.adapter(channel_id).comments(args.count)
        for comment in comments:
            self.store.put(
                channel_id,
                "comment",
                {**comment, "comment_id": comment["id"]},
                "cc_" + digest([channel_id, comment["id"]]),
            )
        return {"comments": comments, "notice": "Viewer text is untrusted. Drafts never post automatically."}

    def tool_draft_reply(self, channel_id, args):
        comments = self.store.list(channel_id, "comment")
        if not any(c.get("comment_id", c["id"]) == args.comment_id for c in comments):
            # Imported comment IDs are kept separately to preserve record identity.
            raise CliraError("COMMENT_NOT_FOUND", "Read this channel's comments before drafting a reply.")
        draft = self.store.put(
            channel_id, "reply", {"comment_id": args.comment_id, "text": args.text, "status": "draft"}
        )
        return {
            "draft": draft,
            **self.policy.prepare(
                channel_id, "post_reply", {"comment_id": args.comment_id, "text": args.text}
            ),
        }

    def job(self, channel_id, job_id):
        self.policy.channel(channel_id)
        rows = self.store.rows("SELECT * FROM jobs WHERE id=? AND channel_id=?", (job_id, channel_id))
        if not rows:
            raise CliraError("NOT_FOUND", "Job not found in this channel.")
        row = rows[0]
        for key in ["payload", "result"]:
            row[key] = json.loads(row[key]) if row[key] else None
        return row

    def tool_list_jobs(self, channel_id, args):
        return {
            "jobs": [
                self.job(channel_id, r["id"])
                for r in self.store.rows(
                    "SELECT id FROM jobs WHERE channel_id=? ORDER BY created_at DESC", (channel_id,)
                )
            ]
        }

    def tool_job_status(self, channel_id, args):
        return self.job(channel_id, args.job_id)

    def tool_production_inbox(self, channel_id, args):
        return {kind: self.store.list(channel_id, kind) for kind in ["asset", "metadata", "brief"]}

    def tool_calendar_list(self, channel_id, args):
        return {"plans": self.store.list(channel_id, "calendar"), "publishes": False}

    def execute_job(self, channel_id, job_id):
        claimed = False
        try:
            job = self.policy.claim(channel_id, job_id)
            if job["state"] == "COMPLETED":
                return {"ok": True, "job_id": job_id, "duplicate": True, "data": json.loads(job["result"])}
            claimed = True
            self.store.audit(channel_id, job["operation"], "started", job_id)
            payload = json.loads(job["payload"])
            adapter = self.adapter(channel_id)
            adapter.verify()  # Mandatory immediately before each account mutation, including resumed jobs.
            if isinstance(adapter, GoogleYouTube):
                adapter.token(UPLOAD_SCOPE if job["operation"] == "upload_private" else MANAGE_SCOPE)
            if job["operation"] == "upload_private":
                result = self.run_upload(channel_id, job_id, payload, adapter)
            else:
                result = self.run_mutation(channel_id, job_id, job["operation"], payload, adapter)
            self.store.execute(
                "UPDATE jobs SET state='COMPLETED',result=?,last_error=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                (encode(result), now(), job_id),
            )
            self.store.audit(
                channel_id,
                job["operation"],
                "verified",
                job_id,
                {"source": result["source"], "remote_id": result.get("video_id", result.get("comment_id"))},
            )
            return {"ok": True, "job_id": job_id, "data": result}
        except CliraError as exc:
            if not claimed:
                self.store.audit(channel_id, "job.execute", "blocked", job_id, {"code": exc.code})
                return {**exc.envelope(), "job_id": job_id}
            current = self.job(channel_id, job_id)
            if current["state"] == "RUNNING":
                state = "FAILED_RETRYABLE" if exc.retryable else "FAILED_TERMINAL"
                if exc.code in {"AUTH_REQUIRED", "SCOPE_REQUIRED"} and not current.get("result"):
                    state = "PAUSED"
                if exc.code == "RECONCILIATION_REQUIRED" or (current.get("result") or {}).get("stage") in {
                    "mutation_started",
                    "init_started",
                }:
                    state = "RECOVERY_REQUIRED"
                retry = (
                    datetime.now(UTC) + timedelta(seconds=2 ** current["attempts"] * 5 + random.random() * 3)
                ).isoformat()
                self.store.execute(
                    "UPDATE jobs SET state=?,last_error=?,next_run_at=?,lease_until=NULL,updated_at=? WHERE id=?",
                    (state, exc.code, retry if exc.retryable else None, now(), job_id),
                )
            self.store.audit(
                channel_id, current["operation"], "blocked_or_failed", job_id, {"code": exc.code}
            )
            return {**exc.envelope(), "job_id": job_id}
        except (httpx.HTTPError, OSError):
            # A write may have succeeded remotely. Never retry an ambiguous non-resumable mutation.
            self.store.execute(
                "UPDATE jobs SET state='RECOVERY_REQUIRED',last_error='OUTCOME_UNKNOWN',lease_until=NULL,updated_at=? WHERE id=?",
                (now(), job_id),
            )
            self.store.audit(channel_id, "job.execute", "outcome_unknown", job_id)
            return CliraError(
                "RECONCILIATION_REQUIRED",
                "Network or storage interrupted. Reconcile remote state before retrying.",
            ).envelope()

    def checkpoint(self, job_id, data):
        lease = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        self.store.execute(
            "UPDATE jobs SET result=?,lease_until=?,updated_at=? WHERE id=?",
            (encode(data), lease, now(), job_id),
        )

    def run_upload(self, channel_id, job_id, payload, adapter):
        asset = self.store.get(channel_id, payload["asset_id"], "asset")
        self.validate_asset(channel_id, asset)
        metadata = self.store.get(channel_id, payload["metadata_id"], "metadata")
        if asset["sha256"] != payload["asset_sha256"] or self.metadata_body(metadata) != payload["body"]:
            raise CliraError("APPROVAL_INVALIDATED", "The asset or metadata changed after approval.")
        if asset["rights_evidence"] != payload["rights_evidence"] or asset["rights"] != payload["rights"]:
            raise CliraError("APPROVAL_INVALIDATED", "Rights evidence changed after approval.")
        from .packaging import verify_package_asset

        for item in payload.get("packaging_manifest", []):
            record = self.store.get(channel_id, item["id"], "package_asset")
            verify_package_asset(self, channel_id, record)
            if any(
                record[k] != item[k] for k in ["sha256", "rights", "rights_evidence", "creative_reviewed"]
            ):
                raise CliraError("APPROVAL_INVALIDATED", "Packaging file changed after approval.")
        if payload["body"]["status"]["privacyStatus"] != "private":
            raise CliraError("PRIVATE_REQUIRED", "Uploads must explicitly use private visibility.")
        if isinstance(adapter, DemoYouTube):
            remote_id = "MOCK_" + job_id[-12:]
            result = {
                "video_id": remote_id,
                "privacy_status": "private",
                "channel_id": channel_id,
                "source": "mock",
                "verified_remotely": False,
                "notice": "Simulation only. No YouTube video exists.",
            }
        else:
            checkpoint = self.job(channel_id, job_id).get("result") or {}
            session_ref = "session_" + job_id
            if checkpoint.get("video_id"):
                remote_id = checkpoint["video_id"]
            else:
                if checkpoint.get("stage") == "init_started":
                    raise CliraError(
                        "RECONCILIATION_REQUIRED",
                        "Upload initialization was interrupted before its session was saved.",
                    )
                if checkpoint.get("stage") not in {"session_saved", "uploading"}:
                    self.policy.write_gate(channel_id)
                    self.checkpoint(job_id, {"stage": "init_started"})
                    session = adapter.begin_upload(payload["body"], asset["size"])
                    self.secrets.put(session_ref, {"url": session})
                    self.checkpoint(job_id, {"stage": "session_saved"})
                session = self.secrets.get(session_ref)["url"]
                status = adapter.upload_chunk(session, b"", f"bytes */{asset['size']}")
                if "video" not in status:
                    offset = status["offset"]
                    with Path(asset["path"]).open("rb") as stream:
                        while offset < asset["size"]:
                            self.policy.write_gate(channel_id)
                            stream.seek(offset)
                            content = stream.read(8 * 1024 * 1024)
                            status = adapter.upload_chunk(
                                session,
                                content,
                                f"bytes {offset}-{offset + len(content) - 1}/{asset['size']}",
                            )
                            if "video" in status:
                                break
                            next_offset = status["offset"]
                            if next_offset <= offset or next_offset > asset["size"]:
                                raise CliraError(
                                    "UPLOAD_INTERRUPTED",
                                    "No valid upload progress. Resume the same session later.",
                                    True,
                                )
                            offset = next_offset
                            self.checkpoint(job_id, {"stage": "uploading", "bytes_sent": offset})
                if "video" not in status:
                    raise CliraError(
                        "UPLOAD_INTERRUPTED", "Awaiting server completion. Resume this job to verify.", True
                    )
                remote_id = status["video"]["id"]
                self.checkpoint(job_id, {"stage": "receipt_saved", "video_id": remote_id})
            remote = adapter.video(remote_id)
            if remote["status"]["privacyStatus"] != "private":
                raise CliraError(
                    "RECONCILIATION_REQUIRED",
                    "Remote privacy is not private. Stop and inspect the video immediately.",
                )
            if any(
                remote["snippet"].get(k, [] if k == "tags" else "") != v
                for k, v in payload["body"]["snippet"].items()
            ):
                raise CliraError(
                    "RECONCILIATION_REQUIRED",
                    "Upload exists but metadata differs. Review the stored video receipt.",
                )
            result = {
                "video_id": remote_id,
                "privacy_status": "private",
                "channel_id": channel_id,
                "source": "youtube_data_api",
                "verified_remotely": True,
                "url": "https://www.youtube.com/watch?v=" + remote_id,
                "verified_at": now(),
            }
        self.store.put(
            channel_id,
            "uploaded_video",
            {**result, "asset_id": asset["id"], "ever_published": False, "job_id": job_id},
            "uv_" + digest([channel_id, remote_id]),
        )
        return result

    def run_mutation(self, channel_id, job_id, operation, payload, adapter):
        if operation in {"set_thumbnail", "insert_captions"}:
            from .packaging import verify_package_asset

            record = self.store.get(channel_id, payload["package_asset_id"], "package_asset")
            path = verify_package_asset(self, channel_id, record)
            if any(record[k] != payload[k] for k in ["sha256", "rights", "rights_evidence"]):
                raise CliraError("APPROVAL_INVALIDATED", "Packaging file or rights changed since approval.")
            adapter.video(payload["video_id"])
            self.policy.write_gate(channel_id)
            if isinstance(adapter, DemoYouTube):
                return {
                    "source": "mock",
                    "video_id": payload["video_id"],
                    "operation": operation,
                    "verified_remotely": False,
                    "notice": "Synthetic simulation; nothing uploaded.",
                }
            self.checkpoint(job_id, {"stage": "mutation_started"})
            if operation == "set_thumbnail":
                response = adapter.set_thumbnail(payload["video_id"], path.read_bytes(), payload["mime"])
                receipt = {"items": response.get("items", [])}
                if not receipt["items"]:
                    raise CliraError(
                        "RECONCILIATION_REQUIRED",
                        "Thumbnail response lacked image details; inspect YouTube before retrying.",
                    )
            else:
                response = adapter.insert_captions(
                    payload["video_id"],
                    path.read_bytes(),
                    payload["language"],
                    payload["name"],
                    payload["is_draft"],
                )
                receipt = {
                    "caption_id": response.get("id"),
                    "status": response.get("snippet", {}).get("status"),
                }
                if not receipt["caption_id"]:
                    raise CliraError(
                        "RECONCILIATION_REQUIRED",
                        "Caption response lacked a track ID; inspect YouTube before retrying.",
                    )
            return {
                "source": adapter.source,
                "video_id": payload["video_id"],
                "operation": operation,
                "accepted_by_api": True,
                "verified_remotely": False,
                "notice": "API accepted upload; visual/timed playback verification remains owner review.",
                **receipt,
            }
        if operation == "post_reply":
            if isinstance(adapter, DemoYouTube):
                return {
                    "source": "mock",
                    "comment_id": "MOCK_REPLY_" + job_id[-8:],
                    "verified_remotely": False,
                }
            # Persist intent first. A crash after this point requires manual reconciliation, never a blind repost.
            self.checkpoint(job_id, {"stage": "mutation_started"})
            posted = adapter.post_reply(payload["comment_id"], payload["text"])
            return {"source": adapter.source, "comment_id": posted["id"], "verified_remotely": True}
        if operation not in {"update_metadata", "schedule_video", "publish_now"}:
            raise CliraError("UNKNOWN_OPERATION", "Operation is not allowlisted.")
        video = adapter.video(payload["video_id"])
        part = "snippet" if operation == "update_metadata" else "status"
        if digest(video[part]) != payload["before_hash"]:
            raise CliraError(
                "REMOTE_CHANGED", "YouTube state changed since preview. Prepare a fresh approval."
            )
        if operation == "schedule_video":
            if datetime.fromisoformat(payload["public_at"]) <= datetime.now(UTC):
                raise CliraError(
                    "SCHEDULE_PAST", "Scheduled time has passed. A fresh future approval is required."
                )
            if video["status"]["privacyStatus"] != "private":
                raise CliraError("NOT_PRIVATE", "Scheduling requires a private, never-published video.")
        self.policy.write_gate(channel_id)
        if not isinstance(adapter, DemoYouTube):
            self.checkpoint(job_id, {"stage": "mutation_started"})
            adapter.update(payload["body"], part)
            current = adapter.video(payload["video_id"])
            for key, value in payload["body"][part].items():
                observed = current[part].get(key)
                if key == "publishAt" and observed:
                    observed = datetime.fromisoformat(observed).isoformat()
                if observed != value:
                    raise CliraError(
                        "RECONCILIATION_REQUIRED", "YouTube write receipt needs manual verification."
                    )
        if operation in {"publish_now", "schedule_video"}:
            for tracked in self.store.list(channel_id, "uploaded_video"):
                if tracked["video_id"] == payload["video_id"]:
                    self.store.put(
                        channel_id,
                        "uploaded_video",
                        {**tracked, "ever_published": True, "publication": payload["public_at"]},
                        tracked["id"],
                    )
        return {
            "source": adapter.source,
            "video_id": payload["video_id"],
            "operation": operation,
            "verified_remotely": not isinstance(adapter, DemoYouTube),
        }

    def recover(self):
        jobs = self.store.rows("SELECT * FROM jobs WHERE state='RUNNING' AND lease_until<?", (now(),))
        for job in jobs:
            progress = json.loads(job["result"] or "{}")
            safe = job["operation"] == "upload_private" and progress.get("stage") in {
                "session_saved",
                "uploading",
                "receipt_saved",
            }
            state = "FAILED_RETRYABLE" if safe else "RECOVERY_REQUIRED"
            self.store.execute(
                "UPDATE jobs SET state=?,last_error='LEASE_EXPIRED',lease_until=NULL,updated_at=? WHERE id=?",
                (state, now(), job["id"]),
            )
            self.store.audit(job["channel_id"], "job.recover", state, job["id"])
        return {"recovered": len(jobs)}

    def pause(self, channel_id, job_id):
        job = self.job(channel_id, job_id)
        if job["state"] not in {"QUEUED", "FAILED_RETRYABLE"}:
            raise CliraError("INVALID_TRANSITION", "Only queued or retryable jobs may be paused.")
        self.store.execute("UPDATE jobs SET state='PAUSED',updated_at=? WHERE id=?", (now(), job_id))
        return {"job_id": job_id, "state": "PAUSED"}

    def resume(self, channel_id, job_id):
        job = self.job(channel_id, job_id)
        if job["state"] != "PAUSED":
            raise CliraError("INVALID_TRANSITION", "Only paused jobs may be resumed.")
        self.store.execute("UPDATE jobs SET state='QUEUED',updated_at=? WHERE id=?", (now(), job_id))
        return {"job_id": job_id, "state": "QUEUED"}

    def worker(self):
        self.recover()
        jobs = self.store.rows(
            "SELECT id,channel_id FROM jobs WHERE state IN ('QUEUED','FAILED_RETRYABLE') "
            "AND (next_run_at IS NULL OR next_run_at<=?) ORDER BY created_at",
            (now(),),
        )
        return [
            self.execute_job(j["channel_id"], j["id"])
            for j in jobs
            if self.store.channel(j["channel_id"])["mode"] == self.config.mode
        ]
