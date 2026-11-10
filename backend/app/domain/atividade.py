"""Atividades. Reunião exige início < fim no mesmo dia. Criar atividade ≠ enviar mensagem."""

from datetime import date, time

from app.domain import RegraViolada

TIPOS = ("tarefa", "email", "ligacao", "whatsapp", "reuniao")
STATUS = ("pendente", "concluida")
ORIGENS = ("manual", "automacao", "ia")


def validar_atividade(*, assunto: str | None, tipo: str, prazo: date | None, hora_inicio: time | None,
                      hora_fim: time | None) -> None:
    if not (assunto or "").strip():
        raise RegraViolada("Informe o assunto da atividade.")
    if tipo not in TIPOS:
        raise RegraViolada("Tipo de atividade inválido.")
    if prazo is None:
        raise RegraViolada("Informe o prazo da atividade.")
    if tipo == "reuniao" and (hora_inicio is None or hora_fim is None or hora_inicio >= hora_fim):
        raise RegraViolada("Reunião exige início e fim válido no mesmo dia")
    if tipo != "reuniao" and hora_inicio and hora_fim and hora_inicio >= hora_fim:
        raise RegraViolada("O horário final deve ser depois do inicial.")


def atrasada(*, prazo: date, status: str, hoje: date) -> bool:
    return status == "pendente" and prazo < hoje


def validar_conclusao(status: str) -> str:
    if status == "concluida":
        raise RegraViolada("Esta atividade já foi concluída.")
    return "concluida"
