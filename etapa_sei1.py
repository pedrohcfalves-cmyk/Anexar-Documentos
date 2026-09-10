"""
Etapa SEI (1): localizar a aba do SEI e abrir/pesquisar o processo,
expandindo a árvore de pastas para deixá-lo pronto para as próximas
etapas (CE, NL, PP, OB, SEI(2)).
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils import URL_SEI, confirmar, obter_ou_criar_aba


def abrir_processo_sei(aba_sei: Page, processo: str, timeout_ms: int = 15000) -> None:
    """
    Abre o processo informado no SEI: pesquisa o processo pelo número na
    aba já focada e expande todas as pastas da árvore de documentos.

    Lança RuntimeError com uma mensagem clara caso algum passo falhe
    (elemento não respondeu a tempo, processo não localizado etc.), em
    vez de deixar o script travar silenciosamente em um timeout do
    Playwright.
    """
    try:
        aba_sei.locator('img.infraImg[title="Controle de Processos"]:visible').click(
            timeout=timeout_ms
        )
        aba_sei.locator("#txtPesquisaRapida").fill(processo, timeout=timeout_ms)
        aba_sei.locator('img.infraImg[title="Pesquisa Rápida"]:visible').click(
            timeout=timeout_ms
        )
    except PlaywrightTimeoutError as erro:
        raise RuntimeError(
            f"Não foi possível pesquisar o processo '{processo}' no SEI: "
            f"elemento da tela de pesquisa não respondeu a tempo ({erro})."
        ) from erro

    try:
        aba_sei.frame_locator("#ifrArvore").locator(
            'img[title="Abrir todas as Pastas"]:visible'
        ).click(timeout=timeout_ms)
    except PlaywrightTimeoutError as erro:
        raise RuntimeError(
            f"Processo '{processo}' pesquisado, mas não foi possível abrir as "
            f"pastas da árvore no SEI (verifique se o processo foi encontrado): {erro}"
        ) from erro


def coletar_dados_sigef() -> dict:
    """
    Pergunta interativamente os dados necessários para as automações do
    SIGEF (CE, NL, PP, OB), mostra um resumo e só segue depois de
    confirmado (S/N). Repete a coleta se o usuário responder N.

    Esses dados são coletados aqui, na etapa do SEI (é lá que o operador
    consulta o processo para obter os valores), e depois são reutilizados
    em todas as etapas seguintes do SIGEF, sem precisar perguntar de novo.
    """
    while True:
        print("=" * 50)
        print("  Coloque as informações a baixo para preencher o sistema do sigef")
        print("=" * 50)

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
            break
        print("\n🔄 Ok, vamos preencher novamente.\n")

    return {
        "valor": valor,
        "valor_padronizado": valor.replace(".", "").replace(",", ""),  # 7.878,75 -> 787875
        "cnpj_cpf": cnpj_cpf,
        "municipio": municipio,
        "escola": escola,
        "conta_pp": conta_pp,
        "conta_ob": conta_ob,
        "parcela": parcela,
        "mes_referencia": mes_referencia,
        "programa": programa,
    }


def executar_sei1(context, processo: str = None) -> tuple[Page, str, dict]:
    """
    Executa a Etapa SEI (1) completa: obtém/cria a aba do SEI, garante que
    ela está em foco, pergunta o número do processo (se não informado),
    abre/pesquisa esse processo e coleta os dados que serão usados em
    todas as automações do SIGEF (CE, NL, PP, OB).

    Retorna a aba do SEI, o número do processo e o dict de dados
    coletados, para uso nas próximas etapas (CE, NL, PP, OB, SEI(2)).
    """
    aba_sei = obter_ou_criar_aba(
        context,
        dominio="sei.sistemas.ro.gov.br",
        url_navegacao=URL_SEI,
    )
    aba_sei.bring_to_front()

    if processo is None:
        processo = input("Digite o processo do SEI: ").strip()

    abrir_processo_sei(aba_sei, processo)

    dados = coletar_dados_sigef()

    return aba_sei, processo, dados


if __name__ == "__main__":
    # Teste isolado da Etapa SEI (1): conecta no Chrome já aberto e só
    # executa essa etapa, sem depender do restante do fluxo.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        input("Sua conta já foi aberta no SEI? (S/N) ")
        aba_sei, processo, dados = executar_sei1(context)
        print(f"OK: processo '{processo}' aberto e pastas expandidas no SEI.")
        print("Dados coletados:", dados)
    finally:
        playwright.stop()
