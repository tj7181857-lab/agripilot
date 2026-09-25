"""
AgriPilot :: SQLite persistence for farms, predictions, queries, and advisories.

Used by the Step-4 farm advisory engine, multilingual assistant, and HTTP API.
Does not replace the existing simulator or trained ML artifacts.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

from paths import CROP_COMPARISON, DEFAULT_DB, DISEASE_METRICS, db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    created_at TEXT NOT NULL,
    username TEXT,
    password_hash TEXT,
    role TEXT NOT NULL DEFAULT 'farmer'
);

CREATE TABLE IF NOT EXISTS farms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    location TEXT,
    district TEXT,
    state TEXT,
    soil_type TEXT,
    irrigation_system TEXT,
    area_ha REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS farm_crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL REFERENCES farms(id),
    crop TEXT NOT NULL,
    variety TEXT,
    season TEXT,
    sowing_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS farm_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL REFERENCES farms(id),
    n REAL,
    p REAL,
    k REAL,
    ph REAL,
    temperature REAL,
    humidity REAL,
    rainfall REAL,
    soil_moisture REAL,
    weather_notes TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crop_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    measurement_id INTEGER,
    recommended_crop TEXT NOT NULL,
    confidence REAL,
    alternatives_json TEXT,
    reasons_json TEXT,
    input_json TEXT,
    model_name TEXT,
    model_version TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS disease_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    crop TEXT,
    disease TEXT,
    class_name TEXT,
    is_healthy INTEGER,
    confidence REAL,
    severity TEXT,
    top_candidates_json TEXT,
    image_name TEXT,
    gradcam_path TEXT,
    model_version TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS farmer_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    user_id INTEGER,
    language TEXT,
    detected_language TEXT,
    question TEXT NOT NULL,
    answer TEXT,
    sources_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS advisories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    language TEXT NOT NULL DEFAULT 'en',
    title TEXT,
    summary TEXT,
    reasons_json TEXT,
    actions_json TEXT,
    payload_json TEXT,
    crop_prediction_id INTEGER,
    disease_prediction_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS irrigation_advisories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER,
    advisory_id INTEGER,
    recommendation TEXT NOT NULL,
    reason TEXT,
    soil_moisture REAL,
    rainfall REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT,
    artifact_path TEXT,
    metrics_json TEXT,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _connect(path: Optional[str] = None) -> sqlite3.Connection:
    p = path or db_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(path: Optional[str] = None):
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Optional[str] = None, seed: bool = True) -> str:
    p = path or db_path()
    with get_connection(p) as conn:
        conn.executescript(SCHEMA)
        # Add auth fields in-place for existing Step-4 databases. Existing user
        # and farm rows remain unchanged and all pre-existing accounts default
        # to the least-privileged farmer role.
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "username" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "password_hash" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if "role" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'farmer'")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique "
            "ON users(username) WHERE username IS NOT NULL AND username != ''"
        )
        if seed:
            _seed_model_versions(conn)
            _seed_demo_records(conn)
    return p


def _seed_model_versions(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS c FROM model_versions").fetchone()["c"]
    if existing:
        return
    crop_metrics = {}
    if os.path.exists(CROP_COMPARISON):
        with open(CROP_COMPARISON, "r", encoding="utf-8") as f:
            crop_json = json.load(f)
        best = crop_json.get("best_model", "random_forest")
        crop_metrics = crop_json.get("comparison", {}).get(best, {})
        conn.execute(
            """INSERT INTO model_versions
               (model_type, name, version, artifact_path, metrics_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "crop_recommendation",
                crop_metrics.get("model_name", "Random Forest"),
                crop_json.get("metadata", {}).get("timestamp", "step2"),
                "outputs/crop_models/crop_recommender_bundle.joblib",
                json.dumps(crop_metrics, ensure_ascii=False),
                now(),
            ),
        )
    if os.path.exists(DISEASE_METRICS):
        with open(DISEASE_METRICS, "r", encoding="utf-8") as f:
            dis_json = json.load(f)
        conn.execute(
            """INSERT INTO model_versions
               (model_type, name, version, artifact_path, metrics_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "disease_classification",
                dis_json.get("metadata", {}).get("model_architecture", "MobileNetV2"),
                dis_json.get("metadata", {}).get("training_timestamp", "step3"),
                "outputs/disease_model.keras",
                json.dumps(dis_json.get("overall", {}), ensure_ascii=False),
                now(),
            ),
        )


def _seed_demo_records(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]:
        return
    cur = conn.execute(
        "INSERT INTO users (name, phone, language, created_at) VALUES (?, ?, ?, ?)",
        ("Demo Farmer", None, "en", now()),
    )
    user_id = cur.lastrowid
    cur = conn.execute(
        """INSERT INTO farms
           (user_id, name, location, district, state, soil_type, irrigation_system, area_ha, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, "Nashik Demo Farm", "Nashik", "Nashik", "Maharashtra",
         "loam", "drip", 0.8, now()),
    )
    farm_id = cur.lastrowid
    conn.execute(
        """INSERT INTO farm_crops (farm_id, crop, variety, season, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (farm_id, "tomato", "local", "kharif", "active", now()),
    )
    conn.execute(
        """INSERT INTO farm_measurements
           (farm_id, n, p, k, ph, temperature, humidity, rainfall, soil_moisture, source, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (farm_id, 90, 45, 48, 6.5, 26.0, 78.0, 85.0, 32.0, "demo_seed", now()),
    )


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_list(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [row_to_dict(r) for r in rows]


def insert(table: str, data: Dict[str, Any], path: Optional[str] = None) -> int:
    cols = list(data.keys())
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    with get_connection(path) as conn:
        cur = conn.execute(sql, [data[c] for c in cols])
        return int(cur.lastrowid)


def update(table: str, record_id: int, data: Dict[str, Any], path: Optional[str] = None) -> int:
    if not data:
        return 0
    assignments = ", ".join(f"{k} = ?" for k in data)
    sql = f"UPDATE {table} SET {assignments} WHERE id = ?"
    with get_connection(path) as conn:
        cur = conn.execute(sql, list(data.values()) + [record_id])
        return int(cur.rowcount)


def update_farm_profile(
    farm_id: int, farm_fields: Dict[str, Any], crop_fields: Dict[str, Any],
    path: Optional[str] = None,
) -> None:
    """Update a farm and its active crop together, preserving their farm_id link."""
    farm_columns = {
        "name", "location", "district", "state", "soil_type",
        "irrigation_system", "area_ha",
    }
    crop_columns = {"crop", "variety", "season", "sowing_date"}
    farm_fields = {k: v for k, v in farm_fields.items() if k in farm_columns}
    crop_fields = {k: v for k, v in crop_fields.items() if k in crop_columns}
    with get_connection(path) as conn:
        if farm_fields:
            assignments = ", ".join(f"{k} = ?" for k in farm_fields)
            conn.execute(
                f"UPDATE farms SET {assignments} WHERE id = ?",
                list(farm_fields.values()) + [farm_id],
            )
        if crop_fields:
            active = conn.execute(
                "SELECT id FROM farm_crops WHERE farm_id = ? AND status = 'active' "
                "ORDER BY id DESC LIMIT 1", (farm_id,),
            ).fetchone()
            if active:
                assignments = ", ".join(f"{k} = ?" for k in crop_fields)
                conn.execute(
                    f"UPDATE farm_crops SET {assignments} WHERE id = ? AND farm_id = ?",
                    list(crop_fields.values()) + [active["id"], farm_id],
                )
            elif crop_fields.get("crop"):
                conn.execute(
                    "INSERT INTO farm_crops "
                    "(farm_id, crop, variety, season, sowing_date, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, 'active', ?)",
                    (farm_id, crop_fields.get("crop"), crop_fields.get("variety"),
                     crop_fields.get("season"), crop_fields.get("sowing_date"), now()),
                )


def get_by_id(table: str, record_id: int, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection(path) as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
        return row_to_dict(row)


def user_by_username(username: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection(path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return row_to_dict(row)


def create_account(
    *, name: str, username: str, password_hash: str, phone: Optional[str] = None,
    language: str = "en", role: str = "farmer", farm: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
) -> int:
    if role not in {"farmer", "analyst"}:
        raise ValueError("Invalid account role")
    with get_connection(path) as conn:
        cur = conn.execute(
            "INSERT INTO users (name, phone, language, created_at, username, password_hash, role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, phone, language, now(), username, password_hash, role),
        )
        user_id = int(cur.lastrowid)
        if farm:
            conn.execute(
                """INSERT INTO farms
                   (user_id, name, location, district, state, soil_type,
                    irrigation_system, area_ha, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, farm["name"], farm.get("location"), farm.get("district"),
                 farm.get("state") or "Maharashtra", farm.get("soil_type"),
                 farm.get("irrigation_system"), farm.get("area_ha"), now()),
            )
        return user_id


def create_farm_profile(
    user_id: int, farm_fields: Dict[str, Any], crop_fields: Dict[str, Any],
    path: Optional[str] = None,
) -> int:
    """Create an owned farm and its active crop atomically."""
    with get_connection(path) as conn:
        cur = conn.execute(
            """INSERT INTO farms
               (user_id, name, location, district, state, soil_type,
                irrigation_system, area_ha, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, farm_fields["name"], farm_fields["location"], farm_fields["district"],
             farm_fields["state"], farm_fields["soil_type"], farm_fields["irrigation_system"],
             farm_fields["area_ha"], now()),
        )
        farm_id = int(cur.lastrowid)
        conn.execute(
            """INSERT INTO farm_crops (farm_id, crop, status, created_at)
               VALUES (?, ?, 'active', ?)""",
            (farm_id, crop_fields["crop"], now()),
        )
        return farm_id


def set_user_login(
    user_id: int, username: str, password_hash: str, role: str = "farmer",
    path: Optional[str] = None,
) -> int:
    if role not in {"farmer", "analyst"}:
        raise ValueError("Invalid account role")
    return update(
        "users", user_id,
        {"username": username, "password_hash": password_hash, "role": role},
        path,
    )


def list_rows(
    table: str,
    where: Optional[str] = None,
    params: Optional[tuple] = None,
    order_by: str = "id DESC",
    limit: int = 50,
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += f" ORDER BY {order_by} LIMIT ?"
    with get_connection(path) as conn:
        rows = conn.execute(sql, list(params or ()) + [limit]).fetchall()
        return rows_to_list(rows)


def latest_for_farm(table: str, farm_id: int, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection(path) as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE farm_id = ? ORDER BY id DESC LIMIT 1",
            (farm_id,),
        ).fetchone()
        return row_to_dict(row)


def farm_context(
    farm_id: int, path: Optional[str] = None, *, exclude_demo: bool = False,
) -> Dict[str, Any]:
    farm = get_by_id("farms", farm_id, path)
    if not farm:
        raise KeyError(f"Farm {farm_id} not found")
    user = get_by_id("users", farm["user_id"], path) if farm.get("user_id") else None
    crops = list_rows("farm_crops", "farm_id = ?", (farm_id,), "id DESC", 10, path)
    if exclude_demo:
        demo_sources = ("demo_seed", "simulation", "pilot_simulation")
        measurements = list_rows(
            "farm_measurements",
            "farm_id = ? AND source NOT IN (?, ?, ?)",
            (farm_id, *demo_sources), "id DESC", 1, path,
        )
        measurement = measurements[0] if measurements else None
        predictions = list_rows(
            "crop_predictions",
            "farm_id = ? AND (measurement_id IS NULL OR measurement_id NOT IN "
            "(SELECT id FROM farm_measurements WHERE source IN (?, ?, ?)))",
            (farm_id, *demo_sources), "id DESC", 1, path,
        )
        crop_pred = predictions[0] if predictions else None
        advisories = list_rows(
            "advisories",
            "farm_id = ? AND (crop_prediction_id IS NULL OR crop_prediction_id NOT IN "
            "(SELECT id FROM crop_predictions WHERE measurement_id IN "
            "(SELECT id FROM farm_measurements WHERE source IN (?, ?, ?))))",
            (farm_id, *demo_sources), "id DESC", 1, path,
        )
        last_advisory = advisories[0] if advisories else None
    else:
        measurement = latest_for_farm("farm_measurements", farm_id, path)
        crop_pred = latest_for_farm("crop_predictions", farm_id, path)
        last_advisory = latest_for_farm("advisories", farm_id, path)
    disease_pred = latest_for_farm("disease_predictions", farm_id, path)
    last_queries = list_rows("farmer_queries", "farm_id = ?", (farm_id,), "id DESC", 5, path)
    return {
        "farm": farm,
        "user": user,
        "crops": crops,
        "active_crop": next((c for c in crops if c.get("status") == "active"), crops[0] if crops else None),
        "measurement": measurement,
        "crop_prediction": crop_pred,
        "disease_prediction": disease_pred,
        "last_advisory": last_advisory,
        "recent_queries": last_queries,
    }


if __name__ == "__main__":
    created = init_db()
    print(f"SQLite database ready: {created}")
    print(f"Default path: {DEFAULT_DB}")
