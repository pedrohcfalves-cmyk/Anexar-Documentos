"""
Etapa OB: Ordem Bancária no SIGEF.

Ainda NÃO implementada — este módulo existe só para reservar o lugar
dessa etapa no fluxo (SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)) e permitir
que main.py já a chame, pulando-a com um aviso até que seja implementada.
"""
from utils import URL_SIGEF_OB  # já disponível para quando for implementar


def executar_ob(context, *args, **kwargs) -> None:
    """Executa a Etapa OB. TODO: implementar o preenchimento da tela em URL_SIGEF_OB."""
    raise NotImplementedError("Etapa OB (Ordem Bancária) ainda não implementada.")


if __name__ == "__main__":
    print("Etapa OB ainda não implementada.")
