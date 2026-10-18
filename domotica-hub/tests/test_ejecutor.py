from __future__ import annotations

import threading
from pathlib import Path

from conftest import mergear

from domotica_hub import db as D
from domotica_hub.agentes import Resultado
from domotica_hub.ejecutor import Ejecutor


class AgenteFalso:
    """Registra las llamadas y simula el trabajo del agente en la copia de trabajo."""

    def __init__(self, plan: bool = False, limite_en: tuple[str, ...] = ()):
        self.plan = plan
        self.limite_en = limite_en
        self.llamadas: list[dict] = []

    def __call__(self, cfg, *, agente, casa, fase, cuenta, sesion, prompt, cwd: Path, log_path, cancelar, avance):
        self.llamadas.append({"agente": agente, "fase": fase, "cuenta": cuenta, "sesion": sesion, "prompt": prompt})
        if cuenta in self.limite_en:
            return Resultado(False, None, "", error="usage limit", limite_uso=True)
        if fase == "trabajo" and self.plan:
            carpeta = cwd / "tareas" / prompt.split("tareas/")[1].split("/")[0]
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / "plan_aplicar.md").write_text("1. Encender luz.cocina\n")
        return Resultado(True, sesion or f"sesion-{len(self.llamadas)}", f"hecho ({fase})")


def _ejecutor(e, agente) -> Ejecutor:
    return Ejecutor(e["cfg"], e["db"], e["gh"], correr_agente=agente)


def test_tarea_solo_lectura_termina_con_issue_rama_y_pr(entorno):
    e = entorno
    ag = AgenteFalso()
    ej = _ejecutor(e, ag)
    tid = e["db"].crear_tarea("lote101", "claude", "¿Qué luces están encendidas?", "gmail", False)
    ej._procesar(e["db"].siguiente_en_cola())

    t = e["db"].tarea(tid)
    assert t["estado"] == D.TERMINADA
    assert t["rama"] == f"claude/{tid}" and t["issue"] and t["pr"]
    assert t["sesion_id"] == "sesion-1"
    assert ag.llamadas[0]["fase"] == "trabajo"
    assert e["gh"].prs[t["pr"]]["cuerpo"].startswith(f"Closes #{t['issue']}")
    assert (Path(t["worktree"]) / "tareas" / str(tid) / f"informe-{tid}.md").exists()


def test_plan_espera_aprobacion_y_se_aplica_al_mergear(entorno):
    e = entorno
    ag = AgenteFalso(plan=True)
    ej = _ejecutor(e, ag)
    tid = e["db"].crear_tarea("lote101", "codex", "Encender la luz de la cocina", "gmail", False)
    ej._procesar(e["db"].siguiente_en_cola())
    t = e["db"].tarea(tid)
    assert t["estado"] == D.ESPERANDO_APROBACION and t["requiere_aplicar"]

    ej._revisar_prs()  # PR abierto: no pasa nada
    assert e["db"].tarea(tid)["estado"] == D.ESPERANDO_APROBACION
    assert [l["fase"] for l in ag.llamadas] == ["trabajo"]

    mergear(e["origen"], t["rama"], e["tmp"])
    e["gh"].prs[t["pr"]]["estado"] = "MERGED"
    ej._revisar_prs()
    t = e["db"].tarea(tid)
    assert t["estado"] == D.TERMINADA
    aplicar = ag.llamadas[-1]
    assert aplicar["fase"] == "aplicar" and aplicar["sesion"] == "sesion-1"
    assert "Encender luz.cocina" in aplicar["prompt"]
    assert not Path(t["worktree"]).exists()


def test_pr_cerrado_sin_merge_cancela(entorno):
    e = entorno
    ej = _ejecutor(e, AgenteFalso(plan=True))
    tid = e["db"].crear_tarea("lote101", "claude", "Cambiar la escena de la noche", "gmail", False)
    ej._procesar(e["db"].siguiente_en_cola())
    e["gh"].prs[e["db"].tarea(tid)["pr"]]["estado"] = "CLOSED"
    ej._revisar_prs()
    assert e["db"].tarea(tid)["estado"] == D.CANCELADA


def test_repo_publico_no_publica_nada(entorno):
    e = entorno
    e["gh"].visible = "PUBLIC"
    ag = AgenteFalso()
    ej = _ejecutor(e, ag)
    tid = e["db"].crear_tarea("lote101", "claude", "¿Qué luces están encendidas?", "gmail", False)
    ej._procesar(e["db"].siguiente_en_cola())
    t = e["db"].tarea(tid)
    assert t["estado"] == D.ERROR and "no es privado" in t["error"]
    assert not ag.llamadas and not e["gh"].issues


def test_respaldo_a_bravosm_por_limite_de_uso(entorno):
    e = entorno
    ag = AgenteFalso(limite_en=("gmail",))
    ej = _ejecutor(e, ag)
    tid = e["db"].crear_tarea("lote101", "claude", "¿Qué luces están encendidas?", "gmail", False)
    ej._procesar(e["db"].siguiente_en_cola())
    t = e["db"].tarea(tid)
    assert t["estado"] == D.TERMINADA and t["cuenta"] == "bravosm"
    assert [l["cuenta"] for l in ag.llamadas] == ["gmail", "bravosm"]


def test_cuenta_explicita_no_usa_respaldo(entorno):
    e = entorno
    ej = _ejecutor(e, AgenteFalso(limite_en=("gmail",)))
    tid = e["db"].crear_tarea("lote101", "claude", "¿Qué luces están encendidas?", "gmail", True)
    ej._procesar(e["db"].siguiente_en_cola())
    assert e["db"].tarea(tid)["estado"] == D.ERROR


def test_continuar_reutiliza_sesion_rama_y_pr(entorno):
    e = entorno
    ag = AgenteFalso()
    ej = _ejecutor(e, ag)
    t1 = e["db"].crear_tarea("lote101", "claude", "¿Qué luces están encendidas?", "gmail", False)
    ej._procesar(e["db"].siguiente_en_cola())
    t2 = e["db"].crear_tarea("lote101", "claude", "¿Y cuáles están en el patio?", "gmail", False, continuar_de=t1)
    ej._procesar(e["db"].siguiente_en_cola())
    a, b = e["db"].tarea(t1), e["db"].tarea(t2)
    assert b["estado"] == D.TERMINADA
    assert (b["sesion_id"], b["rama"], b["pr"], b["issue"]) == (a["sesion_id"], a["rama"], a["pr"], a["issue"])
    assert ag.llamadas[1]["sesion"] == a["sesion_id"]
    assert len(e["gh"].prs) == 1


def test_cancelar_en_cola_y_arranque_marca_interrumpidas(entorno):
    e = entorno
    ej = _ejecutor(e, AgenteFalso())
    t1 = e["db"].crear_tarea("lote101", "claude", "Tarea que se cancela", "gmail", False)
    assert ej.cancelar(t1) == "cancelada"
    t2 = e["db"].crear_tarea("lote101", "claude", "Tarea que quedó corriendo", "gmail", False)
    e["db"].cambiar_estado(t2, D.EN_CURSO)
    assert e["db"].marcar_interrumpidas() == [t2]
    assert e["db"].tarea(t2)["estado"] == D.INTERRUMPIDA
    assert e["db"].siguiente_en_cola() is None


def test_salud_escribe_archivo(entorno):
    e = entorno
    ej = _ejecutor(e, AgenteFalso())
    ej._hilo = threading.Thread(target=lambda: None)
    ej.escribir_salud()
    assert (e["cfg"].estado / "salud.json").exists()
