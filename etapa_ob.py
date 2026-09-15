"""
Etapa OB: Ordem Bancária no SIGEF.

Localiza a Preparação de Pagamento (PP) gerada na etapa anterior e
preenche a tela de Ordem Bancária pra gerar o número da OB.

executar_ob() recebe `pp`, `conta_ob` e `valor_padronizado` direto, no
mesmo esquema da NL/PP, pra dar pra testar essa etapa sozinha sem rodar
as anteriores de novo -- o bloco "__main__" abaixo carrega os últimos
valores salvos na sessão como padrão.
"""
import re
from datetime import date

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from utils import (
    URL_SIGEF_OB,
    carregar_sessao,
    normalizar,
    obter_ou_criar_aba,
    perguntar_ou_reusar,
    salvar_sessao,
)


def executar_ob(context, pp: str, conta_ob: str, valor_padronizado: str, dados: dict = None) -> str | None:
    """
    Executa a Etapa OB (Ordem Bancária), localizando o lançamento pelo
    número `pp` e o valor `valor_padronizado` (o mesmo valor_padronizado
    já coletado no SEI(1) -- ver coletar_dados_sigef() em etapa_sei1.py)
    e gerando a Ordem Bancária na conta `conta_ob`.

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

    # Parte fixa

    data_atual = date.today().strftime("%d%m%Y")

    aba_sigef.locator("input[name='txtDataReferencia$SIGEFData']").fill(data_atual)
    aba_sigef.locator("input[name='txtGestao$SIGEFPesquisa']").fill("00001")
    aba_sigef.locator("input[name='txtBancoOrigem']").fill("001")
    aba_sigef.locator("input[name='txtAgenciaOrigem']").fill("2757X")
    aba_sigef.locator("input[name='txtContaOrigem']").fill(conta_ob)
    aba_sigef.locator("#cboTipoOB").select_option("3")
    aba_sigef.locator("#cboTipoPagamento").select_option("2")

    # ============================================================
    # Iniciar LOOP (A fazer)(fazer até o fim da planilha)
    # ============================================================

    aba_sigef.locator("#txtDeObservacao").fill(
        "Regularização do valor pago na data de 01/07/2026 na conta do PROAFI"
    )

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#btnAdicionar").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    nova_pagina.locator("#txtUnidadeGestora").fill("160001")
    nova_pagina.locator("#txtGestao_SIGEFPesquisa").fill("00001")
    nova_pagina.locator("#txtIdUso").fill("1")
    nova_pagina.locator("#txtFonte_SIGEFPesquisa").fill("869000000")
    nova_pagina.locator("#btnPesquisar").click()

    # ============================================================
    # SISTEMA PARA PREVENÇÃO DE ERRO DE OB
    # ============================================================

    # PP gerada na Etapa PP (já com prefixo, ex: "2026PP047704"), no
    # mesmo formato da coluna "pp" da grade abaixo.
    PP_ESPERADA = pp

    # Aguarda a tabela carregar
    nova_pagina.wait_for_selector("tr.GridLinhaPar, tr.GridLinhaImpar")

    # Lê a tabela toda em uma única chamada (NÃO renomeie pra "dados" --
    # esse nome já é o parâmetro com o dict do SEI(1)).
    registros_grid = nova_pagina.evaluate(
        """
        () => {
            const linhas = document.querySelectorAll(
                "tr.GridLinhaPar, tr.GridLinhaImpar"
            );

            return [...linhas].map((linha, indice) => {
                const td = [...linha.querySelectorAll("td")]
                    .map(x => x.innerText.trim());

                return {
                    indice: indice,

                    // COLUNAS REAIS DO SIGEF
                    pp: td[6],
                    valor: td[15],
                };
            });
        }
        """
    )

    print(f"Total de registros: {len(registros_grid)}")

    valor_esperado = normalizar(valor_padronizado)

    registro = None

    for item in registros_grid:
        try:
            valor_site = normalizar(item["valor"])
        except Exception:
            continue

        print(f"PP: {item['pp']} | Valor: {valor_site:.2f}")

        if item["pp"] == PP_ESPERADA and abs(valor_site - valor_esperado) < 0.01:
            registro = item
            break

    # CASO NÃO ENCONTRE
    if registro is None:
        raise Exception(
            f"""
    ================================================
    ERRO PP NÃO CORRESPONDE

    PP esperado:
    {PP_ESPERADA}

    Valor esperado:
    {valor_esperado:.2f}
    ================================================
    """
        )

    indice = registro["indice"]
    print(f"\nPP localizado na linha {indice}")

    checkbox = nova_pagina.locator(f"#chk{indice}")
    checkbox.wait_for(state="visible")

    if not checkbox.is_checked():
        checkbox.click()

    print(f"Checkbox chk{indice} marcada com sucesso.")

    nova_pagina.locator("#btnConfirmar").click()
    nova_pagina.wait_for_event("close")

    aba_sigef.bring_to_front()
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.locator("#SIGEFBotoesManutencao_BtnIncluir").click()

    # capturar a OB

    # O clique dispara um postback assíncrono -- conferir o elemento na
    # hora (sem esperar) pode achar que não tem nada lá ainda e devolver
    # None mesmo quando a OB FOI gerada no SIGEF (mesmo bug já visto na
    # Etapa PP). Espera a mensagem de sucesso aparecer antes de decidir.
    elemento_sucesso = aba_sigef.locator("td.SIGEFMensagemSucesso").first
    try:
        elemento_sucesso.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        print("Não foi possível gerar a OB.")
        return None

    ob = elemento_sucesso.inner_text().strip()
    print(f"OB capturada: {ob}")

    match = re.search(r"\d{4}OB\d+", ob)
    if not match:
        raise Exception("Número da OB não encontrado na mensagem de sucesso.")

    numero_ob = match.group(0)
    print(f"Número da OB: {numero_ob}")

    # finalização
    aba_sigef.locator("#txtNumeroOB").fill("")
    aba_sigef.locator("#chk0").check()
    aba_sigef.locator("#btnRemover").click()

    salvar_sessao(ob=numero_ob)

    return numero_ob


if __name__ == "__main__":
    # Teste isolado da Etapa OB: conecta no Chrome já aberto e pede só a
    # PP, a conta OB e o valor diretamente pelo teclado — não precisa
    # rodar as etapas anteriores de novo. Útil quando você já tem esses
    # valores de um teste anterior e só quer testar essa etapa.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        pp = perguntar_ou_reusar("Digite a PP (gerada na Etapa PP)", "pp", sessao)
        conta_ob = perguntar_ou_reusar("Digite a conta OB", "conta_ob", sessao)
        valor_padronizado = perguntar_ou_reusar(
            "Digite o valor padronizado (ex: 787875 para 7.878,75)",
            "valor_padronizado",
            sessao,
        )
        ob = executar_ob(context, pp, conta_ob, valor_padronizado)
        print(f"OK: OB processada para a PP '{pp}'. Número da OB: {ob}")
    finally:
        playwright.stop()
