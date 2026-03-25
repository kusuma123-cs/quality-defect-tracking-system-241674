from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, status

from src.api.constants import ACTIVE_DEFECT_STATUSES, DefectStatus, Severity
from src.api.utils import row_to_dict, utc_now_iso


def _dt_from_iso(value: str | None) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _date_from_iso(value: str | None) -> Optional[date]:
    if value is None or value == "":
        return None
    return date.fromisoformat(value)


def _ensure_defect_exists(conn: sqlite3.Connection, defect_id: int) -> None:
    row = conn.execute("SELECT id FROM defects WHERE id = ?", (defect_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defect not found")


def list_defects(
    conn: sqlite3.Connection,
    *,
    q: Optional[str],
    status: Optional[DefectStatus],
    severity: Optional[Severity],
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> tuple[list[dict[str, Any]], int]:
    where = []
    params: list[Any] = []

    if q:
        where.append("(title LIKE ? OR description LIKE ? OR root_cause LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if status:
        where.append("status = ?")
        params.append(status.value)
    if severity:
        where.append("severity = ?")
        params.append(severity.value)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sort_allowed = {"created_at", "updated_at", "due_date", "severity", "status"}
    sort_key = sort if sort in sort_allowed else "updated_at"
    order_sql = "ASC" if order == "asc" else "DESC"

    total = conn.execute(f"SELECT COUNT(1) as c FROM defects{where_sql}", params).fetchone()["c"]

    rows = conn.execute(
        f"""
        SELECT *
        FROM defects
        {where_sql}
        ORDER BY {sort_key} {order_sql}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()

    return [row_to_dict(r) for r in rows], int(total)


def get_defect(conn: sqlite3.Connection, defect_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defect not found")
    data = row_to_dict(row)
    # Images
    images = conn.execute(
        "SELECT * FROM defect_images WHERE defect_id = ? ORDER BY created_at DESC", (defect_id,)
    ).fetchall()
    data["images"] = [row_to_dict(r) for r in images]
    # Actions counts
    counts = conn.execute(
        """
        SELECT
          SUM(CASE WHEN status IN ('open','in_progress') THEN 1 ELSE 0 END) AS open_count,
          COUNT(1) AS total_count
        FROM corrective_actions
        WHERE defect_id = ?
        """,
        (defect_id,),
    ).fetchone()
    data["actions_open"] = int(counts["open_count"] or 0)
    data["actions_total"] = int(counts["total_count"] or 0)
    return data


def create_defect(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO defects (title, description, severity, status, area, location, reported_by, assigned_to, root_cause, due_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["title"],
            payload["description"],
            payload["severity"],
            payload["status"],
            payload.get("area"),
            payload.get("location"),
            payload.get("reported_by"),
            payload.get("assigned_to"),
            payload.get("root_cause"),
            payload.get("due_date"),
            now,
            now,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_defect(conn: sqlite3.Connection, defect_id: int, updates: dict[str, Any]) -> None:
    _ensure_defect_exists(conn, defect_id)
    if not updates:
        return
    updates["updated_at"] = utc_now_iso()

    cols = []
    params = []
    for k, v in updates.items():
        cols.append(f"{k} = ?")
        params.append(v)
    params.append(defect_id)
    conn.execute(f"UPDATE defects SET {', '.join(cols)} WHERE id = ?", params)
    conn.commit()


def delete_defect(conn: sqlite3.Connection, defect_id: int) -> None:
    _ensure_defect_exists(conn, defect_id)
    conn.execute("DELETE FROM defects WHERE id = ?", (defect_id,))
    conn.commit()


def list_actions(conn: sqlite3.Connection, *, defect_id: Optional[int], include_done: bool) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if defect_id is not None:
        where.append("defect_id = ?")
        params.append(defect_id)
    if not include_done:
        where.append("status NOT IN ('done','canceled')")

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM corrective_actions{where_sql} ORDER BY due_date ASC, updated_at DESC", params
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def create_action(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    _ensure_defect_exists(conn, int(payload["defect_id"]))
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO corrective_actions (defect_id, title, description, owner, status, due_date, completed_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["defect_id"],
            payload["title"],
            payload.get("description"),
            payload.get("owner"),
            payload["status"],
            payload.get("due_date"),
            payload.get("completed_at"),
            now,
            now,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_action(conn: sqlite3.Connection, action_id: int, updates: dict[str, Any]) -> None:
    row = conn.execute("SELECT id FROM corrective_actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrective action not found")
    if not updates:
        return
    updates["updated_at"] = utc_now_iso()

    cols = []
    params = []
    for k, v in updates.items():
        cols.append(f"{k} = ?")
        params.append(v)
    params.append(action_id)
    conn.execute(f"UPDATE corrective_actions SET {', '.join(cols)} WHERE id = ?", params)
    conn.commit()


def delete_action(conn: sqlite3.Connection, action_id: int) -> None:
    row = conn.execute("SELECT id FROM corrective_actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corrective action not found")
    conn.execute("DELETE FROM corrective_actions WHERE id = ?", (action_id,))
    conn.commit()


def insert_image_record(
    conn: sqlite3.Connection,
    *,
    defect_id: int,
    file_name: Optional[str],
    content_type: str,
    storage_path: str,
    created_at: str,
) -> int:
    _ensure_defect_exists(conn, defect_id)
    cur = conn.execute(
        """
        INSERT INTO defect_images (defect_id, file_name, content_type, storage_path, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (defect_id, file_name, content_type, storage_path, created_at),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_image_record(conn: sqlite3.Connection, image_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM defect_images WHERE id = ?", (image_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return row_to_dict(row)


def dashboard_counts(conn: sqlite3.Connection) -> dict[str, Any]:
    by_status_rows = conn.execute("SELECT status, COUNT(1) as c FROM defects GROUP BY status").fetchall()
    by_sev_rows = conn.execute("SELECT severity, COUNT(1) as c FROM defects GROUP BY severity").fetchall()

    by_status = {r["status"]: int(r["c"]) for r in by_status_rows}
    by_severity = {r["severity"]: int(r["c"]) for r in by_sev_rows}

    open_defects = conn.execute(
        f"SELECT COUNT(1) as c FROM defects WHERE status IN ({','.join(['?'] * len(ACTIVE_DEFECT_STATUSES))})",
        [s.value for s in ACTIVE_DEFECT_STATUSES],
    ).fetchone()["c"]

    overdue_actions = conn.execute(
        """
        SELECT COUNT(1) as c
        FROM corrective_actions
        WHERE due_date IS NOT NULL
          AND status NOT IN ('done','canceled')
          AND date(due_date) < date('now')
        """
    ).fetchone()["c"]

    return {
        "by_status": by_status,
        "by_severity": by_severity,
        "open_defects": int(open_defects),
        "overdue_actions": int(overdue_actions),
    }


def overdue_alerts(conn: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          a.id AS action_id,
          a.defect_id AS defect_id,
          a.title AS title,
          a.owner AS owner,
          a.due_date AS due_date,
          d.title AS defect_title
        FROM corrective_actions a
        JOIN defects d ON d.id = a.defect_id
        WHERE a.due_date IS NOT NULL
          AND a.status NOT IN ('done','canceled')
          AND date(a.due_date) < date('now')
        ORDER BY date(a.due_date) ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    today = date.today()
    items = []
    for r in rows:
        due = _date_from_iso(r["due_date"])
        if due is None:
            continue
        items.append(
            {
                "action_id": int(r["action_id"]),
                "defect_id": int(r["defect_id"]),
                "title": r["title"],
                "owner": r["owner"],
                "due_date": due.isoformat(),
                "days_overdue": (today - due).days,
                "defect_title": r["defect_title"],
            }
        )
    return items


def analytics(conn: sqlite3.Connection, *, range_days: int) -> dict[str, Any]:
    # Trend by day for created, and "resolved" approximated by status updated to one of terminal-ish statuses.
    # We'll bucket using date(created_at) and date(updated_at) for resolved statuses.
    range_days = max(1, min(range_days, 365))
    start_date = (date.today() - timedelta(days=range_days - 1)).isoformat()

    created_rows = conn.execute(
        """
        SELECT date(created_at) AS d, COUNT(1) AS c
        FROM defects
        WHERE date(created_at) >= date(?)
        GROUP BY date(created_at)
        """,
        (start_date,),
    ).fetchall()
    created_map = {r["d"]: int(r["c"]) for r in created_rows}

    resolved_rows = conn.execute(
        """
        SELECT date(updated_at) AS d, COUNT(1) AS c
        FROM defects
        WHERE date(updated_at) >= date(?)
          AND status IN ('resolved','verified','closed')
        GROUP BY date(updated_at)
        """,
        (start_date,),
    ).fetchall()
    resolved_map = {r["d"]: int(r["c"]) for r in resolved_rows}

    trends = []
    for i in range(range_days):
        d = (date.today() - timedelta(days=(range_days - 1 - i))).isoformat()
        trends.append({"date": d, "created": created_map.get(d, 0), "resolved": resolved_map.get(d, 0)})

    # Average days to resolve (only for resolved-ish)
    avg_row = conn.execute(
        """
        SELECT AVG(julianday(updated_at) - julianday(created_at)) AS avg_days
        FROM defects
        WHERE status IN ('resolved','verified','closed')
        """
    ).fetchone()
    avg_days = avg_row["avg_days"]
    return {"range_days": range_days, "trends": trends, "avg_days_to_resolve": float(avg_days) if avg_days is not None else None}
