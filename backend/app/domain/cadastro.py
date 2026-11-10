"""Cadastro único compartilhado (empresa, pessoa, produto): nome obrigatório e sem duplicidade.

A empresa é UM cadastro para os três módulos; o nome basta para começar. "Aurora Consultoria", " aurora  consultoria"
e "Aurora Consultória" são a mesma empresa: a chave normalizada (`chave_de_nome`) é única no banco.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.domain import RegraViolada

PAPEIS_EMPRESA = ("prospect", "cliente", "fornecedor", "parceiro")


def chave_de_nome(nome: str) -> str:
    """Minúsculas, sem acento, espaços colapsados. Usada na UNIQUE `empresa.nome_chave`."""
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def validar_nome(nome: str | None, *, o_que: str = "o nome") -> str:
    limpo = re.sub(r"\s+", " ", (nome or "")).strip()
    if not limpo:
        raise RegraViolada(f"Informe {o_que}.")
    return limpo


def validar_nome_unico(nome: str, chaves_existentes: set[str]) -> None:
    """`chaves_existentes` = chaves das OUTRAS empresas (exclua a própria ao renomear)."""
    if chave_de_nome(nome) in chaves_existentes:
        raise RegraViolada("Já existe empresa com este nome")


def validar_papeis(papeis: list[str]) -> list[str]:
    desconhecidos = [p for p in papeis if p not in PAPEIS_EMPRESA]
    if desconhecidos:
        raise RegraViolada(f"Papel de empresa desconhecido: {', '.join(desconhecidos)}.")
    return [p for p in PAPEIS_EMPRESA if p in papeis]


# ================================================================================================= documentos e CEP
UFS = ("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ",
       "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO")


def so_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def _dv_cnpj(base: str) -> str:
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for _ in range(2):
        soma = sum(int(d) * p for d, p in zip(base, pesos[-len(base):], strict=True))
        resto = soma % 11
        base += "0" if resto < 2 else str(11 - resto)
    return base[-2:]


def cnpj_valido(cnpj: str | None) -> bool:
    d = so_digitos(cnpj)
    return len(d) == 14 and len(set(d)) > 1 and _dv_cnpj(d[:12]) == d[12:]


def formatar_cnpj(cnpj: str) -> str:
    d = so_digitos(cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def validar_cnpj(cnpj: str | None) -> str:
    """Confere os dígitos verificadores e devolve o CNPJ formatado (00.000.000/0000-00)."""
    if not cnpj_valido(cnpj):
        raise RegraViolada("CNPJ inválido.")
    return formatar_cnpj(cnpj)


def cpf_valido(cpf: str | None) -> bool:
    d = so_digitos(cpf)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[n]):
            return False
    return True


def validar_documento(doc: str | None) -> str | None:
    """CNPJ (14 dígitos) ou CPF (11 dígitos) válido, formatado. Vazio → None."""
    d = so_digitos(doc)
    if not d:
        return None
    if len(d) == 14:
        return validar_cnpj(d)
    if len(d) == 11:
        if not cpf_valido(d):
            raise RegraViolada("CPF inválido.")
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    raise RegraViolada("Documento inválido: informe um CNPJ (14 dígitos) ou CPF (11 dígitos).")


def validar_cep(cep: str | None) -> str:
    """CEP com 8 dígitos → "00000-000"."""
    d = so_digitos(cep)
    if len(d) != 8:
        raise RegraViolada("CEP inválido: informe os 8 dígitos.")
    return f"{d[:5]}-{d[5:]}"


def validar_uf(uf: str | None) -> str:
    sigla = (uf or "").strip().upper()
    if sigla not in UFS:
        raise RegraViolada("UF inválida: use a sigla do estado (ex.: SP).")
    return sigla


# ================================================================================================= endereço
CAMPOS_ENDERECO = ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")


def normalizar_endereco(dados: dict) -> dict:
    """Normaliza as chaves de endereço presentes em `dados` (CEP 00000-000, UF maiúscula, texto sem espaços sobrando).
    Chaves ausentes continuam ausentes (update grava só o enviado); vazio vira None."""
    out = dict(dados)
    for k in CAMPOS_ENDERECO:
        if k not in out:
            continue
        v = out[k]
        v = re.sub(r"\s+", " ", str(v)).strip() if v is not None else None
        if not v:
            out[k] = None
        elif k == "cep":
            out[k] = validar_cep(v)
        elif k == "uf":
            out[k] = validar_uf(v)
        else:
            out[k] = v
    return out


def endereco_de(registro) -> dict:
    """As 7 chaves de endereço de um objeto (ou dicionário)."""
    if isinstance(registro, dict):
        return {k: registro.get(k) for k in CAMPOS_ENDERECO}
    return {k: getattr(registro, k, None) for k in CAMPOS_ENDERECO}


def endereco_vazio(endereco: dict) -> bool:
    return all(not endereco.get(k) for k in CAMPOS_ENDERECO)


def resolver_endereco_pessoa(*, marca_atual: bool, endereco_atual: dict, enviado: dict, marca_enviada: bool | None,
                             endereco_empresa: dict | None) -> tuple[bool, dict]:
    """Decide a marca `usa_endereco_da_empresa` e o endereço final da pessoa (criar ou editar).

    - a tela mandou a marca → vale o que ela mandou;
    - senão, editar o endereço manualmente (algum campo enviado diferente do atual) desliga a marca;
    - marca ligada e pessoa com empresa → o endereço da pessoa é o da empresa (o enviado é ignorado);
    - caso contrário fica o endereço atual com o que foi enviado por cima.
    Devolve (marca, endereço com as 7 chaves).
    """
    enviado = {k: v for k, v in enviado.items() if k in CAMPOS_ENDERECO}
    if marca_enviada is not None:
        marca = marca_enviada
    else:
        editou = any(v != endereco_atual.get(k) for k, v in enviado.items())
        marca = False if editou else marca_atual
    if marca and endereco_empresa is not None:
        return True, endereco_de(endereco_empresa)
    return marca, {**endereco_de(endereco_atual), **enviado}


@dataclass(frozen=True)
class PessoaEndereco:
    id: int
    usa_endereco_da_empresa: bool
    endereco: dict


def propagar_endereco(endereco_empresa: dict, pessoas: list[PessoaEndereco]) -> list[tuple[int, dict]]:
    """Endereço da empresa mudou: as pessoas com a marca ligada recebem o novo endereço; quem desligou a marca não é
    tocado. Devolve [(pessoa_id, novo endereço)] só de quem muda de fato."""
    novo = endereco_de(endereco_empresa)
    return [(p.id, dict(novo)) for p in pessoas
            if p.usa_endereco_da_empresa and endereco_de(p.endereco) != novo]


# ================================================================================================= aplicar consulta CNPJ
CAMPOS_PREENCHIVEIS_CNPJ = ("nome_fantasia", "segmento", "porte", "telefone", "email_financeiro", *CAMPOS_ENDERECO)


def preencher_vazios(atual: dict, consulta: dict, campos: tuple[str, ...] = CAMPOS_PREENCHIVEIS_CNPJ) -> dict:
    """O que a consulta pública traz para os campos VAZIOS do cadastro (o que o usuário já preencheu não muda).
    Devolve só {campo: valor novo}."""
    return {c: consulta[c] for c in campos if not atual.get(c) and consulta.get(c)}
