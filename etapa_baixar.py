"""
Etapa Baixar: baixa e converte o relatório da Despesa Certificada (CE) em JPG.

Na tela de Listar Despesa Certificada, localiza o CE, abre o detalhe, gera e
baixa o relatório em PDF, converte para JPG e salva/renomeia o arquivo final
na pasta do processo. Remove o PDF temporário no final.

executar_baixar() recebe `ce` e `processo` direto, no mesmo esquema da
NL/PP/OB, pra dar pra testar essa etapa sozinha sem rodar as anteriores de
novo -- o bloco "__main__" abaixo carrega os últimos valores salvos na
sessão como padrão.

Etapa ainda não integrada ao fluxo principal (main.py) -- roda isolada.
"""
import os

from utils import (
    URL_SIGEF_LISTAR_DESPESA_CERTIFICADA,
    PASTA_BASE,
    carregar_sessao,
    nome_pasta_valido,
    obter_ou_criar_aba,
    pdf_para_jpg,
    perguntar_ou_reusar,
)


def executar_baixar(context, ce: str, processo: str, pasta_base: str = PASTA_BASE) -> list[str]:
    """
    Localiza o CE na tela de Listar Despesa Certificada, abre o detalhe,
    gera e baixa o relatório em PDF, converte para JPG e salva/renomeia o
    arquivo final na pasta do processo.

    Retorna a lista de caminhos dos JPGs gerados.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_LISTAR_DESPESA_CERTIFICADA,
    )
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

    # Fecha as abas de detalhe e de relatório -- já cumpriram seu papel.
    for pagina_temp in (nova_pagina1, nova_pagina):
        try:
            pagina_temp.close()
        except Exception:
            pass

    pasta_destino = os.path.join(pasta_base, nome_pasta_valido(processo))
    os.makedirs(pasta_destino, exist_ok=True)

    caminho_pdf_temp = os.path.join(pasta_destino, "temp.pdf")
    download.save_as(caminho_pdf_temp)

    arquivos_jpg = pdf_para_jpg(caminho_pdf_temp, pasta_destino, nome_arquivo="Despesa Certificada")
    os.remove(caminho_pdf_temp)

    print("JPG pronto em:", arquivos_jpg)

    return arquivos_jpg


if __name__ == "__main__":
    # Teste isolado da Etapa Baixar: conecta no Chrome já aberto e pede só
    # o CE e o processo diretamente pelo teclado -- não precisa rodar as
    # etapas anteriores de novo.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        ce = perguntar_ou_reusar("Digite o CE (gerado na Etapa CE)", "ce", sessao)
        processo = perguntar_ou_reusar(
            "Digite o processo do SEI (para nomear a pasta)", "processo", sessao
        )
        arquivos_jpg = executar_baixar(context, ce, processo)
        print(f"OK: relatório do CE '{ce}' baixado. Arquivos: {arquivos_jpg}")
    finally:
        playwright.stop()
