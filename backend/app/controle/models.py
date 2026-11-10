"""Banco de controle da FlicSales (`flicsales_controle`): quais organizações existem, onde mora o banco de cada uma,
por quais domínios elas entram e a quem pertence cada login. Nenhuma organização enxerga este banco.

Portado do MayaFit (app/controle/models.py) SÓ com o mínimo para resolver organização/domínio/login. Planos, cobrança,
contratos e indicação ficam para a fase do Admin FlicSales (docs/PROGRESSO.md, fase 4).
"""

from datetime import datetime

from sqlalchemy import ForeignKey, MetaData, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.core.db import NAMING, UtcDateTime, agora


class BaseControle(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class OrganizacaoCliente(BaseControle):
    """Uma organização cliente da FlicSales."""

    __tablename__ = "organizacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)  # identificador curto (acme, flic-demo…)
    nome: Mapped[str] = mapped_column(String(200))
    banco: Mapped[str | None] = mapped_column(String(63), unique=True)  # None = banco principal (DATABASE_URL)
    status: Mapped[str] = mapped_column(String(15), default="ativo")  # ativo | suspenso | inativo (sem acesso)
    criado_em: Mapped[datetime] = mapped_column(UtcDateTime(), default=agora)

    dominios: Mapped[list["Dominio"]] = relationship(back_populates="organizacao", cascade="all, delete-orphan",
                                                     order_by="Dominio.id")


class Dominio(BaseControle):
    """Endereço da organização (subdomínio <slug>.<domínio base> ou domínio próprio)."""

    __tablename__ = "dominio"

    id: Mapped[int] = mapped_column(primary_key=True)
    organizacao_id: Mapped[int] = mapped_column(ForeignKey("organizacao.id", ondelete="CASCADE"), index=True)
    host: Mapped[str] = mapped_column(String(253), unique=True)

    organizacao: Mapped[OrganizacaoCliente] = relationship(back_populates="dominios")


class Login(BaseControle):
    """Catálogo de logins: no endereço principal, o login diz de qual organização é a pessoa. Logins curtos
    ("francine") podem se repetir entre organizações; nesse caso só se entra pelo endereço da organização."""

    __tablename__ = "login"

    chave: Mapped[str] = mapped_column(String(200), primary_key=True)  # login, minúsculo
    organizacao_id: Mapped[int] = mapped_column(ForeignKey("organizacao.id", ondelete="CASCADE"), primary_key=True,
                                                index=True)
    usuario_id: Mapped[int]


_engine = None
_fabrica = None


def SessaoControle():  # noqa: N802 — usado como SessionLocal
    global _engine, _fabrica
    if _fabrica is None:
        from app.core import tenancy

        url = tenancy.url_controle()
        args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
        _engine = create_engine(url, pool_pre_ping=True, connect_args=args)
        _fabrica = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _fabrica()


def engine_controle():
    SessaoControle().close()
    return _engine


def reiniciar_engine() -> None:
    """Testes: esquece o engine para reapontar o controle (tenancy.forcar_controle)."""
    global _engine, _fabrica
    if _engine is not None:
        _engine.dispose()
    _engine = _fabrica = None
