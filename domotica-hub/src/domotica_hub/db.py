"""Persistencia en SQLite: cola de tareas, historial de eventos y estado OAuth.

Una sola conexión compartida (servidor MCP asíncrono + hilo ejecutor), serializada con un lock.
Los tokens OAuth se guardan solo como hash SHA-256.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

# Ciclo de vida de una tarea.
EN_COLA = "en_cola"
EN_CURSO = "en_curso"
ESPERANDO_APROBACION = "esperando_aprobacion"
APLICANDO = "aplicando"
TERMINADA = "terminada"
ERROR = "error"
CANCELADA = "cancelada"
INTERRUMPIDA = "interrumpida"

ESTADOS_ACTIVOS = (EN_CURSO, APLICANDO)
ESTADOS_FINALES = (TERMINADA, ERROR, CANCELADA, INTERRUMPIDA)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS tareas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    casa             TEXT NOT NULL,
    agente           TEXT NOT NULL,
    cuenta           TEXT,
    cuenta_explicita INTEGER NOT NULL DEFAULT 0,
    descripcion      TEXT NOT NULL,
    estado           TEXT NOT NULL,
    continuar_de     INTEGER REFERENCES tareas(id),
    sesion_id        TEXT,
    issue            INTEGER,
    rama             TEXT,
    pr               INTEGER,
    worktree         TEXT,
    log_path         TEXT,
    resultado        TEXT,
    error            TEXT,
    requiere_aplicar INTEGER NOT NULL DEFAULT 0,
    creada           REAL NOT NULL,
    actualizada      REAL NOT NULL,
    iniciada         REAL,
    terminada        REAL
);
CREATE INDEX IF NOT EXISTS tareas_estado ON tareas(estado);

CREATE TABLE IF NOT EXISTS eventos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tarea_id INTEGER NOT NULL REFERENCES tareas(id),
    ts       REAL NOT NULL,
    tipo     TEXT NOT NULL,
    detalle  TEXT
);

CREATE TABLE IF NOT EXISTS oauth_clientes (
    client_id TEXT PRIMARY KEY,
    info_json TEXT NOT NULL,
    creado    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_pendientes (
    id          TEXT PRIMARY KEY,
    client_id   TEXT NOT NULL,
    params_json TEXT NOT NULL,
    expira      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_codigos (
    code_hash TEXT PRIMARY KEY,
    datos_json TEXT NOT NULL,
    expira    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    token_hash TEXT PRIMARY KEY,
    tipo       TEXT NOT NULL CHECK (tipo IN ('access', 'refresh')),
    client_id  TEXT NOT NULL,
    scopes     TEXT NOT NULL,
    resource   TEXT,
    expira     REAL,
    grupo      TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(ESQUEMA)
        path.chmod(0o600)

    def ejecutar(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def uno(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        with self._lock:
            fila = self._conn.execute(sql, params).fetchone()
        return dict(fila) if fila else None

    def todos(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(f) for f in self._conn.execute(sql, params).fetchall()]

    # --- tareas -------------------------------------------------------------------------

    def crear_tarea(
        self,
        casa: str,
        agente: str,
        descripcion: str,
        cuenta: str | None,
        cuenta_explicita: bool,
        continuar_de: int | None = None,
    ) -> int:
        ahora = time.time()
        cur = self.ejecutar(
            "INSERT INTO tareas (casa, agente, cuenta, cuenta_explicita, descripcion, estado,"
            " continuar_de, creada, actualizada) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (casa, agente, cuenta, int(cuenta_explicita), descripcion, EN_COLA, continuar_de, ahora, ahora),
        )
        tarea_id = int(cur.lastrowid)
        self.evento(tarea_id, "creada", f"{agente}/{cuenta or '-'} en {casa}")
        return tarea_id

    def tarea(self, tarea_id: int) -> dict[str, Any] | None:
        return self.uno("SELECT * FROM tareas WHERE id = ?", (tarea_id,))

    def actualizar(self, tarea_id: int, **campos: Any) -> None:
        if not campos:
            return
        campos["actualizada"] = time.time()
        sets = ", ".join(f"{k} = :{k}" for k in campos)
        self.ejecutar(f"UPDATE tareas SET {sets} WHERE id = :id", {**campos, "id": tarea_id})

    def cambiar_estado(self, tarea_id: int, estado: str, detalle: str = "", **campos: Any) -> None:
        if estado in ESTADOS_FINALES or estado == ESPERANDO_APROBACION:
            campos.setdefault("terminada", time.time())
        self.actualizar(tarea_id, estado=estado, **campos)
        self.evento(tarea_id, estado, detalle)

    def evento(self, tarea_id: int, tipo: str, detalle: str = "") -> None:
        self.ejecutar(
            "INSERT INTO eventos (tarea_id, ts, tipo, detalle) VALUES (?, ?, ?, ?)",
            (tarea_id, time.time(), tipo, detalle[:2000]),
        )

    def eventos(self, tarea_id: int) -> list[dict[str, Any]]:
        return self.todos("SELECT ts, tipo, detalle FROM eventos WHERE tarea_id = ? ORDER BY id", (tarea_id,))

    def siguiente_en_cola(self) -> dict[str, Any] | None:
        return self.uno("SELECT * FROM tareas WHERE estado = ? ORDER BY id LIMIT 1", (EN_COLA,))

    def marcar_interrumpidas(self) -> list[int]:
        """Al arrancar: lo que estaba corriendo pasa a 'interrumpida' y no se relanza."""
        filas = self.todos(
            f"SELECT id FROM tareas WHERE estado IN ({','.join('?' * len(ESTADOS_ACTIVOS))})",
            ESTADOS_ACTIVOS,
        )
        for f in filas:
            self.cambiar_estado(f["id"], INTERRUMPIDA, "reinicio del servicio")
        return [f["id"] for f in filas]

    # --- OAuth --------------------------------------------------------------------------

    def guardar_json(self, tabla: str, clave_col: str, clave: str, **cols: Any) -> None:
        nombres = [clave_col, *cols]
        valores = [clave, *[json.dumps(v) if isinstance(v, (dict, list)) else v for v in cols.values()]]
        self.ejecutar(
            f"INSERT OR REPLACE INTO {tabla} ({', '.join(nombres)}) VALUES ({', '.join('?' * len(nombres))})",
            tuple(valores),
        )
