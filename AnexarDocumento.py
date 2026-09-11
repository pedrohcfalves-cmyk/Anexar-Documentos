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

URL_SIGEF = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINManterDespesaCertificada.aspx?CdTransacao=121"

URL_SIGEF_NL = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINLiquidarDespesaCertificada.aspx?CdTransacao=160"

URL_SIGEF_PP = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINPreparacaoPagamentoDespesaEmpenhada.aspx?CdTransacao=250"

URL_SIGEF_OB  = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINManterOrdemBancaria.aspx?CdTransacao=214"

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
        url_navegacao=URL_SIGEF,
        trecho_pagina="FINListarOrdemBancaria",
    )

    # ===== Aba 2: SEI =====
    # Obs: a URL do SEI muda a cada processo/sessão (infra_hash, #ID-...),
    # por isso a verificação de "já está na aba certa" usa só o domínio.
    aba_sei = obter_ou_criar_aba(
        context,
        dominio="sei.sistemas.ro.gov.br",
        url_navegacao=URL_SEI,
    )

    # ========= SUA AUTOMAÇÃO ALTERNANDO ENTRE AS ABAS =========

    # 1 Parte do SEI, (Definindo variaveis)

    input("Sua conta ja foi Aberta? (S/N) ").strip().upper()

    #processo = "0029.002128/2026-37" # Sera coletado da planilha
    aba_sei.bring_to_front()

    processo = input("Digite o processo do SEI: ").strip()
    aba_sei.locator('img.infraImg[title="Controle de Processos"]:visible').click()
    aba_sei.locator("#txtPesquisaRapida").fill(processo)
    aba_sei.locator('img.infraImg[title="Pesquisa Rápida"]:visible').click()

    aba_sei.frame_locator("#ifrArvore").locator('img[title="Abrir todas as Pastas"]:visible').click()

    def confirmar(mensagem: str = "Você tem certeza? (S/N): ") -> bool:
        """Pergunta S/N e só aceita essas duas opções."""
        while True:
            resposta = input(mensagem).strip().upper()
            if resposta in ("S", "N"):
                return resposta == "S"
            print("⚠️  Digite apenas S ou N.\n")


    while True:
        print("=" * 50)
        print("  Coloque as informações a baixo para preencher o sistema do sigef")
        print("=" * 50)

        data_atual = date.today().strftime("%d%m%Y")
        valor = input("Digite o valor Total da Parcela: ").strip()
        cnpj_cpf = input("Digite o CNPJ/CPF: ").strip()
        municipio = input("Digite o nome do município: ").strip()
        escola = input("Digite o nome da escola: ").strip()
        conta_pp = input("Digite a conta PP: ").strip()
        conta_ob = input("Digite a conta OB: ").strip()
        parcela = input("Digite a parcela: ").strip()
        mes_referencia = input("Digite o mês de referência (1-12): ").strip()
        programa = input("Digite o programa: ").strip()

        print("-" * 50)
        print(f"Valor Total da Parcela : {valor}")
        print(f"CNPJ/CPF               : {cnpj_cpf}")
        print(f"Município               : {municipio}")
        print(f"Escola                  : {escola}")
        print(f"Conta PP                : {conta_pp}")
        print(f"Conta OB                : {conta_ob}")
        print(f"Parcela                 : {parcela}")
        print(f"Mês de Referência       : {mes_referencia}")
        print(f"Programa                : {programa}")
        print("-" * 50)

        if confirmar("Você tem certeza? (S/N): "):
            break  # sai do loop, dados confirmados
        print("\n🔄 Ok, vamos preencher novamente.\n")

    valor_padronizado = valor.replace(".", "").replace(",", "")  # 7.878,75 -> 787875

    #parte do sigef

    #CE 

    aba_sigef.bring_to_front()

    aba_sigef.locator("#txtCdGestao_SIGEFPesquisa").fill("00001")
    aba_sigef.locator("#cmbCdTipoDocumento").select_option("99")
    aba_sigef.locator("#txtNuDocumento").fill(f"{programa}/{date.today().year}")
    aba_sigef.locator("#chkFlAtestadoRecSouResp").check()
    aba_sigef.locator("#txtDtAceite_SIGEFData").fill(data_atual)
    aba_sigef.locator("#txtDtApresentacao_SIGEFData").fill(data_atual)
    aba_sigef.locator("#txtDtEmissao_SIGEFData").fill(data_atual)
    aba_sigef.locator("#cboMesComp").select_option(mes_referencia)
    aba_sigef.locator("#txtDeObservacao").fill(f"Regularização da {parcela} do {programa} Em favor de {escola}, localizado no município de {municipio}, referente ao processo {processo}.")  # {programa} Deve ser substituido pelo nome da planilha, para se adequar ao programa

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#txtNmCredor_BtnPesquisa").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    nova_pagina.locator("#txtNuCnpj").fill(cnpj_cpf)
    nova_pagina.locator("#btnConfirmar").click()
    nova_pagina.locator("td.GridLink[onclick*='SelecionarItem']").first.click()

    aba_sigef.bring_to_front()

    aba_sigef.locator("#txtVlDocumento").press_sequentially(valor_padronizado)
    aba_sigef.locator("#btnManutencao_BtnIncluir").click()
    #018682
    ce = aba_sigef.locator("#txtNuSeq").input_value()
    print(ce)

    aba_sigef.locator("#txtNuSeq").fill("")

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
