"""
Funções e constantes utilitárias compartilhadas entre as etapas do fluxo
SEI/SIGEF (SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)).
"""
import json
import os

import pymupdf
from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

# ===== URLs dos sistemas =====

URL_SIGEF = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINManterDespesaCertificada.aspx?CdTransacao=121"

URL_SIGEF_NL = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINLiquidarDespesaCertificada.aspx?CdTransacao=160"

URL_SIGEF_PP = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINPreparacaoPagamentoDespesaEmpenhada.aspx?CdTransacao=250"

URL_SIGEF_OB = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINManterOrdemBancaria.aspx?CdTransacao=214"

URL_SIGEF_LISTAR_DESPESA_CERTIFICADA = "http://sigefhom.sefin.ro.gov.br/SIGEF2026/FIN/FINListarDespesaCertificada.aspx?CdTransacao=122"

URL_SEI = (
    "https://sei.sistemas.ro.gov.br/sei/controlador.php?"
    "acao=procedimento_controlar&reset=1&infra_sistema=100000100"
    "&infra_unidade_atual=110001024&infra_hash=65b46b11bd14b0c74b5e2d346aefc10544275ad2dbf99c43cf3c119593ea4377"
    "#ID-79129738"
)

PASTA_BASE = r"C:\Users\04789010201\Downloads\Anexar Documentos"

# Arquivo onde ficam guardados os últimos valores digitados (processo,
# dados do SEI, CE, etc.), pra não precisar redigitar tudo de novo toda
# vez que for testar uma etapa separada. Fica na mesma pasta do projeto.
CAMINHO_SESSAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessao_atual.json")


def conectar_chrome(porta: int = 9222, timeout_ms: int = 60000):
    """
    Conecta ao Chrome aberto em modo de depuração (CDP) e retorna o
    objeto playwright (para poder chamar .stop() no final), o browser e o
    primeiro contexto disponível.

    Lança Exception com instruções caso o Chrome não esteja aberto na
    porta de depuração. Por padrão desiste depois de 60s (em vez do
    padrão do Playwright, que pode levar minutos) pra não parecer que o
    script travou quando o Chrome simplesmente não está aberto.

    Existem dois motivos bem diferentes pra essa conexão falhar, e o
    tratamento abaixo distingue os dois:
      1) O Chrome nem está aberto na porta de depuração -> a conexão
         websocket nunca chega a abrir ("<ws connecting>" sem
         "<ws connected>" no log do erro).
      2) O Chrome está aberto e a conexão websocket abre normalmente
         ("<ws connected>" aparece no log), mas ele demora demais pra
         responder ao protocolo CDP. Nesse caso o Chrome ESTÁ em modo de
         depuração, só está demorando -- use o Chrome aberto pelo
         abrir_chrome_automacao.bat (perfil dedicado, sem as suas abas
         de navegação normal) em vez do seu Chrome do dia a dia, que
         costuma resolver isso.
    """
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{porta}", timeout=timeout_ms
        )
    except PlaywrightTimeoutError as erro:
        playwright.stop()
        if "<ws connected>" in str(erro):
            raise Exception(
                "O Chrome está em modo de depuração e a conexão abriu, "
                f"mas ele demorou mais de {timeout_ms // 1000}s pra "
                "responder ao protocolo do navegador.\n"
                "Feche esse Chrome e abra o dedicado pra automação com "
                "2 cliques em abrir_chrome_automacao.bat (na pasta do "
                "projeto), depois rode de novo."
            )
        raise Exception(
            "Chrome em modo de depuração não encontrado.\n"
            "Dê 2 cliques em abrir_chrome_automacao.bat (na pasta do "
            "projeto), ou abra manualmente com:\n"
            "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" "
            f"--remote-debugging-port={porta}"
        )
    except Exception:
        playwright.stop()
        raise Exception(
            "Chrome em modo de depuração não encontrado.\n"
            "Dê 2 cliques em abrir_chrome_automacao.bat (na pasta do "
            "projeto), ou abra manualmente com:\n"
            "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" "
            f"--remote-debugging-port={porta}"
        )
    return playwright, browser, browser.contexts[0]


def nome_pasta_valido(nome: str) -> str:
    """Remove caracteres que o Windows não aceita em nome de pasta/arquivo."""
    for caractere in '<>:"/\\|?*':
        nome = nome.replace(caractere, "-")
    return nome.strip()


def pdf_para_jpg(caminho_pdf: str, pasta_destino: str, nome_arquivo: str) -> list[str]:
    """Converte cada página do PDF em um JPG e salva na pasta destino."""
    os.makedirs(pasta_destino, exist_ok=True)
    doc = pymupdf.open(caminho_pdf)

    caminhos_gerados = []
    for i, pagina in enumerate(doc, start=1):
        pix = pagina.get_pixmap(dpi=200)
        sufixo = "" if len(doc) == 1 else f"_{i}"
        caminho_jpg = os.path.join(pasta_destino, f"{nome_arquivo}{sufixo}.jpg")
        pix.save(caminho_jpg)
        caminhos_gerados.append(caminho_jpg)

    doc.close()
    return caminhos_gerados


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


