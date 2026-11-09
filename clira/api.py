import json
import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent import Agent
from .config import CliraError
from .contracts import (
    ApprovalDecision,
    ChatRequest,
    CopyWorkspace,
    ExecuteJob,
    LaunchRequest,
    Profile,
    SessionRequest,
    ToolRequest,
    tool_contracts,
)
from .service import Service
from .storage import encode, now


def create_app(service=None):
    service = service or Service()
    app = FastAPI(title=service.config.display_name, docs_url=None, redoc_url=None)
    from .connections import Connections

    app.state.connections = Connections(service)
    app.state.service = service
    app.state.csrf = secrets.token_urlsafe(32)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])

    @app.middleware("http")
    async def protect(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"error": {"code": "ORIGIN_BLOCKED", "message": "Same-origin access required."}},
                status_code=403,
            )
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            token = request.headers.get("x-clira-token", "")
            if not secrets.compare_digest(token, app.state.csrf):
                return JSONResponse(
                    {"error": {"code": "CSRF", "message": "Reload the local dashboard."}}, status_code=403
                )
            if len(await request.body()) > 1024 * 1024:
                return JSONResponse(
                    {"error": {"code": "BODY_LIMIT", "message": "Request too large."}}, status_code=413
                )
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse(
                    {"error": {"code": "CONTENT_TYPE", "message": "Use application/json."}}, status_code=415
                )
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(CliraError)
    async def domain_error(request, exc):
        return JSONResponse(exc.envelope(), status_code=400)

    @app.get("/api/session")
    def session():
        return {
            "token": app.state.csrf,
            "name": service.config.display_name,
            "mode": service.config.mode,
            "model": service.config.model,
            "model_calls_enabled": service.config.allow_model_calls,
            "writes_enabled": service.config.enable_writes,
            "import_dir": str(service.config.import_dir),
            "paused": service.store.setting("paused", False),
            "channels": service.channels(),
        }

    @app.get("/api/state/{channel_id}")
    def state(channel_id: str):
        service.policy.channel(channel_id)
        approvals = service.store.rows(
            "SELECT * FROM approvals WHERE channel_id=? ORDER BY created_at DESC", (channel_id,)
        )
        for approval in approvals:
            approval["payload"] = json.loads(approval["payload"])
        return {
            "channel": next(c for c in service.channels() if c["id"] == channel_id),
            "records": {
                kind: service.store.list(channel_id, kind)
                for kind in [
                    "idea",
                    "brief",
                    "metadata",
                    "calendar",
                    "asset",
                    "analytics",
                    "comment",
                    "reply",
                    "uploaded_video",
                    "video_cache",
                    "package_asset",
                    "launch",
                ]
            },
            "approvals": approvals,
            "jobs": service.tool_list_jobs(channel_id, None)["jobs"],
            "audit": service.store.rows(
                "SELECT * FROM audit_events WHERE channel_id=? ORDER BY seq DESC LIMIT 100", (channel_id,)
            ),
        }

    @app.post("/api/connect/start")
    def start_connection():
        return app.state.connections.start()

    @app.get("/api/connect/status")
    def connection_status():
        return app.state.connections.status()

    @app.post("/api/connect/{connection_id}/confirm")
    def confirm_connection(connection_id: str, body: ExecuteJob):
        return app.state.connections.confirm(connection_id, body.channel_id)

    @app.get("/api/tools")
    def contracts():
        return tool_contracts()

    @app.post("/api/chat")
    def chat(body: ChatRequest):
        return Agent(service).chat(body.channel_id, body.message, body.conversation_id)

    @app.post("/api/tool")
    def tool(body: ToolRequest):
        return service.tool(body.channel_id, body.tool, body.arguments)

    @app.post("/api/approvals/{approval_id}")
    def decide(approval_id: str, body: ApprovalDecision):
        return service.policy.decide(body.channel_id, approval_id, body.approve)

    @app.post("/api/jobs/{job_id}/run")
    def execute(job_id: str, body: ExecuteJob):
        return service.execute_job(body.channel_id, job_id)

    @app.post("/api/approvals/{approval_id}/renew")
    def renew(approval_id: str, body: ExecuteJob):
        return service.policy.renew(body.channel_id, approval_id)

    @app.post("/api/jobs/{job_id}/{action}")
    def job_action(job_id: str, action: str, body: ExecuteJob):
        if action not in {"pause", "resume"}:
            raise CliraError("UNKNOWN_ACTION", "Use pause or resume.")
        return getattr(service, action)(body.channel_id, job_id)

    @app.put("/api/profile/{channel_id}")
    def profile(channel_id: str, body: Profile):
        service.policy.channel(channel_id)
        service.store.execute(
            "UPDATE channels SET profile=? WHERE id=?", (encode(body.model_dump()), channel_id)
        )
        service.store.audit(channel_id, "profile.update", "saved")
        return {"ok": True}

    @app.post("/api/pause")
    def pause_all():
        service.store.set_setting("paused", True)
        service.store.audit(None, "writes.pause", "paused")
        return {"paused": True}

    @app.post("/api/unpause")
    def unpause_all():
        service.store.set_setting("paused", False)
        service.store.audit(None, "writes.pause", "unpaused")
        return {"paused": False}

    @app.get("/api/conversations/{channel_id}")
    def conversations(channel_id: str):
        service.policy.channel(channel_id)
        return service.store.sessions(channel_id)

    @app.post("/api/conversations")
    def new_conversation(body: SessionRequest):
        service.policy.channel(body.channel_id)
        return service.store.new_session(body.channel_id, body.title)

    @app.get("/api/conversations/{channel_id}/{conversation_id}")
    def conversation(channel_id: str, conversation_id: str):
        service.policy.channel(channel_id)
        return service.store.session(channel_id, conversation_id)

    @app.put("/api/conversations/{conversation_id}")
    def title_conversation(conversation_id: str, body: SessionRequest):
        service.policy.channel(body.channel_id)
        return service.store.title_session(body.channel_id, conversation_id, body.title)

    @app.post("/api/workspaces")
    def launch_workspace(body: LaunchRequest):
        from .workspaces import launch

        result = launch(service, **body.model_dump())
        # Never return credential-bearing channel rows.
        return {
            "workspace": next(c for c in service.channels() if c["id"] == result["workspace"]["id"]),
            "plan": result["plan"],
        }

    @app.post("/api/workspaces/copy")
    def copy_workspace(body: CopyWorkspace):
        from .workspaces import copy_drafts

        return copy_drafts(service, body.workspace_id, body.channel_id, body.confirmation)

    @app.get("/api/preview/{channel_id}/{asset_id}")
    def preview(channel_id: str, asset_id: str):
        from .packaging import verify_package_asset

        service.policy.channel(channel_id)
        record = service.store.get(channel_id, asset_id, "package_asset")
        path = verify_package_asset(service, channel_id, record, reviewed=False)
        return FileResponse(path, media_type=record["mime"], headers={"Content-Disposition": "inline"})

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "mode": service.config.mode,
            "at": now(),
            "store_id": service.store.setting("store_id"),
        }

    web = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web), name="static")

    @app.get("/")
    def home():
        return FileResponse(web / "index.html")

    return app
