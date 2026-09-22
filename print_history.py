import os
import sqlite3
import os
from datetime import datetime
from pathlib import Path

DEFAULT_DB_NAME = "3d_printer_logs.db"
DB_ENV_VAR = "OPENSPOOLMAN_PRINT_HISTORY_DB"


def _default_db_path() -> Path:
    # Resolve the print history database path, allowing an env override.

    env_path = os.getenv(DB_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser().resolve()

    return Path(__file__).resolve().parent / "data" / DEFAULT_DB_NAME


db_config = {"db_path": str(_default_db_path())}  # Configuration for database location


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def create_database() -> None:
    #
    # Ensure the SQLite schema exists (used for both fresh and upgrading databases).
    db_path = Path(db_config["db_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            print_date TEXT NOT NULL,
            file_name TEXT NOT NULL,
            print_type TEXT NOT NULL,
            image_file TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS filament_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            print_id INTEGER NOT NULL,
            spool_id INTEGER,
            filament_type TEXT NOT NULL,
            color TEXT NOT NULL,
            grams_used REAL NOT NULL,
            ams_slot INTEGER NOT NULL,
            estimated_grams REAL,
            length_used REAL,
            estimated_length REAL,
            calculated_length REAL,
            spoolman_length_used REAL,
        FOREIGN KEY (print_id) REFERENCES prints (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS filament_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            print_id INTEGER NOT NULL,
            layer INTEGER NOT NULL,
            filament_index INTEGER NOT NULL,
            spool_id INTEGER NOT NULL,
            length_used REAL NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('pending', 'sent', 'confirmed')),
            UNIQUE (print_id, layer, filament_index),
            FOREIGN KEY (print_id) REFERENCES prints (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS print_layer_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            print_id INTEGER NOT NULL UNIQUE,
            total_layers INTEGER,
            layers_printed INTEGER,
            filament_grams_billed REAL,
            filament_grams_total REAL,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            predicted_end_time TEXT,
            actual_end_time TEXT,
            FOREIGN KEY (print_id) REFERENCES prints (id) ON DELETE CASCADE
        )
    ''')

    _ensure_column(
        cursor,
        "filament_usage",
        "estimated_grams",
        "REAL",
    )
    _ensure_column(
        cursor,
        "filament_usage",
        "length_used",
        "REAL",
    )
    _ensure_column(
        cursor,
        "filament_usage",
        "estimated_length",
        "REAL",
    )
    _ensure_column(cursor, "filament_usage_events", "status", "TEXT NOT NULL DEFAULT 'confirmed'")
    # Events written by older versions already caused the corresponding Spoolman
    # charge, so they must never become retry candidates after migration.
    cursor.execute("UPDATE filament_usage_events SET status = 'confirmed' WHERE status IS NULL OR status NOT IN ('pending', 'sent', 'confirmed')")
    _ensure_column(cursor, "filament_usage", "calculated_length", "REAL")
    _ensure_column(cursor, "filament_usage", "spoolman_length_used", "REAL")
    cursor.execute("UPDATE filament_usage SET calculated_length = length_used WHERE calculated_length IS NULL AND length_used IS NOT NULL")
    # Legacy completed/failed jobs already had their usage sent to Spoolman.
    # Backfill the confirmed total while leaving the currently running job open.
    cursor.execute(
        """UPDATE filament_usage
           SET calculated_length = COALESCE(calculated_length, length_used, 0),
               spoolman_length_used = COALESCE(spoolman_length_used, length_used, 0)
           WHERE spoolman_length_used IS NULL
             AND print_id IN (
               SELECT f.print_id
               FROM filament_usage f
               LEFT JOIN print_layer_tracking t ON t.print_id = f.print_id
               WHERE COALESCE(t.status, 'COMPLETED') <> 'RUNNING'
             )"""
    )
    _ensure_column(
        cursor,
        "filament_usage",
        "physical_ams_slot",
        "INTEGER",
    )

    # Ensure column definitions exist for older databases
    _ensure_column(
        cursor,
        "print_layer_tracking",
        "predicted_end_time",
        "TEXT",
    )
    _ensure_column(cursor, "prints", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(
        cursor,
        "print_layer_tracking",
        "actual_end_time",
        "TEXT",
    )
    _ensure_column(cursor, "print_layer_tracking", "completion_source", "TEXT")
    _ensure_column(cursor, "print_layer_tracking", "printer_completion_time", "TEXT")
    _ensure_column(cursor, "print_layer_tracking", "reconciliation_done", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(cursor, "print_layer_tracking", "estimated_duration_minutes", "REAL")
    _ensure_column(cursor, "print_layer_tracking", "printer_percent", "REAL")
    _ensure_column(cursor, "print_layer_tracking", "last_status_at", "TEXT")
    _ensure_column(cursor, "print_layer_tracking", "last_usage_event_at", "TEXT")

    conn.commit()
    conn.close()


def insert_print(file_name: str, print_type: str, image_file: str = None, print_date: str = None) -> int:
    #
    # Inserts a new print job into the database and returns the print ID.
    # If no print_date is provided, the current timestamp is used.
    if print_date is None:
        print_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_config["db_path"])
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO prints (print_date, file_name, print_type, image_file)
        VALUES (?, ?, ?, ?)
    ''', (print_date, file_name, print_type, image_file))
    print_id = cursor.lastrowid
    if print_id is None:
        conn.rollback()
        conn.close()
        raise RuntimeError("Print-History konnte keine Print-ID erzeugen")
    conn.commit()
    conn.close()
    return print_id


def ensure_layer_tracking(print_id: int, status: str = "PREPARING") -> None:
    # Create the lightweight tracking row before 3MF metadata is ready.
    if print_id is None:
        return
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute(
        "INSERT INTO print_layer_tracking (print_id, status) VALUES (?, ?) "
        "ON CONFLICT(print_id) DO UPDATE SET status = excluded.status",
        (print_id, status),
    )
    conn.commit()
    conn.close()

def update_print_image(print_id: int, image_file: str) -> None:
    if print_id is None or not image_file:
        return
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute("UPDATE prints SET image_file = ? WHERE id = ?", (image_file, print_id))
    conn.commit()
    conn.close()

def get_print_image(print_id: int) -> str | None:
    if print_id is None:
        return None
    conn = sqlite3.connect(db_config["db_path"])
    row = conn.execute("SELECT image_file FROM prints WHERE id = ?", (print_id,)).fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def get_latest_running_print_id() -> int | None:
    conn = sqlite3.connect(db_config["db_path"])
    row = conn.execute(
        "SELECT print_id FROM print_layer_tracking WHERE status = 'RUNNING' ORDER BY print_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return int(row[0]) if row else None


def find_latest_print_id(file_name: str | None) -> int | None:
    # Find the newest history entry for a printer-reported file/subtask name.
    if not file_name:
        return None

    name = str(file_name).strip()
    candidates = [name]
    for suffix in (".gcode.3mf", ".3mf", ".gcode"):
        if name.lower().endswith(suffix):
            candidates.append(name[: -len(suffix)])
    candidates = list(dict.fromkeys(candidates))

    conn = sqlite3.connect(db_config["db_path"])
    placeholders = ",".join("?" for _ in candidates)
    row = conn.execute(
        f"SELECT id FROM prints WHERE file_name IN ({placeholders}) "
        "AND COALESCE(is_deleted, 0) = 0 ORDER BY id DESC LIMIT 1",
        candidates,
    ).fetchone()
    conn.close()
    return int(row[0]) if row else None


def _normalise_print_name(value: str | None) -> str:
    name = str(value or "").strip().lower()
    for suffix in (".gcode.3mf", ".3mf", ".gcode"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def find_open_print_for_printer_job(*names: str | None) -> dict | None:
    # Find the newest non-finalized history row matching a printer job name.
    wanted = {_normalise_print_name(name) for name in names if name}
    wanted.discard("")
    if not wanted:
        return None

    conn = sqlite3.connect(db_config["db_path"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT p.id, p.file_name, t.status, t.total_layers,
                         t.layers_printed, t.predicted_end_time,
                         t.estimated_duration_minutes, t.reconciliation_done
             FROM prints p
             JOIN print_layer_tracking t ON t.print_id = p.id
             WHERE COALESCE(p.is_deleted, 0) = 0
               AND t.status IN ('RUNNING', 'ABORTED')
               AND COALESCE(t.reconciliation_done, 0) = 0
             ORDER BY p.id DESC"""
    ).fetchall()
    conn.close()
    for row in rows:
        if _normalise_print_name(row["file_name"]) in wanted:
            return dict(row)
    return None


def get_filament_usage_for_reconciliation(print_id: int) -> list[dict]:
    conn = sqlite3.connect(db_config["db_path"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, ams_slot, spool_id, grams_used, estimated_grams,
                         length_used, estimated_length, calculated_length,
                         spoolman_length_used
             FROM filament_usage
             WHERE print_id = ?
             ORDER BY ams_slot""",
        (int(print_id),),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_estimated_duration_if_missing(print_id: int, minutes: float) -> None:
    if print_id is None or minutes <= 0:
        return
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute(
        """UPDATE print_layer_tracking
           SET estimated_duration_minutes = ?
           WHERE print_id = ? AND estimated_duration_minutes IS NULL""",
        (float(minutes), int(print_id)),
    )
    conn.commit()
    conn.close()


def update_printer_job_status(
    print_id: int,
    *,
    percent: float | None = None,
    status_at: str | None = None,
) -> None:
    if print_id is None:
        return
    fields = []
    values = []
    if percent is not None:
        fields.append("printer_percent = ?")
        values.append(max(0.0, min(100.0, float(percent))))
    if status_at:
        fields.append("last_status_at = ?")
        values.append(status_at)
    if not fields:
        return
    values.append(int(print_id))
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute(f"UPDATE print_layer_tracking SET {', '.join(fields)} WHERE print_id = ?", values)
    conn.commit()
    conn.close()


def update_latest_printer_job_status(names: tuple[str | None, ...], *, percent: float | None, status_at: str) -> None:
    wanted = {_normalise_print_name(name) for name in names if name}
    wanted.discard("")
    if not wanted:
        return
    conn = sqlite3.connect(db_config["db_path"])
    rows = conn.execute(
        """SELECT p.id, p.file_name FROM prints p
           WHERE COALESCE(p.is_deleted, 0) = 0 ORDER BY p.id DESC"""
    ).fetchall()
    for print_id, file_name in rows:
        if _normalise_print_name(file_name) in wanted:
            fields = ["last_status_at = ?"]
            values: list[object] = [status_at]
            if percent is not None:
                fields.append("printer_percent = ?")
                values.append(max(0.0, min(100.0, float(percent))))
            values.append(int(print_id))
            conn.execute(f"UPDATE print_layer_tracking SET {', '.join(fields)} WHERE print_id = ?", values)
            break
    conn.commit()
    conn.close()


def mark_print_reconciled(
    print_id: int,
    usage_updates: list[dict],
    completion_time: str,
    source: str = "mqtt_finish_recovery",
) -> None:
    # Persist recovered totals and close the job after successful external transfers.
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute("PRAGMA foreign_keys = ON")
    for update in usage_updates:
        conn.execute(
            """UPDATE filament_usage
               SET grams_used = ?, length_used = ?, calculated_length = ?,
                   spoolman_length_used = ?
               WHERE id = ?""",
            (
                update["grams_used"],
                update["length_used"],
                update["length_used"],
                update["length_used"],
                int(update["id"]),
            ),
        )
    conn.execute(
        """UPDATE print_layer_tracking
           SET status = 'COMPLETED',
               layers_printed = COALESCE(total_layers, layers_printed),
               filament_grams_billed = COALESCE(
                   (SELECT SUM(grams_used) FROM filament_usage WHERE print_id = ?),
                   filament_grams_billed
               ),
               estimated_duration_minutes = COALESCE(
                   estimated_duration_minutes,
                   (julianday(predicted_end_time) -
                    (SELECT julianday(print_date) FROM prints WHERE id = ?)) * 1440.0
               ),
               actual_end_time = ?, completion_source = ?,
               printer_completion_time = ?, printer_percent = 100,
               last_usage_event_at = COALESCE(
                   last_usage_event_at,
                   (SELECT MAX(created_at) FROM filament_usage_events WHERE print_id = ?)
               ),
               reconciliation_done = 1
           WHERE print_id = ?""",
        (int(print_id), int(print_id), completion_time, source, completion_time, int(print_id), int(print_id)),
    )
    conn.execute(
        "DELETE FROM filament_usage_events WHERE print_id = ? AND status = 'confirmed'",
        (int(print_id),),
    )
    conn.commit()
    conn.close()


def cancel_stale_running_prints(actual_end_time: str) -> int:
    # Mark interrupted legacy runs as canceled without touching filament usage.
    conn = sqlite3.connect(db_config["db_path"])
    cursor = conn.execute(
        "UPDATE print_layer_tracking SET status = 'ABORTED', actual_end_time = ? "
        "WHERE status = 'RUNNING' AND predicted_end_time IS NOT NULL AND predicted_end_time < ?",
        (actual_end_time, actual_end_time),
    )
    conn.commit()
    changed = cursor.rowcount
    conn.close()
    return changed

def insert_filament_usage(
    print_id: int,
    filament_type: str,
    color: str,
    grams_used: float,
    ams_slot: int,
    estimated_grams: float | None = None,
    length_used: float | None = None,
    estimated_length: float | None = None,
    physical_ams_slot: int | None = None,
) -> None:
    #
    # Inserts a new filament usage entry for a specific print job.
    if print_id is None:
        raise ValueError("Filamentverbrauch benötigt eine gültige Print-ID")

    conn = sqlite3.connect(db_config["db_path"])
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO filament_usage (print_id, filament_type, color, grams_used, ams_slot, estimated_grams, length_used, estimated_length, calculated_length, physical_ams_slot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (print_id, filament_type, color, grams_used, ams_slot, estimated_grams, length_used, estimated_length, length_used, physical_ams_slot))
    conn.commit()
    conn.close()

def update_filament_spool(print_id: int, filament_id: int, spool_id: int) -> None:
    #
    # Updates the spool_id for a given filament usage entry, ensuring it belongs to the specified print job.
    conn = sqlite3.connect(db_config["db_path"])
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE filament_usage
        SET spool_id = ?
        WHERE ams_slot = ? AND print_id = ?
    ''', (spool_id, filament_id, print_id))
    conn.commit()
    conn.close()

def update_filament_physical_slot(print_id: int, filament_id: int, physical_ams_slot: int) -> None:
    # Persist the physical AMS tray for a logical filament channel.
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute(
        "UPDATE filament_usage SET physical_ams_slot = ? WHERE ams_slot = ? AND print_id = ?",
        (physical_ams_slot, filament_id, print_id),
    )
    conn.commit()
    conn.close()

def claim_filament_usage_event(print_id: int | None, layer: int, filament_index: int, spool_id: int, length_used: float) -> str | None:
    # Create/inspect one consumption event and return its transfer status.
    if print_id is None:
        return "pending"
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute(
        """INSERT OR IGNORE INTO filament_usage_events
           (print_id, layer, filament_index, spool_id, length_used, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
        (print_id, int(layer), int(filament_index), int(spool_id), float(length_used), datetime.now().isoformat()),
    )
    row = conn.execute(
        "SELECT status FROM filament_usage_events WHERE print_id = ? AND layer = ? AND filament_index = ?",
        (print_id, int(layer), int(filament_index)),
    ).fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else None


def finalize_filament_usage_events(print_id: int) -> None:
    # Persist confirmed transfer totals and remove only finalized layer events.
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute("PRAGMA foreign_keys = ON")
    rows = conn.execute(
        """SELECT filament_index, SUM(length_used) AS transferred_length
           FROM filament_usage_events
           WHERE print_id = ? AND status = 'confirmed'
           GROUP BY filament_index""",
        (int(print_id),),
    ).fetchall()
    for filament_index, transferred_length in rows:
        filament_id = int(filament_index) + 1
        conn.execute(
            """UPDATE filament_usage
               SET calculated_length = COALESCE(calculated_length, length_used, ?),
                   spoolman_length_used = ?
               WHERE print_id = ? AND ams_slot = ?""",
            (float(transferred_length or 0.0), float(transferred_length or 0.0), int(print_id), filament_id),
        )
    conn.execute(
        "DELETE FROM filament_usage_events WHERE print_id = ? AND status = 'confirmed'",
        (int(print_id),),
    )
    conn.commit()
    conn.close()


def set_filament_usage_event_status(print_id: int, layer: int, filament_index: int, status: str) -> None:
    # Advance a consumption event through pending, sent and confirmed.
    if status not in {"pending", "sent", "confirmed"}:
        raise ValueError(f"Invalid filament usage event status: {status}")
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute(
        "UPDATE filament_usage_events SET status = ? WHERE print_id = ? AND layer = ? AND filament_index = ?",
        (status, int(print_id), int(layer), int(filament_index)),
    )
    if status == "confirmed":
        conn.execute(
            """UPDATE print_layer_tracking
               SET last_usage_event_at = COALESCE(
                   (SELECT MAX(created_at) FROM filament_usage_events WHERE print_id = ?),
                   last_usage_event_at
               )
               WHERE print_id = ?""",
            (int(print_id), int(print_id)),
        )
    conn.commit()
    conn.close()

def update_filament_grams_used(print_id: int, filament_id: int, grams_used: float, length_used: float | None = None) -> None:
    #
    # Updates the grams_used (and optional length_used) for a given filament usage entry, ensuring it belongs to the specified print job.
    set_parts = ["grams_used = ?"]
    params: list[float | int] = [grams_used]
    if length_used is not None:
        set_parts.append("length_used = ?")
        params.append(length_used)
        set_parts.append("calculated_length = ?")
        params.append(length_used)

    set_clause = ", ".join(set_parts)
    params.extend([filament_id, print_id])

    conn = sqlite3.connect(db_config["db_path"])
    cursor = conn.cursor()
    cursor.execute(f'''
        UPDATE filament_usage
        SET {set_clause}
        WHERE ams_slot = ? AND print_id = ?
    ''', params)
    conn.commit()
    conn.close()


def get_prints_with_filament(limit: int | None = None, offset: int | None = None, include_deleted: bool = False):
    #
    # Retrieves print jobs along with their associated filament usage, grouped by print job.
    #
    # A total count is returned to support pagination.
    conn = sqlite3.connect(db_config["db_path"])
    conn.row_factory = sqlite3.Row  # Enable column name access

    count_cursor = conn.cursor()
    where_clause = "" if include_deleted else " WHERE COALESCE(is_deleted, 0) = 0"
    count_cursor.execute("SELECT COUNT(*) FROM prints" + where_clause)
    total_count = count_cursor.fetchone()[0]

    cursor = conn.cursor()
    query = '''
        SELECT p.id AS id, p.print_date AS print_date, p.file_name AS file_name,
               p.print_type AS print_type, p.image_file AS image_file, p.is_deleted AS is_deleted,
       (
           SELECT json_group_array(json_object(
               'spool_id', f.spool_id,
                'filament_type', f.filament_type,
                'color', f.color,
                'grams_used', f.grams_used,
                'estimated_grams', f.estimated_grams,
                'length_used', f.length_used,
                'estimated_length', f.estimated_length,
                'calculated_length', f.calculated_length,
                'spoolman_length_used', f.spoolman_length_used,
                'ams_slot', f.ams_slot,
                'physical_ams_slot', f.physical_ams_slot
            )) FROM filament_usage f WHERE f.print_id = p.id
        ) AS filament_info
        FROM prints p
    ''' + where_clause + '''
        ORDER BY p.print_date DESC
    '''
    params: list[int] = []
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

    cursor.execute(query, params)
    prints = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return prints, total_count


def soft_delete_print(print_id: int) -> None:
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute("UPDATE prints SET is_deleted = 1 WHERE id = ?", (print_id,))
    conn.commit()
    conn.close()


def restore_print(print_id: int) -> None:
    conn = sqlite3.connect(db_config["db_path"])
    conn.execute("UPDATE prints SET is_deleted = 0 WHERE id = ?", (print_id,))
    conn.commit()
    conn.close()


def has_deleted_prints() -> bool:
    conn = sqlite3.connect(db_config["db_path"])
    row = conn.execute("SELECT 1 FROM prints WHERE COALESCE(is_deleted, 0) = 1 LIMIT 1").fetchone()
    conn.close()
    return row is not None

def get_prints_by_spool(spool_id: int):
    #
    # Retrieves all print jobs that used a specific spool.
    conn = sqlite3.connect(db_config["db_path"])
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT p.* FROM prints p
        JOIN filament_usage f ON p.id = f.print_id
        WHERE f.spool_id = ?
    ''', (spool_id,))
    prints = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return prints


def get_spool_print_usage(spool_id: int) -> list[dict]:
    # Return the print-level consumption records for one spool.
    conn = sqlite3.connect(db_config["db_path"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT p.id AS print_id, p.print_date, p.file_name,
                  f.grams_used, f.length_used, f.calculated_length,
                  f.spoolman_length_used
           FROM prints p
           JOIN filament_usage f ON f.print_id = p.id
           WHERE f.spool_id = ?
           ORDER BY p.print_date DESC, p.id DESC""",
        (int(spool_id),),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_filament_for_slot(print_id: int, ams_slot: int):
  conn = sqlite3.connect(db_config["db_path"])
  conn.row_factory = sqlite3.Row  # Enable column name access
  cursor = conn.cursor()

  cursor.execute('''
      SELECT * FROM filament_usage
      WHERE print_id = ? AND ams_slot = ?
  ''', (print_id, ams_slot))

  row = cursor.fetchone()
  conn.close()
  return dict(row) if row else None

def _ensure_layer_tracking_entry(print_id: int):
  conn = sqlite3.connect(db_config["db_path"])
  cursor = conn.cursor()
  cursor.execute('''
      INSERT OR IGNORE INTO print_layer_tracking (print_id)
      VALUES (?)
  ''', (print_id,))
  conn.commit()
  conn.close()

def update_layer_tracking(print_id: int, **fields):
  if not fields:
    return

  allowed_columns = {
      "total_layers",
      "layers_printed",
      "filament_grams_billed",
      "filament_grams_total",
      "status",
      "predicted_end_time",
      "actual_end_time",
      "printer_percent",
      "last_status_at",
      "last_usage_event_at",
  }

  sanitized = {key: value for key, value in fields.items() if key in allowed_columns}
  if not sanitized:
    return

  _ensure_layer_tracking_entry(print_id)

  set_clause = ", ".join(f"{key} = ?" for key in sanitized)
  params = list(sanitized.values()) + [print_id]

  conn = sqlite3.connect(db_config["db_path"])
  cursor = conn.cursor()
  cursor.execute(f'''
      UPDATE print_layer_tracking
      SET {set_clause}
      WHERE print_id = ?
  ''', params)
  conn.commit()
  conn.close()

def get_layer_tracking_for_prints(print_ids: list[int]):
  if not print_ids:
    return {}

  conn = sqlite3.connect(db_config["db_path"])
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  placeholders = ",".join("?" for _ in print_ids)
  cursor.execute(f'''
      SELECT print_id, total_layers, layers_printed, filament_grams_billed, filament_grams_total, status, predicted_end_time, actual_end_time, estimated_duration_minutes, printer_percent, last_status_at, last_usage_event_at
      FROM print_layer_tracking
      WHERE print_id IN ({placeholders})
  ''', print_ids)
  rows = cursor.fetchall()
  conn.close()
  return {row["print_id"]: dict(row) for row in rows}


def get_latest_print_summary() -> dict | None:
  # Return the latest visible print and its persisted tracking status.
  conn = sqlite3.connect(db_config["db_path"])
  conn.row_factory = sqlite3.Row
  row = conn.execute(
    """SELECT p.id, p.print_date, p.file_name,
              t.status, t.layers_printed, t.total_layers,
              t.actual_end_time, t.predicted_end_time, t.estimated_duration_minutes,
              t.printer_percent, t.last_status_at, t.last_usage_event_at,
              t.filament_grams_billed, t.filament_grams_total
       FROM prints p
       LEFT JOIN print_layer_tracking t ON t.print_id = p.id
       WHERE COALESCE(p.is_deleted, 0) = 0
       ORDER BY p.print_date DESC, p.id DESC
       LIMIT 1"""
  ).fetchone()
  conn.close()
  return dict(row) if row else None

def get_all_filament_usage_for_print(print_id: int):
  #
  # Retrieves all filament usage entries for a specific print.
  # Returns a dict mapping ams_slot to a dict with grams_used and length_used.
  conn = sqlite3.connect(db_config["db_path"])
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  cursor.execute('''
      SELECT ams_slot, grams_used, length_used FROM filament_usage
      WHERE print_id = ?
  ''', (print_id,))

  results = {
      row["ams_slot"]: {
          "grams_used": row["grams_used"],
          "length_used": row["length_used"],
      }
      for row in cursor.fetchall()
  }
  conn.close()
  return results

# Example for creating the database if it does not exist
create_database()
