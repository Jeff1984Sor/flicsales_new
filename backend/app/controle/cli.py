"""Terminal do banco de controle (um banco por organização). Portado do MayaFit (app/controle/cli.py).

    python -m app.controle.cli ativar [--slug-principal flic-demo]   # cria o flicsales_controle e registra o principal
    python -m app.controle.cli migrar                                # controle + banco de cada organização
    python -m app.controle.cli nova-organizacao --slug acme --nome "Acme" --admin-email ana@acme.com --admin-login ana
    python -m app.controle.cli dominio --slug acme --host app.acme.com.br
    python -m app.controle.cli status --slug acme --valor inativo
    python -m app.controle.cli sincronizar-logins [--slug acme]
    python -m app.controle.cli listar

A senha nunca vai na linha de comando: `--senha-stdin` lê da entrada padrão; sem ela, vai convite por link.
"""

import argparse
import sys

from app.controle import service
from app.controle.models import OrganizacaoCliente, SessaoControle
from app.core import tenancy


def _ativar(slug_principal: str | None) -> None:
    """Cria o banco de controle (no SQLite, o arquivo) e migra. Daqui em diante o modo multi liga sozinho."""
    from pathlib import Path

    from sqlalchemy.engine import make_url

    url = make_url(tenancy.url_controle())
    if url.get_backend_name() == "sqlite":
        Path(url.database or "").parent.mkdir(parents=True, exist_ok=True)
    else:
        service.criar_banco(tenancy.BANCO_CONTROLE)
    service.migrar_controle()
    tenancy.forcar_controle(None)  # redetecta: agora o controle existe
    slug = service.registrar_principal_se_faltar(slug_principal)
    print(f"Banco {tenancy.BANCO_CONTROLE} pronto. Um banco por organização ATIVO (reinicie a API e o worker).")
    if slug:
        print(f"A organização do banco principal entrou no controle como {slug} (logins no catálogo).")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="app.controle.cli", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ativar", help="cria o banco de controle e migra (liga o modo um banco por organização)")
    p.add_argument("--slug-principal", help="slug da organização que já mora no banco principal (padrão: pelo nome)")
    sub.add_parser("migrar", help="controle + banco de cada organização ativa")
    sub.add_parser("listar")
    p = sub.add_parser("nova-organizacao", help="organização nova, com banco próprio e o Gestor")
    p.add_argument("--slug", required=True)
    p.add_argument("--nome", required=True)
    p.add_argument("--admin-email", required=True)
    p.add_argument("--admin-login", help="login do Gestor (obrigatório sem --primeiro-acesso)")
    p.add_argument("--primeiro-acesso", action="store_true", help="quem contratou cria o Gestor pelo link")
    p.add_argument("--admin-nome", default="")
    p.add_argument("--senha-stdin", action="store_true", help="lê a senha do Gestor da entrada padrão")
    p.add_argument("--dominio", action="append", default=[])
    p = sub.add_parser("dominio", help="acrescenta um domínio a uma organização")
    p.add_argument("--slug", required=True)
    p.add_argument("--host", required=True)
    p = sub.add_parser("status", help="ativo | suspenso | inativo")
    p.add_argument("--slug", required=True)
    p.add_argument("--valor", required=True)
    p = sub.add_parser("sincronizar-logins", help="reconstrói o catálogo de logins (todas sem --slug)")
    p.add_argument("--slug")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "ativar":
            _ativar(a.slug_principal)
            return
        if not tenancy.multi():
            if a.cmd == "migrar":  # o deploy sempre chama: sem banco de controle, nada a fazer
                print(f"Sem o banco {tenancy.BANCO_CONTROLE}: um banco só, nada a migrar no controle.")
                return
            sys.exit(f"Sem o banco {tenancy.BANCO_CONTROLE}. Rode antes: python -m app.controle.cli ativar")
        import app.controle.sincronia  # noqa: F401  (catálogo de logins)

        if a.cmd == "migrar":
            print("Migradas:", ", ".join(service.migrar_todos()) or "(só o controle)")
        elif a.cmd == "nova-organizacao":
            senha = sys.stdin.readline().rstrip("\r\n") if a.senha_stdin else None
            _, link = service.provisionar(a.slug, a.nome, admin_email=a.admin_email, admin_login=a.admin_login,
                                          admin_nome=a.admin_nome, admin_senha=senha, dominios=a.dominio,
                                          primeiro_acesso=a.primeiro_acesso)
            print(f"Organização {a.slug} criada no banco {service.nome_do_banco(a.slug)}.")
            if link:
                print(("Link de primeiro acesso: " if a.primeiro_acesso else "Convite do Gestor: ") + link)
        elif a.cmd == "dominio":
            with SessaoControle() as db:
                c = db.query(OrganizacaoCliente).filter_by(slug=a.slug).one_or_none()
                if not c:
                    sys.exit(f"Organização {a.slug} não existe.")
                service.adicionar_dominio(db, c, a.host)
                db.commit()
            print(f"{a.host} -> {a.slug}")
        elif a.cmd == "status":
            service.definir_status(a.slug, a.valor)
            print(f"{a.slug}: {a.valor}")
        elif a.cmd == "sincronizar-logins":
            slugs = [a.slug] if a.slug else [o.slug for o in service.ativas()]
            for slug in slugs:
                print(f"{slug}: {service.sincronizar_todos(slug)} usuário(s) no catálogo.")
        elif a.cmd == "listar":
            with SessaoControle() as db:
                for c in db.query(OrganizacaoCliente).order_by(OrganizacaoCliente.id):
                    doms = ", ".join(d.host for d in c.dominios) or "-"
                    print(f"{c.slug:20} {c.status:9} {c.banco or '(principal)':28} {doms}")
    except service.RegraControle as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
