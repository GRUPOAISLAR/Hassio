"""Operaciones de GitHub (gh CLI) y git sobre el repositorio de registro.

El token (GH_TOKEN_HASSIO) solo se pasa por entorno a gh/git; nunca va en la línea de
comandos ni en la URL del remoto, y los agentes no lo reciben.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .config import Config


class ErrorGitHub(RuntimeError):
    pass


class GitHub:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _env(self) -> dict[str, str]:
        token = self.cfg.secreto("GH_TOKEN_HASSIO")
        if not token:
            raise ErrorGitHub("Falta GH_TOKEN_HASSIO en el archivo env")
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(Path.home()),
            "LANG": "C.UTF-8",
            "GH_TOKEN": token,
            "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }

    def _correr(self, args: list[str], cwd: Path | None = None, entrada: str | None = None) -> str:
        r = subprocess.run(
            args, cwd=cwd, input=entrada, capture_output=True, text=True, env=self._env(), timeout=120
        )
        if r.returncode != 0:
            raise ErrorGitHub(f"{args[0]} {args[1]} falló: {r.stderr.strip()[:500]}")
        return r.stdout.strip()

    def gh(self, *args: str, entrada: str | None = None) -> str:
        return self._correr(["gh", *args, "--repo", self.cfg.repo_github], entrada=entrada)

    def git(self, *args: str, cwd: Path) -> str:
        # gh actúa como helper de credenciales leyendo GH_TOKEN del entorno.
        return self._correr(
            ["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", *args], cwd=cwd
        )

    # --- consultas ----------------------------------------------------------------------

    def visibilidad(self) -> str:
        return json.loads(self.gh("repo", "view", "--json", "visibility"))["visibility"].upper()

    def rama_default(self) -> str:
        return json.loads(self.gh("repo", "view", "--json", "defaultBranchRef"))["defaultBranchRef"]["name"]

    def estado_pr(self, pr: int) -> str:
        """OPEN, MERGED o CLOSED."""
        return json.loads(self.gh("pr", "view", str(pr), "--json", "state"))["state"].upper()

    # --- escrituras ---------------------------------------------------------------------

    def crear_issue(self, titulo: str, cuerpo: str) -> int:
        url = self.gh("issue", "create", "--title", titulo, "--body-file", "-", entrada=cuerpo)
        return int(url.rstrip("/").rsplit("/", 1)[-1])

    def comentar(self, issue: int, texto: str) -> None:
        self.gh("issue", "comment", str(issue), "--body-file", "-", entrada=texto)

    def crear_pr(self, rama: str, base: str, titulo: str, cuerpo: str) -> int:
        url = self.gh(
            "pr", "create", "--head", rama, "--base", base, "--title", titulo, "--body-file", "-", entrada=cuerpo
        )
        return int(url.rstrip("/").rsplit("/", 1)[-1])
