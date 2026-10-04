"""
Entry point.

  python run.py                 start the API on http://localhost:8000
  python run.py serve --port 9000
  python run.py demo            run all 5 demo scenarios in the terminal
  python run.py demo failed_verification     run one (normal | high_priority | duplicate |
                                                      failed_verification | max_retry)
  python run.py complaint "Garbage not collected in Gulbahar" --scenario fail_once
"""
import argparse
import sys

SYMBOLS = {"success": "✓", "failed": "✗", "replanning": "↻", "escalated": "⚠", "info": "•"}


def print_result(state) -> None:
    print(f"\n  Complaint {state.complaint_id}: {state.description}")
    print(f"  category={state.category} ({state.subcategory}) | area={state.area} ({state.zone}) | "
          f"priority={state.priority} | dept={state.department}")
    if state.duplicate:
        print(f"  duplicate of #{state.related_complaint_id}")
    print("\n  Agent Activity Timeline")
    for h in state.history:
        print(f"   {SYMBOLS.get(h.status, '•')} {h.message:<38} [{h.agent}] {h.result}")
    print(f"\n  FINAL: status={state.status} resolved={state.resolved} team={state.assigned_team} "
          f"retries={state.retry_count}/{state.max_retries}")
    if state.escalation_reason:
        print(f"  escalation: {state.escalation_reason}")
    for e in state.errors:
        print(f"  ! {e}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):          # Windows consoles: allow ✓ ✗ ↻
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Municipal Complaint Resolution Agent")
    sub = parser.add_subparsers(dest="cmd")
    p_serve = sub.add_parser("serve", help="start the FastAPI server (default)")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_demo = sub.add_parser("demo", help="run demo scenarios in the terminal")
    p_demo.add_argument("name", nargs="?", default="all")
    p_c = sub.add_parser("complaint", help="process one complaint from the command line")
    p_c.add_argument("text")
    p_c.add_argument("--location", default=None)
    p_c.add_argument("--scenario", default=None, help="success | fail_once | fail_twice | fail_<n> | always_fail")
    args = parser.parse_args()

    from app.data.mock_data import DEMO_SCENARIOS
    from app.graph.workflow import process_complaint

    # Integrated mode: use the Database Backend (set DB_BACKEND_URL in .env). Without it, the in-memory mock is used.
    from app.data.http_repository import configure_from_env
    configure_from_env()

    if args.cmd == "demo":
        chosen = [s for s in DEMO_SCENARIOS if args.name in ("all", s["key"])]
        if not chosen:
            sys.exit(f"Unknown demo '{args.name}'. Options: all, " + ", ".join(s["key"] for s in DEMO_SCENARIOS))
        for s in chosen:
            print("\n" + "=" * 78 + f"\n{s['title']}\n" + "=" * 78)
            print_result(process_complaint(**s["request"]))
    elif args.cmd == "complaint":
        print_result(process_complaint("CLI-1", args.text, args.location, args.scenario))
    else:  # serve (default)
        import uvicorn
        uvicorn.run("app.main:app", host=getattr(args, "host", "0.0.0.0"),
                    port=getattr(args, "port", 8000), reload=False)


if __name__ == "__main__":
    main()
