"""
Etapa NL: Liquidar Despesa Certificada no SIGEF.

Ainda NÃO implementada — este módulo existe só para reservar o lugar
dessa etapa no fluxo (SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)) e permitir
que main.py já a chame, pulando-a com um aviso até que seja implementada.
"""
from utils import URL_SIGEF_NL  # já disponível para quando for implementar


def executar_nl(context, *args, **kwargs) -> None:
    """Executa a Etapa NL. TODO: implementar o preenchimento da tela em URL_SIGEF_NL."""
    raise NotImplementedError("Etapa NL (Liquidar Despesa Certificada) ainda não implementada.")


if __name__ == "__main__":
    print("Etapa NL ainda não implementada.")
