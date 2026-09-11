"""
Etapa CE: preenche a Despesa Certificada no SIGEF, obtém o número CE
gerado e baixa/converte o relatório em JPG, salvando-o com o nome final
na pasta do processo. Cobre todo o trecho desde o preenchimento do
formulário até salvar e renomear o arquivo.

Os dados usados aqui (valor, CNPJ/CPF, município, escola, contas, etc.)
são coletados na Etapa SEI (1) — ver coletar_dados_sigef() em
etapa_sei1.py — e chegam prontos no parâmetro `dados` de executar_ce().
"""
import os
from datetime import date

from utils import (
    URL_SIGEF,
    URL_SIGEF_LISTAR_DESPESA_CERTIFICADA,
    PASTA_BASE,
    carregar_sessao,
    nome_pasta_valido,
    obter_ou_criar_aba,
    pdf_para_jpg,
    salvar_sessao,
)


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

    return incluir_documento_sigef(aba_sigef, dados["valor_padronizado"])


def baixar_e_converter_relatorio(
    aba_sigef, context, ce: str, processo: str, pasta_base: str = PASTA_BASE
) -> list[str]:
    """
    Na tela de Listar Despesa Certificada, localiza o CE, abre o detalhe,
    gera e baixa o relatório em PDF, converte para JPG e salva/renomeia o
    arquivo final na pasta do processo. Remove o PDF temporário no final.

    Retorna a lista de caminhos dos JPGs gerados.
    """
    aba_sigef.goto(URL_SIGEF_LISTAR_DESPESA_CERTIFICADA)
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")
    aba_sigef.locator("#txtNuDespesa").fill(ce)
    aba_sigef.locator("#btnConfirmar").click()

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("td.GridLink[onclick*='AbrirPaginaDetalhe']").first.click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    with context.expect_page() as nova_pagina1_info:
        nova_pagina.locator("a[title='Gerar Relatório']").click()

    nova_pagina1 = nova_pagina1_info.value
    nova_pagina1.wait_for_load_state("networkidle")

    with context.expect_event("download") as download_info:
        nova_pagina1.locator('img[alt="Imprime Arquivo Formato PostScript (.pdf)"]').click()

    download = download_info.value

    pasta_destino = os.path.join(pasta_base, nome_pasta_valido(processo))
    os.makedirs(pasta_destino, exist_ok=True)

    caminho_pdf_temp = os.path.join(pasta_destino, "temp.pdf")
    download.save_as(caminho_pdf_temp)

    arquivos_jpg = pdf_para_jpg(caminho_pdf_temp, pasta_destino, nome_arquivo="Despesa Certificada")
    os.remove(caminho_pdf_temp)

    return arquivos_jpg


def executar_ce(context, processo: str, dados: dict, pasta_base: str = PASTA_BASE) -> tuple[str, list[str]]:
    """
    Executa a Etapa CE completa: obtém/cria a aba do SIGEF, preenche a
    Despesa Certificada com os dados recebidos (já coletados na Etapa SEI
    (1), via coletar_dados_sigef()), obtém o CE e baixa/converte o
    relatório em JPG (até salvar e renomear o arquivo final).

    Retorna o número CE e a lista de arquivos JPG gerados.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF,
        trecho_pagina="FINListarOrdemBancaria",
    )

    ce = preencher_despesa_certificada(aba_sigef, context, dados, processo)
    print(ce)
    salvar_sessao(ce=ce)

    arquivos_jpg = baixar_e_converter_relatorio(aba_sigef, context, ce, processo, pasta_base)
    print("JPG pronto em:", arquivos_jpg)

    return ce, arquivos_jpg


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
        ce, arquivos_jpg = executar_ce(context, processo, dados)
        print(f"OK: CE '{ce}' processado, arquivos: {arquivos_jpg}")
    finally:
        playwright.stop()
