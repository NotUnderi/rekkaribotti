import sqlite3
from pathlib import Path

OLD_DB_PATH = Path("autot.db")
NEW_DB_PATH = Path("autot_new.db")


def ensure_new_schema(conn: sqlite3.Connection) -> None:
    # Recreate the normalized tables to avoid lingering incompatible schemas.
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in ("message", "vehicle", "manufacturer", "model", "drive_type", "fuel_type"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE IF NOT EXISTS manufacturer (name TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS model (modelName TEXT PRIMARY KEY, description TEXT)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle (
            vinNumber TEXT PRIMARY KEY,
            licensePlate TEXT,
            manufacturer TEXT,
            modelName TEXT,
            fuel TEXT,
            drive TEXT,
            registerDate TEXT,
            cylinders INTEGER,
            cylinderVolumeLiters INTEGER,
            powerHp INTEGER,
            powerKW INTEGER,
            FOREIGN KEY(manufacturer) REFERENCES manufacturer(name),
            FOREIGN KEY(modelName) REFERENCES model(modelName),
            FOREIGN KEY(fuel) REFERENCES fuel_type(name),
            FOREIGN KEY(drive) REFERENCES drive_type(name)
        )
        """
    )
    conn.execute("CREATE TABLE IF NOT EXISTS drive_type (name TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS fuel_type (name TEXT PRIMARY KEY)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY,
            message TEXT,
            vinNumber TEXT,
            time TEXT,
            discord_message_id TEXT,
            discord_channel_id TEXT,
            discord_guild_id TEXT,
            FOREIGN KEY(vinNumber) REFERENCES vehicle(vinNumber)
        )
        """
    )


def migrate_cache(old_cur: sqlite3.Cursor, new_conn: sqlite3.Connection) -> int:
    new_cur = new_conn.cursor()
    old_cur.execute(
        """
        SELECT rekkari, vinNumber, manufacturer, modelName, description, registerDate,
               drive, fuel, cylinders, cylinderVolumeLiters, powerHp, powerKW
        FROM cache
        """
    )
    rows = old_cur.fetchall()
    for row in rows:
        manufacturer = row["manufacturer"]
        model_name = row["modelName"]
        drive = row["drive"]
        fuel = row["fuel"]
        if manufacturer:
            new_cur.execute("INSERT OR IGNORE INTO manufacturer (name) VALUES (?)", (manufacturer,))
        if model_name:
            new_cur.execute(
                """
                INSERT INTO model (modelName, description) VALUES (?, ?)
                ON CONFLICT(modelName)
                DO UPDATE SET description = COALESCE(excluded.description, model.description)
                """,
                (model_name, row["description"]),
            )
        if drive:
            new_cur.execute("INSERT OR IGNORE INTO drive_type (name) VALUES (?)", (drive,))
        if fuel:
            new_cur.execute("INSERT OR IGNORE INTO fuel_type (name) VALUES (?)", (fuel,))

        new_cur.execute(
            """
            INSERT OR REPLACE INTO vehicle (
                vinNumber, licensePlate, manufacturer, modelName, fuel, drive,
                registerDate, cylinders, cylinderVolumeLiters, powerHp, powerKW
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["vinNumber"],
                row["rekkari"],
                manufacturer,
                model_name,
                fuel,
                drive,
                row["registerDate"],
                row["cylinders"],
                row["cylinderVolumeLiters"],
                row["powerHp"],
                row["powerKW"],
            ),
        )
    return len(rows)


def migrate_messages(old_cur: sqlite3.Cursor, new_conn: sqlite3.Connection) -> int:
    new_cur = new_conn.cursor()
    old_cur.execute(
        """
        SELECT id, message, vinNumber, time, discord_message_id, discord_channel_id, discord_guild_id
        FROM autot_messages
        """
    )
    rows = old_cur.fetchall()
    for row in rows:
        new_cur.execute(
            """
            INSERT OR IGNORE INTO message (
                id, message, vinNumber, time, discord_message_id, discord_channel_id, discord_guild_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["message"],
                row["vinNumber"],
                row["time"],
                row["discord_message_id"],
                row["discord_channel_id"],
                row["discord_guild_id"],
            ),
        )
    return len(rows)


def main() -> None:
    if not OLD_DB_PATH.exists():
        raise SystemExit(f"Old database not found at {OLD_DB_PATH}")

    old_db = sqlite3.connect(OLD_DB_PATH)
    old_db.row_factory = sqlite3.Row
    new_db = sqlite3.connect(NEW_DB_PATH)
    new_db.row_factory = sqlite3.Row

    ensure_new_schema(new_db)

    cache_rows = migrate_cache(old_db.cursor(), new_db)
    message_rows = migrate_messages(old_db.cursor(), new_db)

    new_db.commit()
    print(f"Migrated {cache_rows} cache rows to vehicle/manufacturer/model/drive_type/fuel_type")
    print(f"Migrated {message_rows} message rows to message")


if __name__ == "__main__":
    main()
