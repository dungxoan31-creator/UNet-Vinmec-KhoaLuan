"""
KPI calculation service and report generator.
Calculates T_total, N_actions, and N_fields_manual from ui_events telemetry table.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.db.database import SessionLocal, UIEventModel


def calculate_case_kpis(db: Session, case_id: str) -> dict[str, Any]:
    events = (
        db.query(UIEventModel)
        .filter(UIEventModel.case_id == case_id)
        .order_by(UIEventModel.t_ms.asc())
        .all()
    )
    if not events:
        return {
            "case_id": case_id,
            "t_total_sec": 0.0,
            "n_actions": 0,
            "n_fields_manual": 0,
            "events_count": 0,
        }

    start_t = events[0].t_ms
    # Find print_click or sign_click or last event
    end_t = events[-1].t_ms
    for ev in events:
        if ev.event_type in ("print_click", "sign_click"):
            end_t = ev.t_ms
            break

    t_total_sec = max(0.0, (end_t - start_t) / 1000.0)
    n_actions = len(events)
    manual_fields = set()
    for ev in events:
        if ev.event_type == "field_edit":
            payload = ev.payload_json or {}
            if payload.get("source") == "manual" or payload.get("source") is None:
                manual_fields.add(payload.get("field", "unknown"))

    return {
        "case_id": case_id,
        "t_total_sec": round(t_total_sec, 2),
        "n_actions": n_actions,
        "n_fields_manual": len(manual_fields),
        "events_count": len(events),
    }


def generate_kpi_summary(db: Session) -> dict[str, Any]:
    # Distinct cases
    cases = db.query(UIEventModel.case_id).filter(UIEventModel.case_id.isnot(None)).distinct().all()
    case_ids = [c[0] for c in cases if c[0]]

    if not case_ids:
        return {
            "total_cases": 0,
            "avg_t_total_sec": 0.0,
            "avg_n_actions": 0.0,
            "avg_n_fields_manual": 0.0,
            "case_summaries": [],
        }

    summaries = [calculate_case_kpis(db, cid) for cid in case_ids]
    avg_t = sum(s["t_total_sec"] for s in summaries) / len(summaries)
    avg_actions = sum(s["n_actions"] for s in summaries) / len(summaries)
    avg_fields = sum(s["n_fields_manual"] for s in summaries) / len(summaries)

    return {
        "total_cases": len(summaries),
        "avg_t_total_sec": round(avg_t, 2),
        "avg_n_actions": round(avg_actions, 1),
        "avg_n_fields_manual": round(avg_fields, 1),
        "case_summaries": summaries,
    }


def format_kpi_markdown_table(summary: dict[str, Any]) -> str:
    lines = [
        "# BÁO CÁO KPI GIAO DIỆN & VẬN HÀNH LÂM SÀNG (TELEMETRY KPI REPORT)",
        "",
        f"- **Tổng số ca ghi nhận:** {summary['total_cases']}",
        f"- **Thời gian trung bình (T_total):** {summary['avg_t_total_sec']} giây/ca",
        f"- **Số thao tác trung bình (N_actions):** {summary['avg_n_actions']} thao tác/ca",
        f"- **Số trường nhập tay trung bình (N_fields_manual):** {summary['avg_n_fields_manual']} trường/ca",
        "",
        "| Mã ca (Case ID) | T_total (giây) | N_actions | N_fields_manual | Tổng sự kiện |",
        "|---|---|---|---|---|",
    ]
    for s in summary.get("case_summaries", []):
        lines.append(
            f"| `{s['case_id'][:8]}...` | {s['t_total_sec']}s | {s['n_actions']} | {s['n_fields_manual']} | {s['events_count']} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    with SessionLocal() as db:
        summary = generate_kpi_summary(db)
        print(format_kpi_markdown_table(summary))
