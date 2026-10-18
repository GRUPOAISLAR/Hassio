"""Ejecutor: procesa la cola de a una tarea por vez y sigue los PR que esperan aprobación.

Ciclo de una tarea:
  en_cola → en_curso (issue + rama <agente>/<id> + copia de trabajo + agente en fase trabajo,
  solo lectura sobre HA) → commit/push/PR →
    · sin plan_aplicar.md: terminada
    · con plan_aplicar.md: esperando_aprobacion → (el dueño mergea el PR) → aplicando (token de
      escritura) → terminada.  PR cerrado sin merge → cancelada.
Al arrancar, lo que estaba en_curso/aplicando pasa a interrumpida y no se relanza.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from . import agentes
from . import db as D
from .config import Config
from .db import DB
from .github import GitHub

log = logging.getLogger("domotica_hub.ejecutor")

ESPERA_BLOQUEO_S = 10 * 60


class ErrorTarea(RuntimeError):
    pass


@contextmanager
def bloqueo(path: Path, cancelar: threading.Event | None = None, espera_s: float = ESPERA_BLOQUEO_S) -> Iterator[None]:
    """flock exclusivo; espera hasta espera_s. Compatible con otros procesos (p. ej. ha-consulta)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        limite = time.time() + espera_s
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if cancelar is not None and cancelar.is_set():
                    raise agentes.Cancelada()
                if time.time() > limite:
                    raise ErrorTarea(f"no se pudo tomar el bloqueo {path.name}")
                time.sleep(2)
        yield
    finally:
        os.close(fd)


