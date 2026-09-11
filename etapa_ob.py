"""
Etapa OB: Ordem Bancária no SIGEF.

Ainda NÃO implementada — este módulo existe só para reservar o lugar
dessa etapa no fluxo (SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)).

executar_ob() já recebe o `pp` (número gerado na Etapa PP) como
parâmetro, porque é isso que essa tela do SIGEF deve usar pra localizar
o lançamento a pagar — mesmo esquema usado no NL/PP, encadeando o
resultado de uma etapa como entrada da próxima. Assim, quando for
implementada, dá pra testar essa etapa sozinha sem precisar rodar as
anteriores de novo: o bloco "if __name__ == '__main__':" abaixo já
carrega o último PP salvo no arquivo de sessão (sessao_atual.json, ver
utils.py) e oferece como padrão — aperte Enter pra reaproveitar, ou
digite um valor novo pra trocar.
"""
from utils import URL_SIGEF_OB, carregar_sessao, perguntar_ou_reusar  # já disponível para quando for implementar


def executar_ob(context, pp: str, dados: dict = None) -> str | None:
    """
    Executa a Etapa OB (Ordem Bancária), localizando o lançamento pelo
    número `pp`.

    TODO: implementar o preenchimento da tela em URL_SIGEF_OB.

    Deve retornar o número da OB gerada, para uso na Etapa SEI(2) (que
    provavelmente vai anexar/registrar esse número no processo do SEI).
    """
    raise NotImplementedError("Etapa OB (Ordem Bancária) ainda não implementada.")


if __name__ == "__main__":
    # Teste isolado da Etapa OB: conecta no Chrome já aberto e pede só a
    # PP diretamente pelo teclado — não precisa rodar as etapas
    # anteriores de novo. Útil quando você já tem uma PP de um teste
    # anterior e só quer testar essa etapa.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        pp = perguntar_ou_reusar("Digite a PP (gerada na Etapa PP)", "pp", sessao)
        ob = executar_ob(context, pp)
        print(f"OK: OB processado para a PP '{pp}'. Número da OB: {ob}")
    finally:
        playwright.stop()
