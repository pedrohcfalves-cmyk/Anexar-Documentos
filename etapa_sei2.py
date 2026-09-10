"""
Etapa SEI (2): voltar ao SEI para anexar os documentos gerados
(ex.: o JPG da Despesa Certificada) de volta ao processo.

Ainda NÃO implementada — este módulo existe só para reservar o lugar
dessa etapa no fluxo (SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)) e permitir
que main.py já a chame, pulando-a com um aviso até que seja implementada.
"""


def executar_sei2(aba_sei, arquivos: list[str] = None, *args, **kwargs) -> None:
    """Executa a Etapa SEI (2). TODO: implementar o upload/anexação dos arquivos gerados no processo do SEI."""
    raise NotImplementedError("Etapa SEI (2) (anexar documentos ao processo) ainda não implementada.")


if __name__ == "__main__":
    print("Etapa SEI (2) ainda não implementada.")