def git_local(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise ErrorTarea(f"git {args[0]} falló: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def prompt_trabajo(t: dict, raiz: int) -> str:
    casa = t["casa"]
    return f"""Sos el agente de la tarea #{t['id']} sobre la casa "{casa}" (Home Assistant).
Estás en una copia de trabajo del repositorio de registro GRUPOAISLAR/Hassio.

TAREA:
{t['descripcion']}

REGLAS:
- Estado y control de dispositivos: herramientas "ha-{casa}". Si la tarea pide encender,
  apagar o ajustar algo, hacelo directamente y verificá el resultado.
- Configuración (automatizaciones, scripts, escenas, helpers, dashboards, áreas, integraciones,
  HACS, YAML): podés LEERLA con "hacfg-{casa}", pero en esta fase NO podés cambiarla. Si la
  tarea requiere cambios de configuración, escribí un plan exacto y verificable en
  tareas/{raiz}/plan_aplicar.md: qué crear/modificar/borrar, el contenido completo (YAML o
  JSON de cada automatización, script, dashboard, etc.), en qué orden y cómo verificar.
  El dueño revisa ese plan en el PR y, si lo aprueba, se aplica en otra fase.
- Si la tarea no requiere cambios de configuración, no crees plan_aplicar.md.
- Cambios de configuración versionada: editá archivos solo dentro de casas/{casa}/ o tareas/{raiz}/.
- Nunca escribas tokens, contraseñas, URLs de acceso remoto ni contenido de secrets.yaml.
- No incluyas datos personales que no hagan falta para la tarea.
- Terminá con un resumen en español, claro y breve, de lo que encontraste o hiciste.
  Ese resumen se publica en el issue y en tareas/{raiz}/informe-{t['id']}.md."""


def prompt_aplicar(t: dict, pr: int, plan: str) -> str:
    return f"""El dueño aprobó (mergeó) el PR #{pr} de la tarea #{t['id']} en la casa "{t['casa']}".
Ahora tenés permiso de escritura sobre la configuración de Home Assistant con las herramientas
"hacfg-{t['casa']}" (y control de dispositivos con "ha-{t['casa']}").

Aplicá EXACTAMENTE este plan aprobado, sin agregar nada:
----- plan_aplicar.md -----
{plan}
----- fin del plan -----

Si el estado actual no coincide con lo que el plan espera, detenete sin cambiar nada más y
explicá la diferencia. Al terminar, verificá el resultado y resumí en español qué se aplicó."""


class Ejecutor:
    def __init__(self, cfg: Config, db: DB, gh: GitHub,
                 correr_agente: Callable[..., agentes.Resultado] = agentes.ejecutar):
        self.cfg = cfg
        self.db = db
        self.gh = gh
        self.correr_agente = correr_agente
        self._cancelar: dict[int, threading.Event] = {}
        self._parar = threading.Event()
        self._despertar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._ultima_revision_pr = 0.0
        self.ultimo_ciclo = 0.0
        self.ultimo_error = ""
        self._rama_default: str | None = None

    # --- ciclo de vida ------------------------------------------------------------------

    def iniciar(self) -> None:
        for tid in self.db.marcar_interrumpidas():
            t = self.db.tarea(tid)
            if t and t["issue"]:
                self._comentar(t, f"⏹️ Tarea #{tid} interrumpida por reinicio del servicio. No se relanza sola.")
        self._hilo = threading.Thread(target=self._bucle, name="ejecutor", daemon=True)
        self._hilo.start()
        threading.Thread(target=self._latido, name="latido", daemon=True).start()

    def _latido(self) -> None:
        """Escribe estado/salud.json cada minuto, también mientras una tarea está corriendo."""
        while not self._parar.wait(timeout=60):
            try:
                self.escribir_salud()
            except Exception:
                log.exception("no se pudo escribir salud.json")

    def detener(self) -> None:
        self._parar.set()
        for ev in self._cancelar.values():
            ev.set()
        self._despertar.set()
        if self._hilo:
            self._hilo.join(timeout=30)

    def despertar(self) -> None:
        self._despertar.set()

    def vivo(self) -> bool:
        return bool(self._hilo and self._hilo.is_alive())

    def cancelar(self, tarea_id: int) -> str:
        t = self.db.tarea(tarea_id)
        if not t:
            return "no existe"
        if t["estado"] == D.EN_COLA:
            self.db.cambiar_estado(tarea_id, D.CANCELADA, "cancelada antes de empezar")
            return "cancelada"
        if t["estado"] in D.ESTADOS_ACTIVOS:
            ev = self._cancelar.get(tarea_id)
            if ev:
                ev.set()
            return "cancelando"
        if t["estado"] == D.ESPERANDO_APROBACION:
            self.db.cambiar_estado(tarea_id, D.CANCELADA, "cancelada por el dueño; no se aplica")
            self._comentar(t, f"🚫 Tarea #{tarea_id} cancelada: el plan no se va a aplicar aunque se mergee el PR.")
            return "cancelada"
        return f"ya está {t['estado']}"

    def _bucle(self) -> None:
        while not self._parar.is_set():
            self.ultimo_ciclo = time.time()
            try:
                t = self.db.siguiente_en_cola()
                if t:
                    self._procesar(t)
                    continue
                if time.time() - self._ultima_revision_pr >= self.cfg.intervalo_pr_s:
                    self._ultima_revision_pr = time.time()
                    self._revisar_prs()
            except Exception as e:  # el bucle no debe morir
                self.ultimo_error = f"{time.strftime('%F %T')} {type(e).__name__}: {e}"[:500]
                log.exception("error en el ciclo del ejecutor")
            finally:
                self.escribir_salud()
            self._despertar.wait(timeout=30)
            self._despertar.clear()

    # --- salud --------------------------------------------------------------------------

    def salud(self) -> dict:
        conteo = {f["estado"]: f["n"] for f in self.db.todos("SELECT estado, COUNT(*) n FROM tareas GROUP BY estado")}
        # Mientras corre una tarea el ciclo no avanza; alcanza con que el hilo esté vivo.
        ok = self.vivo() and (bool(self._cancelar) or time.time() - self.ultimo_ciclo < 120)
        return {
            "ts": time.strftime("%FT%T%z"),
            "ok": bool(ok),
            "ejecutor_vivo": self.vivo(),
            "en_cola": conteo.get(D.EN_COLA, 0),
            "en_curso": conteo.get(D.EN_CURSO, 0) + conteo.get(D.APLICANDO, 0),
            "esperando_aprobacion": conteo.get(D.ESPERANDO_APROBACION, 0),
            "ultimo_error": self.ultimo_error,
        }

    def escribir_salud(self) -> None:
        destino = self.cfg.estado / "salud.json"
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.salud(), ensure_ascii=False))
        tmp.replace(destino)

    # --- tareas -------------------------------------------------------------------------

    def _rama_base(self) -> str:
        if not self._rama_default:
            self._rama_default = self.gh.rama_default()
        return self._rama_default

    def _comentar(self, t: dict, texto: str) -> None:
        try:
            if t.get("issue"):
                self.gh.comentar(t["issue"], texto)
        except Exception as e:
            log.warning("no se pudo comentar en el issue #%s: %s", t.get("issue"), e)

    def _raiz(self, t: dict) -> int:
        while t.get("continuar_de"):
            t = self.db.tarea(t["continuar_de"]) or {}
        return int(t.get("id") or 0)

    def _procesar(self, t: dict) -> None:
        tid = t["id"]
        cancelar = threading.Event()
        self._cancelar[tid] = cancelar
        log_path = self.cfg.logs / f"tarea-{self._raiz(t)}.log"
        self.db.cambiar_estado(tid, D.EN_CURSO, "", iniciada=time.time(), log_path=str(log_path))
        try:
            if self.gh.visibilidad() != "PRIVATE":
                raise ErrorTarea("el repositorio de registro no es privado; no se publican datos de las casas")
            if t["continuar_de"]:
                t = self._heredar(t)
            sesion_lock = self.cfg.locks / f"sesion-{t['sesion_id']}.lock" if t["sesion_id"] else None
            with bloqueo(self.cfg.locks / f"casa-{t['casa']}.lock", cancelar):
                with bloqueo(sesion_lock, cancelar) if sesion_lock else _nulo():
                    if not t["worktree"]:
                        t = self._preparar(t)
                    self._comentar(t, f"▶️ Tarea #{tid} en curso ({t['agente']}"
                                      f"{'/' + t['cuenta'] if t['cuenta'] else ''}).")
                    self._trabajar(t, cancelar, log_path)
        except agentes.Cancelada:
            self.db.cambiar_estado(tid, D.CANCELADA, "cancelada durante la ejecución")
            self._comentar(self.db.tarea(tid) or t, f"🚫 Tarea #{tid} cancelada.")
        except Exception as e:
            msg = str(e)[:1000]
            self.db.cambiar_estado(tid, D.ERROR, msg, error=msg)
            self._comentar(self.db.tarea(tid) or t, f"❌ Tarea #{tid} terminó con error:\n\n```\n{msg}\n```")
            log.warning("tarea %s con error: %s", tid, msg)
        finally:
            self._cancelar.pop(tid, None)

    def _heredar(self, t: dict) -> dict:
        p = self.db.tarea(t["continuar_de"])
        if not p or not p["sesion_id"] or not p["worktree"] or not Path(p["worktree"]).exists():
            raise ErrorTarea(f"la tarea #{t['continuar_de']} no tiene una sesión o copia de trabajo reanudable")
        if p["pr"] and self.gh.estado_pr(p["pr"]) != "OPEN":
            raise ErrorTarea(f"el PR #{p['pr']} ya no está abierto; creá una tarea nueva")
        campos = {k: p[k] for k in ("cuenta", "sesion_id", "issue", "rama", "pr", "worktree")}
        self.db.actualizar(t["id"], **campos)
        if p["estado"] == D.ESPERANDO_APROBACION:
            self.db.cambiar_estado(p["id"], D.TERMINADA, f"continuada en la tarea #{t['id']}")
        return self.db.tarea(t["id"])

    def _preparar(self, t: dict) -> dict:
        tid = t["id"]
        base = self._rama_base()
        issue = self.gh.crear_issue(
            f"[{t['casa']}] Tarea #{tid}: {t['descripcion'][:70]}",
            f"Tarea creada desde domotica-hub.\n\n- Casa: `{t['casa']}`\n- Agente: `{t['agente']}`"
            f"\n\n### Descripción\n\n{t['descripcion']}",
        )
        rama = f"{t['agente']}/{tid}"
        worktree = self.cfg.worktrees / str(tid)
        self.gh.git("fetch", "origin", base, cwd=self.cfg.repo)
        git_local("worktree", "add", "-b", rama, str(worktree), f"origin/{base}", cwd=self.cfg.repo)
        self.db.actualizar(tid, issue=issue, rama=rama, worktree=str(worktree))
        self.db.evento(tid, "preparada", f"issue #{issue}, rama {rama}")
        return self.db.tarea(tid)

    def _correr(self, t: dict, fase: str, prompt: str, cancelar: threading.Event, log_path: Path) -> agentes.Resultado:
        def avance(seg: float) -> None:
            self._comentar(t, f"⏳ Tarea #{t['id']} sigue en curso ({int(seg // 60)} min).")

        kwargs = dict(agente=t["agente"], casa=t["casa"], fase=fase, sesion=t["sesion_id"], prompt=prompt,
                      cwd=Path(t["worktree"]), log_path=log_path, cancelar=cancelar, avance=avance)
        r = self.correr_agente(self.cfg, cuenta=t["cuenta"], **kwargs)
        if (not r.ok and r.limite_uso and t["agente"] == "claude" and not t["cuenta_explicita"]
                and not t["sesion_id"] and t["cuenta"] == "gmail"):
            self.db.actualizar(t["id"], cuenta="bravosm")
            self.db.evento(t["id"], "respaldo", "límite de uso en gmail; se usa bravosm")
            self._comentar(t, "↪️ La cuenta principal llegó a su límite de uso; sigue con la cuenta de respaldo.")
            t = self.db.tarea(t["id"])
            r = self.correr_agente(self.cfg, cuenta="bravosm", **kwargs)
        return r

    def _trabajar(self, t: dict, cancelar: threading.Event, log_path: Path) -> None:
        tid, raiz = t["id"], self._raiz(t)
        wt = Path(t["worktree"])
        r = self._correr(t, agentes.TRABAJO, prompt_trabajo(t, raiz), cancelar, log_path)
        if r.sesion_id:
            self.db.actualizar(tid, sesion_id=r.sesion_id)
        if not r.ok:
            raise ErrorTarea(r.error or "el agente no devolvió resultado")
        t = self.db.tarea(tid)

        carpeta = wt / "tareas" / str(raiz)
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"informe-{tid}.md").write_text(
            f"# Tarea #{tid} — {t['casa']} ({t['agente']}/{t['cuenta'] or '-'})\n\n"
            f"## Pedido\n\n{t['descripcion']}\n\n## Resultado\n\n{r.texto}\n", encoding="utf-8")
        requiere = (carpeta / "plan_aplicar.md").exists()

        git_local("add", "-A", cwd=wt)
        autor = f"{t['agente']}-{t['cuenta'] or 'gmail'}"
        git_local("-c", f"user.name={autor} (domotica-hub)", "-c", f"user.email={autor}@domotica-hub.local",
                  "commit", "-q", "-m", f"Tarea #{tid}: {t['descripcion'][:60]}", cwd=wt)
        self.gh.git("push", "-q", "-u", "origin", t["rama"], cwd=wt)

        pr = t["pr"]
        if not pr:
            cuerpo = (f"Closes #{t['issue']}\n\nTarea #{tid} en `{t['casa']}`.\n\n"
                      + ("**Requiere aplicar en Home Assistant.** Revisá `tareas/"
                         f"{raiz}/plan_aplicar.md`. Mergear este PR autoriza a aplicar el plan; "
                         "cerrarlo sin merge lo descarta." if requiere else "Solo lectura: no se aplica nada en HA."))
            pr = self.gh.crear_pr(t["rama"], self._rama_base(), f"[{t['casa']}] Tarea #{tid}: {t['descripcion'][:60]}", cuerpo)
            self.db.actualizar(tid, pr=pr)

        resumen = r.texto if len(r.texto) < 60000 else r.texto[:60000] + "\n\n…(recortado; ver informe en el PR)"
        self.db.actualizar(tid, resultado=r.texto, requiere_aplicar=int(requiere))
        if requiere:
            self.db.cambiar_estado(tid, D.ESPERANDO_APROBACION, f"PR #{pr}")
            self._comentar(t, f"📝 Tarea #{tid}: plan listo en el PR #{pr}. Mergealo para aplicar, "
                              f"o cerralo sin merge para descartar.\n\n{resumen}")
        else:
            self.db.cambiar_estado(tid, D.TERMINADA, f"PR #{pr}")
            self._comentar(t, f"✅ Tarea #{tid} terminada (PR #{pr}).\n\n{resumen}")

    # --- aprobación y aplicación --------------------------------------------------------

    def _revisar_prs(self) -> None:
        for t in self.db.todos("SELECT * FROM tareas WHERE estado = ? ORDER BY id", (D.ESPERANDO_APROBACION,)):
            estado_pr = self.gh.estado_pr(t["pr"])
            if estado_pr == "MERGED":
                self._aplicar(t)
            elif estado_pr == "CLOSED":
                self.db.cambiar_estado(t["id"], D.CANCELADA, f"PR #{t['pr']} cerrado sin merge")
                self._comentar(t, f"🚫 PR #{t['pr']} cerrado sin merge: la tarea #{t['id']} no se aplica.")
                self._limpiar(t)

    def _aplicar(self, t: dict) -> None:
        tid = t["id"]
        cancelar = threading.Event()
        self._cancelar[tid] = cancelar
        log_path = Path(t["log_path"] or self.cfg.logs / f"tarea-{self._raiz(t)}.log")
        self.db.cambiar_estado(tid, D.APLICANDO, f"PR #{t['pr']} mergeado")
        try:
            base = self._rama_base()
            self.gh.git("fetch", "origin", base, cwd=self.cfg.repo)
            ruta = f"tareas/{self._raiz(t)}/plan_aplicar.md"
            try:
                plan = git_local("show", f"origin/{base}:{ruta}", cwd=self.cfg.repo)
            except ErrorTarea:
                raise ErrorTarea(f"el PR mergeado no contiene {ruta}")
            with bloqueo(self.cfg.locks / f"casa-{t['casa']}.lock", cancelar):
                with bloqueo(self.cfg.locks / f"sesion-{t['sesion_id']}.lock", cancelar):
                    self._comentar(t, f"⚙️ PR #{t['pr']} mergeado: aplicando el plan en {t['casa']}.")
                    r = self.correr_agente(
                        self.cfg, agente=t["agente"], casa=t["casa"], fase=agentes.APLICAR, cuenta=t["cuenta"],
                        sesion=t["sesion_id"], prompt=prompt_aplicar(t, t["pr"], plan), cwd=Path(t["worktree"]),
                        log_path=log_path, cancelar=cancelar, avance=None)
            if not r.ok:
                raise ErrorTarea(r.error or "el agente no devolvió resultado al aplicar")
            self.db.cambiar_estado(tid, D.TERMINADA, "aplicada", resultado=(t["resultado"] or "") + "\n\n## Aplicación\n\n" + r.texto)
            self._comentar(t, f"✅ Tarea #{tid} aplicada.\n\n{r.texto}")
            self._limpiar(t)
        except agentes.Cancelada:
            self.db.cambiar_estado(tid, D.CANCELADA, "cancelada durante la aplicación")
            self._comentar(t, f"🚫 Aplicación de la tarea #{tid} cancelada. Revisá el estado de la casa.")
        except Exception as e:
            msg = str(e)[:1000]
            self.db.cambiar_estado(tid, D.ERROR, msg, error=msg)
            self._comentar(t, f"❌ Error al aplicar la tarea #{tid}:\n\n```\n{msg}\n```")
        finally:
            self._cancelar.pop(tid, None)

    def _limpiar(self, t: dict) -> None:
        if t.get("worktree") and Path(t["worktree"]).exists():
            try:
                git_local("worktree", "remove", "--force", t["worktree"], cwd=self.cfg.repo)
            except ErrorTarea as e:
                log.warning("no se pudo borrar la copia de trabajo de #%s: %s", t["id"], e)


@contextmanager
def _nulo() -> Iterator[None]:
    yield
