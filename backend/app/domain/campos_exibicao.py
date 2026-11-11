"""Exibir campo personalizado da oportunidade a partir de uma etapa (contrato Núcleo parte 2, §4). Funções puras.

`exibir_funil_id` + `exibir_etapa_id` (null = sempre). O campo aparece nas oportunidades DAQUELE funil quando a etapa
atual tem ordem ≥ a da etapa escolhida (etapa null = qualquer etapa do funil); em outro funil não aparece.
Exigir o campo numa etapa em que ele ainda não aparece (etapa anterior, ou outro funil) é contradição → 400.
"""

from dataclasses import dataclass

from app.domain import RegraViolada


@dataclass(frozen=True)
class EtapaRef:
    id: int
    funil_id: int
    ordem: int


def validar_exibicao(*, objeto: str, exibir_funil_id: int | None, exibir_etapa: EtapaRef | None,
                     exigido_etapa: EtapaRef | None) -> int | None:
    """Confere a combinação e devolve o funil de exibição (deduzido da etapa quando só ela veio)."""
    if exibir_funil_id is None and exibir_etapa is None:
        return None
    if objeto != "oportunidade":
        raise RegraViolada("Só campos de oportunidade podem ser exibidos a partir de uma etapa.")
    funil = exibir_funil_id if exibir_funil_id is not None else exibir_etapa.funil_id
    if exibir_etapa is not None and exibir_etapa.funil_id != funil:
        raise RegraViolada("A etapa de exibição não pertence ao funil escolhido.")
    if exigido_etapa is not None:
        if exigido_etapa.funil_id != funil:
            raise RegraViolada("O campo é exigido numa etapa de outro funil, onde ele não aparece. Exija numa etapa "
                               "do mesmo funil em que ele é exibido.")
        if exibir_etapa is not None and exigido_etapa.ordem < exibir_etapa.ordem:
            raise RegraViolada("O campo é exigido numa etapa anterior à etapa em que ele passa a aparecer. Exija "
                               "na mesma etapa de exibição ou depois.")
    return funil


def visivel_na_oportunidade(*, exibir_funil_id: int | None, exibir_etapa_ordem: int | None, funil_id: int | None,
                            etapa_ordem: int | None) -> bool:
    """O campo aparece numa oportunidade do `funil_id` na etapa de ordem `etapa_ordem`?"""
    if exibir_funil_id is None:
        return True
    if funil_id != exibir_funil_id:
        return False
    if exibir_etapa_ordem is None:
        return True
    return etapa_ordem is not None and etapa_ordem >= exibir_etapa_ordem
