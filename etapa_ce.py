"""
Etapa CE: preenche a Despesa Certificada no SIGEF e obtém o número CE
gerado. Cobre o trecho desde o preenchimento do formulário até a
inclusão do lançamento.

Os dados usados aqui (valor, CNPJ/CPF, município, escola, contas, etc.)
são coletados na Etapa SEI (1) — ver coletar_dados_sigef() em
etapa_sei1.py — e chegam prontos no parâmetro `dados` de executar_ce().

O download/conversão do relatório da CE em JPG foi movido pra
etapa_baixar.py (etapa futura, ainda não integrada ao fluxo principal).
"""
from datetime import date

from utils import URL_SIGEF, carregar_sessao, obter_ou_criar_aba, salvar_sessao


def incluir_documento_sigef(aba_sigef, valor_padronizado: str) -> str:
    """
    Preenche o valor do documento no SIGEF, inclui o lançamento e retorna
    o número de sequência gerado (CE - Certificado de Despesa).
    """
    aba_sigef.bring_to_front()

    aba_sigef.locator("#txtVlDocumento").press_sequentially(valor_padronizado)
    aba_sigef.locator("#btnManutencao_BtnIncluir").click()

    ce = aba_sigef.locator("#txtNuSeq").input_value()

    aba_sigef.locator("#txtNuSeq").fill("")

    return ce


def preencher_despesa_certificada(aba_sigef, context, dados: dict, processo: str) -> str:
    """
    Preenche o formulário de Despesa Certificada no SIGEF (gestão, tipo de
    documento, datas, observação, credor) e inclui o lançamento.

    Retorna o número CE gerado por incluir_documento_sigef.
    """
    data_atual = date.today().strftime("%d%m%Y")
    programa = dados["programa"]

    aba_sigef.bring_to_front()

    aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")
    aba_sigef.locator("#cmbCdTipoDocumento").select_option("99")
    aba_sigef.locator("#txtNuDocumento").fill(f"{programa}/{date.today().year}")
    aba_sigef.locator("#chkFlAtestadoRecSouResp").check()
    aba_sigef.locator("#txtDtAceite_SIGEFData").fill(data_atual)
    aba_sigef.locator("#txtDtApresentacao_SIGEFData").fill(data_atual)
    aba_sigef.locator("#txtDtEmissao_SIGEFData").fill(data_atual)
    aba_sigef.locator("#cboMesComp").select_option(dados["mes_referencia"])
    aba_sigef.locator("#txtDeObservacao").fill(
        f"Regularização da {dados['parcela']} do {programa} Em favor de "
        f"{dados['escola']}, localizado no município de {dados['municipio']}, "
        f"referente ao processo {processo}."
    )

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#txtNmCredor_BtnPesquisa").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    nova_pagina.locator("#txtNuCnpj").fill(dados["cnpj_cpf"])
    nova_pagina.locator("#btnConfirmar").click()
    nova_pagina.locator("td.GridLink[onclick*='SelecionarItem']").first.click()

    # Fecha a aba de busca do credor -- já cumpriu seu papel.
    try:
        nova_pagina.close()
    except Exception:
        pass

    return incluir_documento_sigef(aba_sigef, dados["valor_padronizado"])


def executar_ce(context, processo: str, dados: dict) -> str:
    """
    Executa a Etapa CE completa: obtém/cria a aba do SIGEF, preenche a
    Despesa Certificada com os dados recebidos (já coletados na Etapa SEI
    (1), via coletar_dados_sigef()) e obtém o CE gerado.

    Retorna o número CE gerado.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigef.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF,
        trecho_pagina="FINManterDespesaCertificada",
    )

    ce = preencher_despesa_certificada(aba_sigef, context, dados, processo)
    print(f"CE gerado: {ce}")
    salvar_sessao(ce=ce)

    return ce


if __name__ == "__main__":
    # Teste isolado da Etapa CE: conecta no Chrome já aberto e só executa
    # essa etapa, sem precisar rodar a Etapa SEI(1) de verdade. Os dados
    # (que normalmente vêm do SEI(1)) são coletados aqui na hora, chamando
    # a mesma função que o SEI(1) usa.
    from etapa_sei1 import coletar_dados_sigef
    from utils import carregar_sessao, conectar_chrome, perguntar_ou_reusar

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        processo = perguntar_ou_reusar(
            "Digite o processo do SEI (para nomear a pasta)", "processo", sessao
        )
        dados = coletar_dados_sigef()
        ce = executar_ce(context, processo, dados)
        print(f"OK: CE '{ce}' processado.")
    finally:
        playwright.stop()
