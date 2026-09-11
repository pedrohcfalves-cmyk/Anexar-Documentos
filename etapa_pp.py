"""
Etapa PP: Preparação de Pagamento da Despesa Empenhada no SIGEF.

Localiza a Nota de Lançamento (NL) e a Despesa Certificada (CE) na tela
de Gerar Ordem Cronológica, confirma o item encontrado e, na tela
principal, preenche o tipo de Ordem Bancária, banco/agência/conta e
confirma — gerando o número da PP.

executar_pp() recebe `nl`, `ce` e `conta_pp` como parâmetros separados,
porque são esses os valores que essa etapa usa de verdade (o `dados`
completo do SEI(1) fica disponível caso seja preciso mais alguma coisa
depois, mas hoje não é usado). Isso permite testar essa etapa sozinha
sem precisar rodar as anteriores de novo: o bloco
"if __name__ == '__main__':" abaixo já carrega o último NL, CE e conta
PP salvos no arquivo de sessão (sessao_atual.json, ver utils.py) e
oferece como padrão — aperte Enter pra reaproveitar, ou digite um valor
novo pra trocar.
"""
from datetime import date

from utils import (
    URL_SIGEF_PP,
    carregar_sessao,
    obter_ou_criar_aba,
    perguntar_ou_reusar,
    salvar_sessao,
)


def executar_pp(context, nl: str, ce: str, conta_pp: str, dados: dict = None) -> str | None:
    """
    Executa a Etapa PP (Preparação de Pagamento da Despesa Empenhada),
    localizando o lançamento pelos números `nl` e `ce` e preparando o
    pagamento na conta `conta_pp`.

    Retorna o número da PP gerado, ou None se não for possível gerar.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_PP,
    )
    aba_sigef.goto(URL_SIGEF_PP)
    aba_sigef.wait_for_load_state("networkidle")

    ano_atual = str(date.today().year)

    # ========= SUA AUTOMAÇÃO =========

    aba_sigef.locator("#txtGestao_SIGEFPesquisa").fill("00001")

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#txtNotaLancamento_BtnPesquisa").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    with context.expect_page() as nova_pagina1_info:
        nova_pagina.locator("#lnkNaoObedeceOrdemCronologica").click()

    nova_pagina1 = nova_pagina1_info.value
    nova_pagina1.wait_for_load_state("networkidle")

    nova_pagina1.locator("#txtNotaLancamentoSigla").fill(ano_atual)
    nova_pagina1.locator("#txtDespesaCertificadaSigla").fill(ano_atual)
    nova_pagina1.locator("#txtNotaLancamento_SIGEFPesquisa").fill(nl)
    nova_pagina1.locator("#txtDespesaCertificada_SIGEFPesquisa").fill(ce)
    nova_pagina1.locator("#btnConfirmar").click()
    nova_pagina1.locator("#divdtgGerarOrdemCronologica td.GridLink").first.click()

    aba_sigef.bring_to_front()
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.wait_for_selector("#cboTipoOrdemBancaria", state="visible", timeout=5000)

    aba_sigef.locator("#txtBanco").fill("001")
    aba_sigef.locator("#txtAgencia").fill("27570")
    aba_sigef.locator("#txtConta_SIGEFPesquisa").fill(conta_pp)
    aba_sigef.locator("#cboTipoOrdemBancaria").select_option(value="3")
    aba_sigef.locator("#btnRetencoes").click()
    aba_sigef.locator("img[src*='aba_confirmacao.gif']").click()

    aba_sigef.locator("#btnConfirmar").click()

    elemento_sucesso = aba_sigef.locator("td.SIGEFMensagemSucesso").first
    if elemento_sucesso.count() == 0:
        print("Não foi possível gerar a PP.")
        return None

    pp = elemento_sucesso.inner_text().strip()
    print(f"PP gerado: {pp}")
    salvar_sessao(pp=pp)

    return pp


if __name__ == "__main__":
    # Teste isolado da Etapa PP: conecta no Chrome já aberto e pede só o
    # NL, o CE e a conta PP diretamente pelo teclado — não precisa rodar
    # as etapas anteriores de novo. Útil quando você já tem esses valores
    # de um teste anterior e só quer testar essa etapa.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        nl = perguntar_ou_reusar("Digite a NL (gerada na Etapa NL)", "nl", sessao)
        ce = perguntar_ou_reusar("Digite o CE (gerado na Etapa CE)", "ce", sessao)
        conta_pp = perguntar_ou_reusar("Digite a conta PP", "conta_pp", sessao)
        pp = executar_pp(context, nl, ce, conta_pp)
        print(f"OK: PP processado para a NL '{nl}'. Número da PP: {pp}")
    finally:
        playwright.stop()
