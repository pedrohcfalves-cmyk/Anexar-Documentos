from pprint import pp
import re
import os
import pymupdf  
from datetime import date
from textwrap import fill

from playwright.sync_api import Page, sync_playwright

def nome_pasta_valido(nome: str) -> str:
    """Remove caracteres que o Windows não aceita em nome de pasta/arquivo."""
    for caractere in '<>:"/\\|?*':
        nome = nome.replace(caractere, "-")
    return nome.strip()


def pdf_para_jpg(caminho_pdf: str, pasta_destino: str, nome_arquivo: str) -> list[str]:
    """Converte cada página do PDF em um JPG e salva na pasta destino."""
    os.makedirs(pasta_destino, exist_ok=True)
    doc = pymupdf.open(caminho_pdf)  # <- só essa linha mudou

    caminhos_gerados = []
    for i, pagina in enumerate(doc, start=1):
        pix = pagina.get_pixmap(dpi=200)
        sufixo = "" if len(doc) == 1 else f"_{i}"
        caminho_jpg = os.path.join(pasta_destino, f"{nome_arquivo}{sufixo}.jpg")
        pix.save(caminho_jpg)
        caminhos_gerados.append(caminho_jpg)

    doc.close()
    return caminhos_gerados

URL_SIGEF_listar_pp = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINListarPreparacaoPagamento.aspx?CdTransacao=177"

URL_SEI = (
    "https://sei.sistemas.ro.gov.br/sei/controlador.php?"
    "acao=procedimento_controlar&reset=1&infra_sistema=100000100"
    "&infra_unidade_atual=110001024&infra_hash=65b46b11bd14b0c74b5e2d346aefc10544275ad2dbf99c43cf3c119593ea4377"
    "#ID-79129738"
)


def obter_ou_criar_aba(context, dominio: str, url_navegacao: str, trecho_pagina: str = None) -> Page:
    """
    Procura, entre as abas já abertas no Chrome em debug, uma que pertença ao
    domínio informado. Se não encontrar, cria uma nova aba e navega até a URL.

    dominio        -> trecho da URL usado para identificar a aba (ex: "sigef.sefin.ro.gov.br")
    url_navegacao  -> URL para onde navegar caso a aba não exista ou esteja na página errada
    trecho_pagina  -> (opcional) trecho específico da URL que indica que já está na página certa
    """
    aba = None

    for pagina in context.pages:
        print("Aba encontrada:", pagina.url)
        if dominio.lower() in pagina.url.lower():
            aba = pagina
            print(f"Aba do domínio '{dominio}' encontrada.")
            break

    if aba is None:
        aba = context.new_page()
        aba.goto(url_navegacao)
    else:
        aba.bring_to_front()
        if trecho_pagina and trecho_pagina not in aba.url:
            aba.goto(url_navegacao)

    aba.wait_for_load_state("networkidle")
    return aba


with sync_playwright() as p:

    try:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    except Exception:
        raise Exception(
            "Chrome em modo de depuração não encontrado.\n"
            "Abra o Chrome com:\n"
            "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" "
            "--remote-debugging-port=9222"
        )

    context = browser.contexts[0]

    # ===== Aba 1: SIGEF =====
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigefhom.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_listar_pp,
        trecho_pagina="FINListarPreparacaoPagamento",
    )

    # ===== Aba 2: SEI =====
    # Obs: a URL do SEI muda a cada processo/sessão (infra_hash, #ID-...),
    # por isso a verificação de "já está na aba certa" usa só o domínio.
    aba_sei = obter_ou_criar_aba(
        context,
        dominio="sei.sistemas.ro.gov.br",
        url_navegacao=URL_SEI,
    )


    aba_sigef.bring_to_front()

    aba_sigef("#txtGestao_SIGEFPesquisa").fill("00001")
    aba_sigef("#txtPrepPagSeq").fill(pp)

    # ===== Continua para a tela de Listar Despesa Certificada =====
    
    aba_sigef.goto("http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINListarDespesaCertificada.aspx?CdTransacao=122")
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
    

    pasta_base = r"C:\Users\04789010201\Downloads\Anexar Documentos"
    pasta_destino = os.path.join(pasta_base, nome_pasta_valido(processo))
    os.makedirs(pasta_destino, exist_ok=True)

    caminho_pdf_temp = os.path.join(pasta_destino, "temp.pdf")
    download.save_as(caminho_pdf_temp)

    arquivos_jpg = pdf_para_jpg(caminho_pdf_temp, pasta_destino, nome_arquivo="Despesa Certificada")
    os.remove(caminho_pdf_temp)

    print("JPG pronto em:", arquivos_jpg)