def confirmar(mensagem: str = "Você tem certeza? (S/N): ") -> bool:
    """Pergunta S/N e só aceita essas duas opções."""
    while True:
        resposta = input(mensagem).strip().upper()
        if resposta in ("S", "N"):
            return resposta == "S"
        print("⚠️  Digite apenas S ou N.\n")


def carregar_sessao() -> dict:
    """
    Lê o arquivo de sessão (CAMINHO_SESSAO) com os últimos valores usados
    (processo, dados do SEI, CE, etc.). Retorna um dict vazio se o
    arquivo ainda não existir ou estiver corrompido.
    """
    if not os.path.exists(CAMINHO_SESSAO):
        return {}
    try:
        with open(CAMINHO_SESSAO, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        return {}


def salvar_sessao(**novos_valores) -> None:
    """
    Atualiza o arquivo de sessão com os valores passados, mesclando com o
    que já estava salvo (não apaga o resto). Ex: salvar_sessao(ce=ce)
    guarda só o CE, mantendo processo/dados que já estavam salvos.
    """
    sessao = carregar_sessao()
    sessao.update(novos_valores)
    with open(CAMINHO_SESSAO, "w", encoding="utf-8") as arquivo:
        json.dump(sessao, arquivo, ensure_ascii=False, indent=2)


def normalizar(valor) -> float:
    """
    Converte qualquer um dos formatos de valor que aparecem no projeto
    pra um float em reais, pra dar pra comparar dois valores direto:

    79054      (valor_padronizado, sem vírgula)                    -> 790.54
    790,54     (como aparece formatado no SIGEF)                   -> 790.54
    1.234,56   (como aparece formatado no SIGEF, com milhar)       -> 1234.56
    """
    valor = str(valor).replace("R$", "").strip()

    # valor_padronizado (só dígitos, ex: "876675" pra R$ 8.766,75)
    if valor.isdigit():
        return float(valor) / 100

    # Valor formatado como aparece no SIGEF (ex: "8.766,75")
    return float(valor.replace(".", "").replace(",", "."))


def padronizar_mes(mes) -> str:
    """
    Aceita o mês de referência digitado em qualquer formato ("1", "01",
    "9", "12" etc.) e sempre devolve SEM zero à esquerda (ex: "1", "9",
    "12") -- é esse o formato que o <option value="..."> do combo do
    SIGEF (#cboMesComp) usa; um "0" na frente (ex: "09") faz o
    select_option não achar a opção e travar num timeout, por isso
    digitar "09" precisa virar "9" antes de preencher o combo.

    Lança ValueError se não for um número de 1 a 12.
    """
    texto = str(mes).strip()
    if not texto.isdigit():
        raise ValueError(f"Mês de referência inválido: '{mes}' (digite um número de 1 a 12).")
    numero = int(texto)
    if not 1 <= numero <= 12:
        raise ValueError(f"Mês de referência fora do intervalo 1-12: '{mes}'.")
    return str(numero)


def padronizar_valor(valor) -> tuple[str, str]:
    """
    Aceita um valor em reais digitado em qualquer um dos formatos usados
    no projeto:

        "1.105,50"   (formatado, com separador de milhar e centavos)
        "1105,50"    (formatado, sem separador de milhar)
        "1105,5"     (formatado, só 1 casa decimal)
        "110550"     (só dígitos -- os 2 últimos são os centavos)

    e devolve os DOIS formatos usados no projeto, já padronizados, pra
    que esses jeitos diferentes de digitar o MESMO valor sempre virem
    exatamente o mesmo resultado dali em diante:

        valor_padronizado -> só dígitos, 2 últimos = centavos (ex: "110550")
        valor_formatado   -> formatado em R$ (ex: "1.105,50"), pra mostrar
                             na tela e salvar como "valor" do lançamento

    Lança ValueError se o texto não puder ser interpretado como valor.
    """
    texto = str(valor).replace("R$", "").strip()
    if not texto:
        raise ValueError("Valor em branco.")

    if texto.isdigit():
        centavos = int(texto)
    else:
        try:
            centavos = round(float(texto.replace(".", "").replace(",", ".")) * 100)
        except ValueError:
            raise ValueError(f"Valor inválido: '{valor}' (ex: 1.105,50).")

    reais, cent = divmod(centavos, 100)
    valor_padronizado = str(centavos)
    valor_formatado = f"{reais:,}".replace(",", ".") + f",{cent:02d}"
    return valor_padronizado, valor_formatado


def perguntar_ou_reusar(mensagem: str, chave: str, sessao: dict) -> str:
    """
    Pergunta um valor ao usuário, oferecendo o valor salvo na sessão (se
    houver) como padrão. Basta apertar Enter pra reaproveitar o valor
    salvo, ou digitar um valor novo pra sobrescrevê-lo.
    """
    valor_salvo = sessao.get(chave)
    if valor_salvo:
        resposta = input(f"{mensagem} [Enter para manter '{valor_salvo}']: ").strip()
        return resposta if resposta else str(valor_salvo)
    return input(f"{mensagem}: ").strip()
