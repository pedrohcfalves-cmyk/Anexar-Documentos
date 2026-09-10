"""
Etapa PP: Preparação de Pagamento da Despesa Empenhada no SIGEF.

Ainda NÃO implementada — este módulo existe só para reservar o lugar
dessa etapa no fluxo (SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)) e permitir
que main.py já a chame, pulando-a com um aviso até que seja implementada.
"""
from utils import URL_SIGEF_PP  # já disponível para quando for implementar


def executar_pp(context, *args, **kwargs) -> None:
    """Executa a Etapa PP. TODO: implementar o preenchimento da tela em URL_SIGEF_PP."""
    raise NotImplementedError("Etapa PP (Preparação de Pagamento) ainda não implementada.")


if __name__ == "__main__":
    print("Etapa PP ainda não implementada.")
