import json
from datetime import UTC, datetime, timedelta

from .config import CliraError
from .storage import digest, encode, now, uid


class Policy:
    def __init__(self, config, store):
        self.config, self.store = config, store

    def channel(self, channel_id):
        channel = self.store.channel(channel_id)
        if channel["mode"] not in {self.config.mode, "draft"}:
            raise CliraError(
                "MODE_MISMATCH", "Channel belongs to another execution mode. Switch mode explicitly."
            )
        return channel

    def write_gate(self, channel_id):
        channel = self.channel(channel_id)
        if channel["mode"] == "draft":
            raise CliraError(
                "DRAFT_ONLY",
                "Local launch workspaces cannot perform account actions. Connect a real channel first.",
            )
        if self.store.setting("paused", False):
            raise CliraError("WRITES_PAUSED", "All external writes are paused.")
        if channel["mode"] == "live" and not self.config.enable_writes:
            raise CliraError(
                "WRITES_DISABLED",
                "Advisor mode. Set CLIRA_ENABLE_WRITES=1 explicitly to enable approved writes.",
            )
        return channel

    def prepare(self, channel_id, operation, payload, idempotency_key=None):
        self.channel(channel_id)
        fingerprint = digest(
            {"channel_id": channel_id, "operation": operation, "payload": payload, "mode": self.config.mode}
        )
        key = idempotency_key or fingerprint
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
            if old:
                prior = db.execute("SELECT * FROM approvals WHERE id=?", (old["approval_id"],)).fetchone()
                replaceable = not old["result"] and old["state"] in {
                    "AWAITING_APPROVAL",
                    "QUEUED",
                    "CANCELLED",
                    "PAUSED",
                    "FAILED_TERMINAL",
                }
                needs_refresh = (
                    prior["payload_hash"] != fingerprint
                    or prior["expires_at"] <= now()
                    or prior["status"] == "REJECTED"
                    or old["state"] == "FAILED_TERMINAL"
                )
                if not (replaceable and needs_refresh):
                    return {
                        "job_id": old["id"],
                        "approval_id": old["approval_id"],
                        "state": old["state"],
                        "duplicate": True,
                    }
                # With no saved external-write intent, re-prepare with fresh consent.
                db.execute("UPDATE approvals SET status='SUPERSEDED' WHERE id=?", (old["approval_id"],))
            approval_id, job_id = uid("approval"), uid("job")
            expires = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
            db.execute(
                "INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    approval_id,
                    channel_id,
                    operation,
                    encode(payload),
                    fingerprint,
                    "PENDING",
                    now(),
                    expires,
                    None,
                    None,
                ),
            )
            # Explicit columns avoid silently relying on table field order for durable jobs.
            if old:
                job_id = old["id"]
                db.execute(
                    "UPDATE jobs SET operation=?,payload=?,approval_id=?,state='AWAITING_APPROVAL',attempts=0,last_error=NULL,updated_at=? WHERE id=?",
                    (operation, encode(payload), approval_id, now(), job_id),
                )
            else:
                db.execute(
                    "INSERT INTO jobs(id,channel_id,operation,payload,approval_id,state,idempotency_key,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,'AWAITING_APPROVAL',?,?,?)",
                    (job_id, channel_id, operation, encode(payload), approval_id, key, now(), now()),
                )
        self.store.audit(channel_id, operation, "approval_requested", job_id, {"payload_hash": fingerprint})
        return {
            "job_id": job_id,
            "approval_id": approval_id,
            "state": "AWAITING_APPROVAL",
            "preview": payload,
            "expires_at": expires,
        }

    def decide(self, channel_id, approval_id, approve):
        self.channel(channel_id)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM approvals WHERE id=? AND channel_id=?", (approval_id, channel_id)
            ).fetchone()
            if not row or row["status"] != "PENDING":
                raise CliraError(
                    "INVALID_APPROVAL",
                    "Approval is missing, belongs to another channel, or is no longer pending.",
                )
            if row["expires_at"] <= now():
                raise CliraError("APPROVAL_EXPIRED", "This request expired. Prepare a fresh action.")
            db.execute(
                "UPDATE approvals SET status=?,approved_by='owner' WHERE id=?",
                ("APPROVED" if approve else "REJECTED", approval_id),
            )
            db.execute(
                "UPDATE jobs SET state=?,updated_at=? WHERE approval_id=?",
                ("QUEUED" if approve else "CANCELLED", now(), approval_id),
            )
        self.store.audit(channel_id, row["operation"], "approved" if approve else "rejected", approval_id)
        return {"approval_id": approval_id, "status": "APPROVED" if approve else "REJECTED"}

    def claim(self, channel_id, job_id):
        self.write_gate(channel_id)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE id=? AND channel_id=?", (job_id, channel_id)
            ).fetchone()
            if not row:
                raise CliraError("NOT_FOUND", "Job not found in this channel.")
            job = dict(row)
            if job["state"] == "COMPLETED":
                return job
            if job["state"] not in {"QUEUED", "FAILED_RETRYABLE"}:
                raise CliraError("JOB_NOT_RUNNABLE", f"Job is {job['state']}; no action was taken.")
            if job["next_run_at"] and job["next_run_at"] > now():
                raise CliraError("RETRY_NOT_DUE", "Retry backoff is still active.")
            if job["attempts"] >= 5:
                raise CliraError("RETRY_LIMIT", "Retry cap reached. Review this job manually.")
            approval = db.execute(
                "SELECT * FROM approvals WHERE id=? AND channel_id=?", (job["approval_id"], channel_id)
            ).fetchone()
            expected = digest(
                {
                    "channel_id": channel_id,
                    "operation": job["operation"],
                    "payload": json.loads(job["payload"]),
                    "mode": self.config.mode,
                }
            )
            if (
                not approval
                or approval["payload_hash"] != expected
                or approval["expires_at"] <= now()
                or approval["status"] not in {"APPROVED", "USED"}
            ):
                raise CliraError("APPROVAL_REQUIRED", "Valid exact-payload owner approval required.")
            if approval["status"] == "USED" and job["attempts"] == 0:
                raise CliraError("APPROVAL_USED", "Approval cannot be reused for a different job.")
            if db.execute(
                "SELECT 1 FROM jobs WHERE channel_id=? AND state='RUNNING'", (channel_id,)
            ).fetchone():
                raise CliraError("CHANNEL_BUSY", "Another channel write is running.")
            lease = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
            db.execute(
                "UPDATE jobs SET state='RUNNING',attempts=attempts+1,lease_until=?,updated_at=? WHERE id=?",
                (lease, now(), job_id),
            )
            db.execute(
                "UPDATE approvals SET status='USED',used_at=COALESCE(used_at,?) WHERE id=?",
                (now(), approval["id"]),
            )
            job["state"], job["attempts"] = "RUNNING", job["attempts"] + 1
        return job

    def renew(self, channel_id, approval_id):
        """Owner-only renewal of the SAME job/payload, including a saved resumable session."""
        self.channel(channel_id)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT * FROM approvals WHERE id=? AND channel_id=?", (approval_id, channel_id)
            ).fetchone()
            job = db.execute(
                "SELECT * FROM jobs WHERE approval_id=? AND channel_id=?", (approval_id, channel_id)
            ).fetchone()
            if (
                not prior
                or not job
                or job["state"] not in {"AWAITING_APPROVAL", "QUEUED", "FAILED_RETRYABLE", "PAUSED"}
            ):
                raise CliraError(
                    "RENEWAL_BLOCKED", "This action cannot be renewed. Reconcile unknown outcomes first."
                )
            fresh = uid("approval")
            expires = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
            db.execute("UPDATE approvals SET status='SUPERSEDED' WHERE id=?", (approval_id,))
            db.execute(
                "INSERT INTO approvals VALUES(?,?,?,?,?,'PENDING',?,?,NULL,NULL)",
                (
                    fresh,
                    channel_id,
                    prior["operation"],
                    prior["payload"],
                    prior["payload_hash"],
                    now(),
                    expires,
                ),
            )
            db.execute(
                "UPDATE jobs SET approval_id=?,state='AWAITING_APPROVAL',updated_at=? WHERE id=?",
                (fresh, now(), job["id"]),
            )
        self.store.audit(channel_id, "approval.renew", "pending_fresh_consent", fresh)
        return {"approval_id": fresh, "job_id": job["id"], "status": "PENDING"}
