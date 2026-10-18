from __future__ import annotations

import json
import time

from domotica_hub.vigia import revisar


def _salud(cfg, ok=True, edad=0):
    p = cfg.estado / "salud.json"
    p.write_text(json.dumps({"ok": ok}))
    t = time.time() - edad
    import os
    os.utime(p, (t, t))


class GhVigia:
    def __init__(self):
        self.issues, self.comentarios, self.cerrados = [], [], []

    def crear_issue(self, titulo, cuerpo):
        self.issues.append(titulo)
        return len(self.issues)

    def comentar(self, n, texto):
        self.comentarios.append(n)

    def cerrar_issue(self, n):
        self.cerrados.append(n)


def test_avisa_tras_dos_fallos_y_cierra_al_recuperarse(entorno):
    cfg, gh = entorno["cfg"], GhVigia()
    _salud(cfg, ok=False)
    assert revisar(cfg, gh) == 1 and gh.issues == []          # un fallo aislado no avisa
    assert revisar(cfg, gh) == 1 and len(gh.issues) == 1      # el segundo abre el issue
    assert revisar(cfg, gh) == 1 and len(gh.issues) == 1      # no duplica
    _salud(cfg, ok=True)
    assert revisar(cfg, gh) == 0 and gh.cerrados == [1]


def test_estado_viejo_es_falla(entorno):
    cfg, gh = entorno["cfg"], GhVigia()
    _salud(cfg, ok=True, edad=600)
    assert revisar(cfg, gh) == 1
