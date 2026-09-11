"""
Etapa NL: Liquidar Despesa Certificada no SIGEF.

Localiza a Despesa Certificada pelo `ce`, adiciona a data de vencimento,
vincula a Nota de Empenho, preenche o valor bruto e trata as retenções.
No final, varre a grade de resultados procurando a linha cujo valor
líquido bate com o valor da parcela, pra descobrir o número da NL gerada.

executar_nl() recebe `ce` e `valor_padronizado` como parâmetros
separados, porque são esses dois valores que essa etapa usa de verdade
(o `dados` completo do SEI(1) fica disponível caso seja preciso mais
alguma coisa depois, mas hoje não é usado). Isso permite testar essa
etapa sozinha sem precisar rodar SEI(1) nem CE de novo: o bloco
"if __name__ == '__main__':" abaixo já carrega o último CE e valor
salvos no arquivo de sessão (sessao_atual.json, ver utils.py) e oferece
como padrão — aperte Enter pra reaproveitar, ou digite um valor novo pra
trocar.
"""
from datetime import date

from utils import URL_SIGEF_NL, obter_ou_criar_aba, salvar_sessao


def executar_nl(context, ce: str, valor_padronizado: str, dados: dict = None) -> str | None:
    """
    Executa a Etapa NL (Liquidar Despesa Certificada), localizando o
    lançamento pelo número `ce` e gerando a NL para o `valor_padronizado`
    informado.

    Retorna o número da NL gerada (só o número, sem o prefixo "2026NL"),
    ou None se não encontrar, para ser repassado à Etapa PP, que precisa
    dele.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_NL,
    )
    aba_sigef.goto(URL_SIGEF_NL)
    aba_sigef.wait_for_load_state("networkidle")

    data_atual = date.today().strftime("%d%m%Y")

    # ========= SUA AUTOMAÇÃO =========
    aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")
    aba_sigef.locator("#txtDespesaCertificadaNumero_SIGEFPesquisa").fill(ce)
    aba_sigef.locator("#btnPesquisar").click()

    aba_sigef.locator("#txtDataVencimento_SIGEFData").fill(data_atual)
    aba_sigef.locator("#btnAdicionar").click()

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#txtNotaEmpenhoNumeroId_BtnPesquisa").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    # TODO: "1963" está fixo - o número do empenho precisa vir de algum
    # lugar (planilha? dados do SEI?) em vez de hardcoded.
    nova_pagina.locator("#txtNotaEmpenhoNumero").fill("1963")
    nova_pagina.locator("#btnConfirmar").click()
    nova_pagina.locator("td.GridLink[onclick*='SelecionarItem']").first.click()

    # Fecha a aba de busca da nota de empenho -- ela já cumpriu seu papel
    # (selecionar o item) e, se não for fechada, fica acumulando abas no
    # Chrome a cada execução.
    try:
        nova_pagina.close()
    except Exception:
        pass

    aba_sigef.bring_to_front()

    aba_sigef.locator("#txtValorBrutoId").press_sequentially(valor_padronizado)
    aba_sigef.locator("#btnRetencoesId").click()
    aba_sigef.locator("#menun4").click()

    aba_sigef.locator("#btnConfirmar").click()

    linhas = aba_sigef.locator("tr.GridLinhaPar, tr.GridLinhaImpar")
    total = linhas.count()

    nl = None
    valor_encontrado = None

    for i in range(total):
        linha = linhas.nth(i)
        # ":scope > td" pega só os <td> que são filhos diretos da <tr> --
        # a coluna "Unidade Gestora / Gestão" tem uma tabela aninhada
        # dentro da célula, com seus próprios <td>. Um "td" comum (sem
        # :scope >) pega esses <td> aninhados também, o que desloca a
        # contagem e faz o .nth(N) apontar pra célula errada.
        celulas = linha.locator(":scope > td")
        valor_liquido = celulas.nth(7).text_content().strip()
        valor_liquido_padronizado = valor_liquido.replace(".", "").replace(",", "")

        if valor_liquido_padronizado == valor_padronizado:
            nl_bruto = celulas.nth(5).text_content().strip()
            # A célula vem como "2026NL066210" -- guardamos só o número
            # depois do "NL" (ex: "066210").
            nl = nl_bruto.split("NL")[-1] if "NL" in nl_bruto else nl_bruto
            valor_encontrado = valor_liquido
            break  # achou a linha certa, para de procurar

    if nl:
        print(f"Valores Gerados: {nl}, {valor_encontrado}")
        salvar_sessao(nl=nl, valor_padronizado=valor_padronizado)
    else:
        print(f"Não foi possível gerar a NL.\nPlanilha: {valor_padronizado}")

    aba_sigef.locator("img[src*='Limpar.GIF']").click()

    return nl


if __name__ == "__main__":
    # Teste isolado da Etapa NL: conecta no Chrome já aberto e pede só o
    # CE e o valor diretamente pelo teclado — não precisa rodar SEI(1)
    # nem CE de novo. Útil quando você já tem esses dois valores de um
    # teste anterior e só quer testar essa etapa.
    from utils import carregar_sessao, conectar_chrome, perguntar_ou_reusar

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        ce = perguntar_ou_reusar("Digite o CE (gerado na Etapa CE)", "ce", sessao)
        valor_padronizado = perguntar_ou_reusar(
            "Digite o valor padronizado (ex: 787875 para 7.878,75)",
            "valor_padronizado",
            sessao,
        )
        nl = executar_nl(context, ce, valor_padronizado)
        print(f"OK: NL processado para o CE '{ce}'. Número da NL: {nl}")
    finally:
        playwright.stop()
