import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

from .agent import Agent
from .config import CliraError, Config
from .creator import model_key
from .service import Service
from .storage import encode
from .text import terminal_text
from .youtube import connect


def show(value):
    print(terminal_text(json.dumps(value, indent=2, ensure_ascii=False)))


def doctor(service):
    config = service.config
    return {
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "mode": config.mode,
        "database": str(service.store.path),
        "migration_version": service.store.rows("SELECT MAX(version) AS version FROM migrations")[0][
            "version"
        ],
        "ffprobe": shutil.which("ffprobe"),
        "disk_free_bytes": shutil.disk_usage(config.data_dir).free,
        "model": config.model,
        "model_id": config.model_id,
        "model_key_present": bool(model_key(service)),
        "model_calls_authorized": config.allow_model_calls,
        "max_model_calls_day": config.max_model_calls_day,
        "oauth_client_configured": bool(os.getenv("CLIRA_GOOGLE_CLIENT_FILE")),
        "channels": service.channels(),
        "writes_enabled": config.enable_writes,
        "paused": service.store.setting("paused", False),
        "import_dir": str(config.import_dir),
        "legacy_studio": "available"
        if (Path.home() / "youtube-studio").is_dir()
        else "missing_or_broken_link",
        "external_lemo": "present_unintegrated" if (Path.home() / "lemo-opuscar").is_dir() else "absent",
        "editorial_utilities": str(Path.home() / ".gemini/config/plugins/youtube-agent/skills"),
    }


