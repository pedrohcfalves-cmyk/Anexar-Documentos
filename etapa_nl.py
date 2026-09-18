"""
Etapa NL: Liquidar Despesa Certificada no SIGEF.

A CE é gerada uma única vez (com o Valor Total) e pode ser liquidada em
várias NLs -- uma por lançamento (Valor + Nota de Empenho). Por isso
executar_nl_lote() pesquisa a CE uma única vez e repete só o ciclo de
inclusão (data de vencimento, nota de empenho, valor bruto, retenções,
confirmar) para cada lançamento, sem recarregar a página entre eles --
recarregar seria lento e desnecessário, já que é sempre a mesma CE.

executar_nl_lote() recebe `ce` e a lista de lançamentos direto, pra dar
pra testar essa etapa sozinha sem rodar SEI(1)/CE de novo -- o bloco
"__main__" abaixo carrega os últimos valores salvos na sessão como
padrão e testa com um lançamento só.
"""
from datetime import date

from utils import URL_SIGEF_NL, normalizar, obter_ou_criar_aba, salvar_sessao


def _incluir_nl(aba_sigef, context, valor_padronizado: str, nota_empenho: str) -> str | None:
    """
    Repete o ciclo de inclusão de uma NL (data de vencimento, nota de
    empenho, valor bruto, retenções, confirmar) numa CE já pesquisada na
    página, e varre a grade de resultados procurando a linha cujo valor
    líquido bate com `valor_padronizado`, pra descobrir o número gerado.

    Retorna o número da NL (só o número, sem o prefixo "2026NL"), ou
    None se não encontrar a linha correspondente na grade.
    """
    data_atual = date.today().strftime("%d%m%Y")

    aba_sigef.locator("#txtDataVencimento_SIGEFData").fill(data_atual)
    aba_sigef.locator("#btnAdicionar").click()

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#txtNotaEmpenhoNumeroId_BtnPesquisa").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    nova_pagina.locator("#txtNotaEmpenhoNumero").fill(nota_empenho)
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

    # A página troca/recarrega os campos depois de vincular a nota de
    # empenho, e às vezes esse recarregamento demora mais que os 2s de
    # espera e apaga o valor digitado. Por isso, além de esperar,
    # confere se o valor realmente ficou no campo -- se a página tiver
    # apagado, digita de novo (até 3 tentativas).
    #
    # Dois cuidados importantes aqui, porque é campo de valor de
    # pagamento -- um erro nisso é grave:
    #   1) O campo é LIMPO antes de cada tentativa (seleciona tudo e
    #      apaga). press_sequentially() digita em cima do que já
    #      estiver lá -- sem limpar antes, cada nova tentativa
    #      CONCATENA com o valor anterior em vez de substituir.
    #   2) A comparação usa normalizar() (compara o VALOR numérico),
    #      não o texto cru -- o campo devolve o valor já formatado
    #      pelo SIGEF (ex: "3.258,50"), que nunca seria igual, char a
    #      char, ao valor_padronizado só-dígitos (ex: "325850").
    campo_valor = aba_sigef.locator("#txtValorBrutoId")
    valor_esperado = normalizar(valor_padronizado)
    for tentativa in range(1, 4):
        aba_sigef.wait_for_timeout(2000)
        campo_valor.click()
        campo_valor.press("Control+A")
        campo_valor.press("Backspace")
        campo_valor.press_sequentially(valor_padronizado, delay=20)
        aba_sigef.wait_for_timeout(300)

        valor_atual = campo_valor.input_value().strip()
        try:
            confere = bool(valor_atual) and abs(normalizar(valor_atual) - valor_esperado) < 0.001
        except ValueError:
            confere = False

        if confere:
            break
        print(f"⚠️  Valor Bruto ficou incorreto (campo tem '{valor_atual}'), tentando de novo ({tentativa}/3)...")
    else:
        print("⚠️  Não foi possível confirmar o preenchimento do Valor Bruto -- PARE e confira manualmente antes de confirmar.")

    aba_sigef.locator("#btnRetencoesId").click()
    aba_sigef.locator("#menun4").click()

    aba_sigef.locator("#btnConfirmar").click()

    linhas = aba_sigef.locator("tr.GridLinhaPar, tr.GridLinhaImpar")
    total = linhas.count()

    for i in range(total):
        linha = linhas.nth(i)
        # :scope > td = só os <td> filhos diretos (a coluna "Unidade
        # Gestora" tem uma tabela aninhada com <td> próprios, que um "td"
        # comum pegaria também, desalinhando o .nth(N)).
        celulas = linha.locator(":scope > td")
        valor_liquido = celulas.nth(7).text_content().strip()
        valor_liquido_padronizado = valor_liquido.replace(".", "").replace(",", "")

        if valor_liquido_padronizado == valor_padronizado:
            nl_bruto = celulas.nth(5).text_content().strip()
            # A célula vem como "2026NL066210" -- guardamos só o número
            # depois do "NL" (ex: "066210").
            return nl_bruto.split("NL")[-1] if "NL" in nl_bruto else nl_bruto

    return None


