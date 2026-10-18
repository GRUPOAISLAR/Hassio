from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from domotica_hub.config import Config
from domotica_hub.db import DB


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class GitHubFalso:
    """Imita GitHub sobre un repositorio bare local. Sin red ni tokens."""

    def __init__(self):
        self.visible = "PRIVATE"
        self.issues: dict[int, list[str]] = {}
        self.prs: dict[int, dict] = {}
        self._n = 0

    def visibilidad(self) -> str:
        return self.visible

    def rama_default(self) -> str:
        return "main"

    def estado_pr(self, pr: int) -> str:
        return self.prs[pr]["estado"]

    def crear_issue(self, titulo: str, cuerpo: str) -> int:
        self._n += 1
        self.issues[self._n] = [titulo]
        return self._n

    def comentar(self, issue: int, texto: str) -> None:
        self.issues[issue].append(texto)

    def crear_pr(self, rama: str, base: str, titulo: str, cuerpo: str) -> int:
        self._n += 1
        self.prs[self._n] = {"rama": rama, "estado": "OPEN", "cuerpo": cuerpo}
        return self._n

    def git(self, *args: str, cwd: Path) -> str:
        return _git(*args, cwd=cwd)


@pytest.fixture
def entorno(tmp_path: Path):
    origen = tmp_path / "origen.git"
    semilla = tmp_path / "semilla"
    _git("init", "-q", "--bare", "-b", "main", str(origen), cwd=tmp_path)
    _git("init", "-q", "-b", "main", str(semilla), cwd=tmp_path)
    (semilla / "README.md").write_text("# Hassio\n")
    _git("add", "-A", cwd=semilla)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "inicial", cwd=semilla)
    _git("push", "-q", str(origen), "main", cwd=semilla)

    base = tmp_path / "domotica"
    base.mkdir()
    _git("clone", "-q", str(origen), str(base / "repo"), cwd=tmp_path)

    env = tmp_path / "env"
    env.write_text(
        "HA_LOTE101_URL=https://ejemplo.invalid\nHA_LOTE101_TOKEN_AGENTE=ficticio-agente\n"
        "HA_LOTE101_TOKEN_ADMIN=ficticio-admin\nCLAUDE_TOKEN_GMAIL=ficticio\n"
        "CLAUDE_TOKEN_BRAVOSM=ficticio\nGH_TOKEN_HASSIO=ficticio\n"
    )
    cfg = Config(env_file=env, base=base, agentes_dir=tmp_path / "agentes", intervalo_pr_s=0)
    cfg.preparar_directorios()
    db = DB(cfg.db_path)
    return {"cfg": cfg, "db": db, "gh": GitHubFalso(), "origen": origen, "tmp": tmp_path}


def mergear(origen: Path, rama: str, tmp: Path) -> None:
    """Simula el merge de un PR en el repositorio bare."""
    wc = tmp / f"merge-{rama.replace('/', '-')}"
    _git("clone", "-q", str(origen), str(wc), cwd=tmp)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-ff", "-m", "merge", f"origin/{rama}", cwd=wc)
    _git("push", "-q", "origin", "main", cwd=wc)