def main():
    parser = argparse.ArgumentParser(
        prog="clira", description="Storytelling meets strategic wisdom · local YouTube agent"
    )
    parser.add_argument("--mode", choices=["demo", "live"])
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--version", action="version", version=__import__("clira").__version__)
    parser.add_argument("--channel")
    parser.add_argument("--resume")
    parser.add_argument("--no-logo", action="store_true")
    parser.add_argument(
        "--quickstart", action="store_true", help="Skip personal setup for a temporary/demo session"
    )
    sub = parser.add_subparsers(dest="command")
    tg = sub.add_parser("telegram", help="Run your explicitly paired personal bot")
    tg.add_argument("action", choices=["run", "pair", "disconnect"])
    sub.add_parser("doctor")
    sub.add_parser("channels")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    auth = sub.add_parser("connect")
    auth.add_argument("--capability", choices=["read", "upload", "manage"], default="read")
    auth.add_argument("--client-file")
    chat = sub.add_parser("chat")
    chat.add_argument("message", nargs="?")
    chat.add_argument("--channel")
    chat.add_argument("--json", action="store_true")
    chat.add_argument("--resume")
    tool = sub.add_parser("tool")
    tool.add_argument("name")
    tool.add_argument("--channel", required=True)
    tool.add_argument("--json", default="{}", help="JSON input; use @file.json for private/long payloads")
    for cmd in ["analytics", "ideas"]:
        child = sub.add_parser(cmd)
        child.add_argument("--channel", required=True)
        if cmd == "analytics":
            child.add_argument("--days", type=int, default=28)
    approval = sub.add_parser("approval")
    approval.add_argument("action", choices=["show", "approve", "reject", "renew"])
    approval.add_argument("approval_id")
    approval.add_argument("--channel", required=True)
    approval.add_argument(
        "--yes", action="store_true", help="Approve the displayed exact payload noninteractively as owner"
    )
    jobs = sub.add_parser("jobs")
    jobs.add_argument("action", choices=["list", "get", "run", "pause", "resume"])
    jobs.add_argument("job_id", nargs="?")
    jobs.add_argument("--channel", required=True)
    sub.add_parser("worker", help="Run due, already owner-approved jobs once; no timers installed")
    sub.add_parser("recover", help="Recover expired leases conservatively")
    sub.add_parser("pause-all")
    sub.add_parser("resume-all")
    backup = sub.add_parser("backup")
    backup.add_argument("destination", type=Path)
    disconnect = sub.add_parser("disconnect")
    disconnect.add_argument("--channel", required=True)
    args = parser.parse_args()
    kwargs = {k: v for k, v in [("mode", args.mode), ("data_dir", args.data_dir)] if v is not None}
    try:
        service = Service(Config(**kwargs))
        from .creator import load_runtime

        load_runtime(service)
        if args.command is None:
            from .tui.app import Terminal

            return Terminal(service, args.channel, args.resume, args.no_logo, args.quickstart).run()
        if args.command == "telegram":
            from .telegram import Telegram, pairing_code

            if args.action == "pair":
                print("Privately send /pair " + pairing_code(service) + " to your bot within ten minutes.")
            elif args.action == "disconnect":
                service.secrets.delete("telegram")
                for key in ["telegram_owner", "telegram_pair"]:
                    service.store.set_setting(key, {})
                print(
                    "Telegram credentials and pairing removed locally. Revoke the token with BotFather if needed."
                )
            else:
                channel = args.channel or service.store.setting("active_workspace:" + service.config.mode)
                if not channel:
                    raise CliraError(
                        "CHANNEL_REQUIRED", "Complete setup or select --channel before starting the bot."
                    )
                print(
                    "Clira personal Telegram transport is running. Ctrl+C stops it; device must stay online."
                )
                Telegram(service, channel).run()
        elif args.command == "doctor":
            show(doctor(service))
        elif args.command == "channels":
            show(service.channels())
        elif args.command == "serve":
            import uvicorn

            from .api import create_app

            print(f"{service.config.display_name} · {service.config.mode} · http://127.0.0.1:{args.port}")
            uvicorn.run(create_app(service), host="127.0.0.1", port=args.port, access_log=False)
        elif args.command == "connect":
            if service.config.mode != "live":
                raise CliraError(
                    "LIVE_MODE_REQUIRED",
                    "Use clira --mode live connect; demo never accesses Google credentials.",
                )
            show(connect(service.config, service.store, service.secrets, args.capability, args.client_file))
        elif args.command == "chat":
            args.channel = args.channel or service.store.setting("active_workspace:" + service.config.mode)
            if not args.channel:
                raise CliraError(
                    "CHANNEL_REQUIRED", "Select a workspace with bare clira or pass --channel ID."
                )
            if not args.message and not sys.stdin.isatty():
                args.message = sys.stdin.read(12001).strip()
                if not args.message or len(args.message) > 12000:
                    raise CliraError("MESSAGE_REQUIRED", "Provide a message of 1–12000 characters.")
            if args.message:
                result = Agent(service).chat(args.channel, args.message, args.resume)
                if args.json:
                    show(result)
                else:
                    print(terminal_text(result["message"]))
                    print("Session: " + result["conversation_id"])
            else:
                from .tui.app import Terminal

                return Terminal(service, args.channel, args.resume, args.no_logo, args.quickstart).run()
        elif args.command == "tool":
            raw = Path(args.json[1:]).read_text() if args.json.startswith("@") else args.json
            result = service.tool(args.channel, args.name, json.loads(raw))
            show(result)
            if not result["ok"]:
                sys.exit(1)
        elif args.command in {"analytics", "ideas"}:
            show(
                service.tool(args.channel, "channel_report", {"days": args.days})
                if args.command == "analytics"
                else Agent(service).chat(args.channel, "Suggest three new topic ideas for this channel")
            )
        elif args.command == "approval":
            service.policy.channel(args.channel)
            rows = service.store.rows(
                "SELECT * FROM approvals WHERE id=? AND channel_id=?", (args.approval_id, args.channel)
            )
            if not rows:
                raise CliraError("NOT_FOUND", "Approval not found in this channel.")
            preview = {**rows[0], "payload": json.loads(rows[0]["payload"])}
            show(preview)
            if args.action == "renew":
                show(service.policy.renew(args.channel, args.approval_id))
            elif args.action != "show":
                approve = args.action == "approve"
                if (
                    approve
                    and not args.yes
                    and input("Approve exactly this action? Type APPROVE: ") != "APPROVE"
                ):
                    raise CliraError("NOT_CONFIRMED", "Approval was not granted.")
                show(service.policy.decide(args.channel, args.approval_id, approve))
        elif args.command == "jobs":
            if args.action == "list":
                show(service.tool_list_jobs(args.channel, None))
            elif not args.job_id:
                parser.error("job_id required")
            else:
                method = {
                    "get": service.job,
                    "run": service.execute_job,
                    "pause": service.pause,
                    "resume": service.resume,
                }[args.action]
                result = method(args.channel, args.job_id)
                show(result)
                if result.get("ok") is False:
                    sys.exit(1)
        elif args.command == "worker":
            show(service.worker())
        elif args.command == "recover":
            show(service.recover())
        elif args.command in {"pause-all", "resume-all"}:
            paused = args.command == "pause-all"
            service.store.set_setting("paused", paused)
            service.store.audit(None, "writes.pause", "paused" if paused else "unpaused")
            show({"paused": paused})
        elif args.command == "backup":
            with service.store.connect() as source, sqlite3.connect(args.destination) as target:
                source.backup(target)
            args.destination.chmod(0o600)
            show(
                {
                    "backup": str(args.destination.resolve()),
                    "includes_secrets": False,
                    "includes_assets": False,
                }
            )
        elif args.command == "disconnect":
            channel = service.policy.channel(args.channel)
            ref = channel["connection"].get("secret_ref")
            if ref:
                service.secrets.delete(ref)
            service.store.execute("UPDATE channels SET connection=? WHERE id=?", (encode({}), args.channel))
            service.store.audit(args.channel, "oauth.disconnect", "local_credentials_removed")
            show({"disconnected_locally": True, "revoke_url": "https://myaccount.google.com/permissions"})
    except CliraError as exc:
        show(exc.envelope())
        sys.exit(1)
    except (OSError, ValueError):
        show(
            {
                "ok": False,
                "error": {
                    "code": "LOCAL_INPUT",
                    "message": "Invalid input or inaccessible local file. Check arguments and permissions.",
                },
            }
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