def executar_nl_lote(context, ce: str, lancamentos: list[dict], dados: dict = None) -> list[dict]:
    """
    Gera a NL de cada lançamento da lista, todos vinculados à mesma CE
    `ce` (pesquisada uma única vez).

    Retorna a MESMA lista `lancamentos`, com a chave "nl" adicionada em
    cada item (o número gerado, ou None se não foi possível gerar
    aquela NL).
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigef.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_NL,
    )
    aba_sigef.goto(URL_SIGEF_NL)
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")
    aba_sigef.locator("#txtDespesaCertificadaNumero_SIGEFPesquisa").fill(ce)
    aba_sigef.locator("#btnPesquisar").click()

    gerou_alguma_nova = False
    for item in lancamentos:
        if item.get("nl"):
            # Já tem NL de uma execução anterior (mesma CE) -- pula pra
            # não gerar duplicado.
            print(f"⏭️  Lançamento do valor {item['valor']} já tem NL ({item['nl']}) -- pulando.")
            continue

        item["nl"] = _incluir_nl(aba_sigef, context, item["valor_padronizado"], item["nota_de_empenho"])
        if item["nl"]:
            print(f"NL gerada para o valor {item['valor']}: {item['nl']}")
            gerou_alguma_nova = True
        else:
            print(f"⚠️  Não foi possível gerar a NL para o valor {item['valor']}.")
        salvar_sessao(lancamentos=lancamentos)

    # Depois de colocar todas as NLs na grade (dtgDocumentos), falta
    # confirmar a operação uma última vez pra fechar o lote inteiro --
    # só com esse clique final o fluxo da NL fica completo de verdade.
    # Só clica se algo NOVO foi incluído na grade nesta execução -- se
    # todo mundo já tinha NL de antes (tudo pulado), não tem nada na
    # grade pra confirmar.
    if gerou_alguma_nova:
        aba_sigef.locator("#btnConfirmar").click()
        aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.locator("img[src*='Limpar.GIF']").click()

    return lancamentos


if __name__ == "__main__":
    # Teste isolado da Etapa NL: conecta no Chrome já aberto e pede o CE
    # e um lançamento de teste (valor + nota de empenho) diretamente
    # pelo teclado — não precisa rodar SEI(1) nem CE de novo.
    from utils import carregar_sessao, conectar_chrome, perguntar_ou_reusar

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        ce = perguntar_ou_reusar("Digite o CE (gerado na Etapa CE)", "ce", sessao)
        valor_padronizado = perguntar_ou_reusar(
            "Digite o valor padronizado de um lançamento de teste (ex: 787875)",
            "valor_padronizado",
            sessao,
        )
        nota_empenho = perguntar_ou_reusar(
            "Digite a nota de empenho desse lançamento", "nota_de_empenho", sessao
        )
        item_teste = {
            "valor": valor_padronizado,
            "valor_padronizado": valor_padronizado,
            "nota_de_empenho": nota_empenho,
        }
        resultado = executar_nl_lote(context, ce, [item_teste])
        print(f"OK: NL processada para o CE '{ce}'. Número da NL: {resultado[0]['nl']}")
    finally:
        playwright.stop()
