"""
Etapa Baixar OB: baixa e converte o relatório da Ordem Bancária (OB) em
JPG -- salvando na MESMA pasta do processo onde o relatório da CE é
salvo (ver executar_baixar() em etapa_baixar.py: pasta_base/processo).

Segue EXATAMENTE o mesmo modelo de código da Etapa Baixar (CE): localiza
o número na tela de listagem, abre o detalhe, clica em "Gerar
Relatório", escolhe o formato PDF, baixa, converte pra JPG e apaga o PDF
temporário.

⚠️ AINDA NÃO CONFIRMADO AO VIVO -- diferente da CE (cuja tela de listar
já foi testada), aqui dois pontos são um CHUTE seguindo o mesmo padrão
usado nas outras telas, e precisam ser confirmados testando de verdade
no SIGEF (mesmo processo já usado pra descobrir a Etapa Anexar
Documento: rodar, pegar o erro/HTML real que aparecer e eu ajusto):

    1) URL_SIGEF_LISTAR_OB (em utils.py) -- ainda está vazia. Preencher
       com a URL real da tela "Listar Ordem Bancária" do SIGEF.
    2) O id do campo de busca pela OB abaixo (#txtNuOB) -- um chute
       seguindo o padrão de #txtNuDespesa (CE) / #txtPrepPagSeq (PP).

Etapa ainda não integrada ao fluxo principal (main.py) -- roda isolada,
do mesmo jeito que etapa_baixar.py (CE) também ainda roda isolada.

executar_baixar_ob() recebe `ob` e `processo` direto, no mesmo esquema
da CE/NL/PP/OB, pra dar pra testar essa etapa sozinha sem rodar as
anteriores de novo -- o bloco "__main__" abaixo carrega os últimos
valores salvos na sessão como padrão.
"""
import os

from utils import (
    PASTA_BASE,
    URL_SIGEF_LISTAR_OB,
    carregar_sessao,
    nome_pasta_valido,
    obter_ou_criar_aba,
    pdf_para_jpg,
    perguntar_ou_reusar,
)


def executar_baixar_ob(context, ob: str, processo: str, pasta_base: str = PASTA_BASE) -> list[str]:
    """
    Localiza a OB `ob` na tela de Listar Ordem Bancária, abre o detalhe,
    gera e baixa o relatório em PDF, converte para JPG e salva/renomeia o
    arquivo final na MESMA pasta do processo onde o relatório da CE é
    salvo (mesmo pasta_base/processo de executar_baixar(), em
    etapa_baixar.py).

    Retorna a lista de caminhos dos JPGs gerados.
    """
    if not URL_SIGEF_LISTAR_OB:
        raise Exception(
            "URL_SIGEF_LISTAR_OB ainda não foi preenchida em utils.py -- "
            "veja o aviso no topo de etapa_baixar_ob.py pra saber o que falta."
        )

    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_LISTAR_OB,
    )
    aba_sigef.goto(URL_SIGEF_LISTAR_OB)
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")

    # TODO: confirmar o id real do campo de busca pela OB -- "#txtNuOB" é
    # um chute seguindo o padrão de #txtNuDespesa (CE, em etapa_baixar.py)
    # e #txtPrepPagSeq (PP, em etapa_anexar.py). Ajustar aqui com o id
    # real assim que descobrir (testando ao vivo e olhando o HTML/erro).
    aba_sigef.locator("#txtNuOB").fill(ob)
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

    # MESMA pasta onde o relatório da CE é salvo -- ver executar_baixar()
    # em etapa_baixar.py.
    pasta_destino = os.path.join(pasta_base, nome_pasta_valido(processo))
    os.makedirs(pasta_destino, exist_ok=True)

    caminho_pdf_temp = os.path.join(pasta_destino, "temp_ob.pdf")
    download.save_as(caminho_pdf_temp)

    arquivos_jpg = pdf_para_jpg(caminho_pdf_temp, pasta_destino, nome_arquivo="Ordem Bancária")
    os.remove(caminho_pdf_temp)

    print("JPG da OB pronto em:", arquivos_jpg)

    return arquivos_jpg


if __name__ == "__main__":
    # Teste isolado da Etapa Baixar OB: conecta no Chrome já aberto e
    # pede só a OB e o processo diretamente pelo teclado -- não precisa
    # rodar as etapas anteriores de novo.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        ob = perguntar_ou_reusar("Digite a OB (gerada na Etapa OB)", "ob", sessao)
        processo = perguntar_ou_reusar(
            "Digite o processo do SEI (para nomear a pasta)", "processo", sessao
        )
        arquivos_jpg = executar_baixar_ob(context, ob, processo)
        print(f"OK: relatório da OB '{ob}' baixado. Arquivos: {arquivos_jpg}")
    finally:
        playwright.stop()
