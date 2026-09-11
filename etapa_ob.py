"""
Etapa OB: Ordem Bancária no SIGEF.

Localiza a Preparação de Pagamento (PP) gerada na etapa anterior e
preenche a tela de Ordem Bancária pra gerar o número da OB.

executar_ob() recebe `pp` e `conta_ob` como parâmetros separados, no
mesmo esquema usado na Etapa PP (nl/ce/conta_pp): são os valores que
essa etapa usa de verdade, e isso permite testar essa etapa sozinha sem
precisar rodar as anteriores de novo -- o bloco
"if __name__ == '__main__':" abaixo já carrega a última PP e a conta OB
salvas no arquivo de sessão (sessao_atual.json, ver utils.py) e oferece
como padrão -- aperte Enter pra reaproveitar, ou digite um valor novo
pra trocar.

Preencha o trecho "SUA AUTOMAÇÃO" abaixo com os seletores reais (mesmo
processo que você já fez na etapa_nl.py e na etapa_pp.py: abre a tela no
navegador, inspeciona os campos com o DevTools do Chrome e usa o id/name
de cada um). Algumas coisas pra manter o padrão do resto do projeto:

  - Se algum clique abrir uma aba nova (context.expect_page()), feche
    essa aba com .close() (dentro de um try/except, igual nas outras
    etapas) assim que ela já tiver cumprido o papel dela -- senão as
    abas ficam acumulando no Chrome a cada execução.
  - Se algum <select> tiver onchange (dispara postback/recarrega parte
    da tela), selecione ele ANTES de preencher os campos que vêm depois
    -- foi exatamente isso que causava o bug da Etapa PP (os campos
    sumiam sozinhos porque eram preenchidos antes do select).
  - No final, salve o número gerado com salvar_sessao(ob=ob) e retorne
    ele -- é isso que permite a Etapa SEI(2) (ainda não implementada)
    reaproveitar esse valor depois.
"""
from utils import URL_SIGEF_OB, carregar_sessao, obter_ou_criar_aba, perguntar_ou_reusar, salvar_sessao


def executar_ob(context, pp: str, conta_ob: str, dados: dict = None) -> str | None:
    """
    Executa a Etapa OB (Ordem Bancária), localizando o lançamento pelo
    número `pp` e gerando a Ordem Bancária na conta `conta_ob`.

    Retorna o número da OB gerado, ou None se não for possível gerar.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_OB,
    )
    aba_sigef.goto(URL_SIGEF_OB)
    aba_sigef.wait_for_load_state("networkidle")

    # ========= SUA AUTOMAÇÃO =========
    # Preencha aqui com os seletores reais da tela de Ordem Bancária.
    # Exemplo do formato usado nas outras etapas (ajuste os ids reais):
    #
    #   aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")
    #   aba_sigef.locator("#txtPreparacaoPagamento_SIGEFPesquisa").fill(pp)
    #   aba_sigef.locator("#btnConfirmar").click()
    #   ...
    #   aba_sigef.locator("#txtConta_SIGEFPesquisa").fill(conta_ob)

    raise NotImplementedError("Etapa OB (Ordem Bancária) ainda não implementada.")

    # Quando implementar, troque o "raise" acima e finalize assim (mesmo
    # padrão usado na Etapa PP, ajuste o seletor da mensagem de sucesso
    # se for diferente):
    #
    #   elemento_sucesso = aba_sigef.locator("td.SIGEFMensagemSucesso").first
    #   if elemento_sucesso.count() == 0:
    #       print("Não foi possível gerar a OB.")
    #       return None
    #
    #   ob = elemento_sucesso.inner_text().strip()
    #   print(f"OB gerada: {ob}")
    #   salvar_sessao(ob=ob)
    #
    #   return ob


if __name__ == "__main__":
    # Teste isolado da Etapa OB: conecta no Chrome já aberto e pede só a
    # PP e a conta OB diretamente pelo teclado — não precisa rodar as
    # etapas anteriores de novo. Útil quando você já tem esses valores de
    # um teste anterior e só quer testar essa etapa.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        pp = perguntar_ou_reusar("Digite a PP (gerada na Etapa PP)", "pp", sessao)
        conta_ob = perguntar_ou_reusar("Digite a conta OB", "conta_ob", sessao)
        ob = executar_ob(context, pp, conta_ob)
        print(f"OK: OB processada para a PP '{pp}'. Número da OB: {ob}")
    finally:
        playwright.stop()
