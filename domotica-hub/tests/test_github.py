from __future__ import annotations

from domotica_hub.github import GitHub


class GitHubGrabador(GitHub):
    """Registra los comandos que se ejecutarían, sin red."""

    def __init__(self, cfg, respuesta: str = "{}"):
        super().__init__(cfg)
        self.comandos: list[list[str]] = []
        self.respuesta = respuesta

    def _correr(self, args, cwd=None, entrada=None):
        self.comandos.append(args)
        return self.respuesta


def test_repo_view_usa_argumento_posicional(entorno):
    gh = GitHubGrabador(entorno["cfg"], '{"visibility": "private"}')
    assert gh.visibilidad() == "PRIVATE"
    assert gh.comandos[-1] == ["gh", "repo", "view", "GRUPOAISLAR/Hassio", "--json", "visibility"]


def test_issue_pr_usan_repo_y_cuerpo_por_stdin(entorno):
    gh = GitHubGrabador(entorno["cfg"], "https://github.com/GRUPOAISLAR/Hassio/issues/7")
    assert gh.crear_issue("t", "cuerpo") == 7
    cmd = gh.comandos[-1]
    assert cmd[:3] == ["gh", "issue", "create"] and cmd[-2:] == ["--repo", "GRUPOAISLAR/Hassio"]
    assert "--body-file" in cmd and "cuerpo" not in cmd
    gh.respuesta = "https://github.com/GRUPOAISLAR/Hassio/pull/8"
    assert gh.crear_pr("claude/1", "main", "t", "c") == 8


def test_comandos_reales_de_gh_aceptan_las_opciones(entorno):
    """Valida contra el gh instalado que cada subcomando acepta las opciones que usamos."""
    import subprocess
    for sub, flags in ((["repo", "view"], ["--json"]), (["issue", "create"], ["--repo", "--body-file"]),
                       (["issue", "comment"], ["--repo", "--body-file"]), (["issue", "close"], ["--repo"]),
                       (["pr", "create"], ["--repo", "--head", "--base", "--body-file"]),
                       (["pr", "view"], ["--repo", "--json"])):
        ayuda = subprocess.run(["gh", *sub, "--help"], capture_output=True, text=True).stdout
        ayuda += subprocess.run(["gh", "help", "environment"], capture_output=True, text=True).stdout
        for f in flags:
            if f == "--repo":
                assert "-R, --repo" in ayuda or "--repo" in ayuda, (sub, f)
            else:
                assert f in ayuda, (sub, f)
