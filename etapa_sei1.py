"""
Etapa SEI (1): localizar a aba do SEI e abrir/pesquisar o processo,
expandindo a árvore de pastas para deixá-lo pronto para as próximas
etapas (CE, NL, PP, OB, SEI(2)).
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from utils import (
    URL_SEI,
    carregar_sessao,
    confirmar,
    normalizar,
    obter_ou_criar_aba,
    padronizar_mes,
    padronizar_valor,
    perguntar_ou_reusar,
    salvar_sessao,
)


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


MAX_LANCAMENTOS = 20
LARGURA = 56


def _cabecalho(texto: str, borda: str = "=") -> None:
    """Imprime um título centralizado dentro de uma faixa de bordas."""
    print("\n" + borda * LARGURA)
    print(texto.center(LARGURA))
    print(borda * LARGURA)


def _mostrar_lancamentos(lancamentos: list[dict]) -> None:
    if not lancamentos:
        print("     (nenhum lançamento ainda)")
        return
    for i, item in enumerate(lancamentos, start=1):
        print(f"     {i}. R$ {item['valor']:<12} NE {item['nota_de_empenho']}")


def _mostrar_total(lancamentos: list[dict], valor_total: str = None) -> None:
    """Mostra a soma dos lançamentos e, se houver um Valor Total pra
    comparar, avisa quando os dois não batem (ajuda a pegar erro de
    digitação antes de seguir em frente)."""
    if not lancamentos:
        return
    soma = sum(normalizar(item["valor"]) for item in lancamentos)
    print(f"     {'-' * (LARGURA - 10)}")
    print(f"     Total lançado: R$ {soma:.2f}")
    if valor_total:
        diferenca = abs(soma - normalizar(valor_total))
        if diferenca > 0.01:
            print(f"     ⚠️  Valor Total informado: R$ {normalizar(valor_total):.2f} (não bate!)")
        else:
            print(f"     ✅ Confere com o Valor Total (R$ {normalizar(valor_total):.2f})")


def coletar_lancamentos(sessao: dict, valor_total: str = None) -> list[dict]:
    """
    Submenu expansivo para coletar os lançamentos (Valor + Nota de
    Empenho) do processo -- de 1 até MAX_LANCAMENTOS.

    Cada lançamento vira sua própria NL/PP/OB (ver main.py); só a CE é
    feita uma vez, com o Valor Total. Por isso cada lançamento precisa
    do seu próprio valor e da sua própria nota de empenho -- o resto
    dos dados do processo é compartilhado entre eles.

    Se já existir uma lista salva na sessão de uma execução anterior,
    oferece reaproveitá-la; senão começa uma lista vazia.
    """
    lancamentos = list(sessao.get("lancamentos") or [])

    if lancamentos:
        _cabecalho("📋 LANÇAMENTOS SALVOS DA ÚLTIMA VEZ")
        _mostrar_lancamentos(lancamentos)
        _mostrar_total(lancamentos, valor_total)
        if confirmar("\nReaproveitar essa lista? (S/N): "):
            soma = sum(normalizar(item["valor"]) for item in lancamentos)
            bate_com_total = not valor_total or abs(soma - normalizar(valor_total)) <= 0.01
            if bate_com_total:
                # Já bate com o Valor Total -- reaproveita direto, sem
                # pedir pra passar pelo menu de novo.
                return lancamentos
            print(
                "\n⚠️  Essa lista salva não bate mais com o Valor Total "
                "atual -- revise antes de continuar.\n"
            )
        else:
            lancamentos = []

    while True:
        _cabecalho(f"💵 LANÇAMENTOS -- {len(lancamentos)}/{MAX_LANCAMENTOS}")

        if not lancamentos:
            print("  O QUE É UM LANÇAMENTO?")
            print("  É cada parte em que o Valor Total foi dividido -- cada")
            print("  parte com seu próprio valor e sua própria Nota de")
            print("  Empenho (NE). Cada lançamento gera, sozinho, uma")
            print("  NL + PP + OB, um de cada vez, em ordem.\n")
            print("  EXEMPLO: Valor Total de R$ 5.335,50, dividido em 3")
            print("  notas de empenho, vira 3 lançamentos:")
            print("     1. R$ 2.265,75   |  NE 002180")
            print("     2. R$ 2.465,25   |  NE 002181")
            print("     3. R$   604,50   |  NE 002182\n")
            print("  COMO USAR ESSE MENU:")
            print("     [A] adiciona um lançamento (repita pra cada um)")
            print("     [C] conclui quando já tiver lançado tudo\n")
            print("  Pode digitar o valor como preferir -- 1.105,50 ou")
            print("  1105,50 ou 110550 são todos o mesmo valor.\n")
        else:
            print("  Continue adicionando até o Total lançado bater com o")
            print("  Valor Total. Errou algum? Use [R] pra remover o")
            print("  último e adicionar de novo. Quando terminar, [C].\n")

        _mostrar_lancamentos(lancamentos)
        _mostrar_total(lancamentos, valor_total)
        print("-" * LARGURA)
        print("  [A] Adicionar um lançamento novo")
        if lancamentos:
            print("  [R] Remover o último que foi adicionado")
            print("  [C] Concluir e seguir em frente")
        print("-" * LARGURA)

        escolha = input("Escolha uma opção: ").strip().upper()

        if escolha == "A":
            if len(lancamentos) >= MAX_LANCAMENTOS:
                print(f"⚠️  Máximo de {MAX_LANCAMENTOS} lançamentos atingido.")
                continue
            print()
            valor_digitado = input("  💰 Valor deste lançamento (ex: 5.335,50): ").strip()
            nota_de_empenho = input("  📄 Nota de Empenho deste lançamento (ex: 002180): ").strip()
            if not valor_digitado or not nota_de_empenho:
                print("⚠️  Valor e Nota de Empenho não podem ficar em branco.")
                continue
            try:
                valor_padronizado, valor = padronizar_valor(valor_digitado)
            except ValueError as erro:
                print(f"⚠️  {erro}")
                continue
            lancamentos.append(
                {
                    "valor": valor,
                    "valor_padronizado": valor_padronizado,
                    "nota_de_empenho": nota_de_empenho,
                }
            )
        elif escolha == "R" and lancamentos:
            removido = lancamentos.pop()
            print(f"🗑 Removido: R$ {removido['valor']} | NE {removido['nota_de_empenho']}")
        elif escolha == "C" and lancamentos:
            return lancamentos
        else:
            print("⚠️  Opção inválida -- escolha uma das letras mostradas acima.")


def _mostrar_dados_salvos(sessao: dict) -> None:
    """
    Mostra, antes de qualquer pergunta, o que já está salvo de uma
    execução anterior -- pra a pessoa ver de cara o que vai ser
    reaproveitado (basta apertar Enter em cada pergunta pra manter).
    """
    campos = [
        ("👤 CNPJ/CPF", sessao.get("cnpj_cpf")),
        ("📍 Município", sessao.get("municipio")),
        ("🏫 Escola", sessao.get("escola")),
        ("🏦 Conta PP", sessao.get("conta_pp")),
        ("🏦 Conta OB", sessao.get("conta_ob")),
        ("🔢 Parcela", sessao.get("parcela")),
        ("📅 Mês de Referência", sessao.get("mes_referencia")),
        ("📌 Programa", sessao.get("programa")),
        ("💰 Valor Total (CE)", sessao.get("valor_total")),
    ]
    if not any(valor for _, valor in campos):
        return  # primeira execução -- ainda não tem nada salvo

    _cabecalho("📋 DADOS SALVOS DA ÚLTIMA VEZ")
    for rotulo, valor in campos:
        if valor:
            print(f"  {rotulo:<24}: {valor}")

    lancamentos_salvos = sessao.get("lancamentos") or []
    if lancamentos_salvos:
        print(f"  💵 Lançamentos ({len(lancamentos_salvos)}):")
        _mostrar_lancamentos(lancamentos_salvos)

    print("-" * LARGURA)
    print("  Aperte Enter em cada pergunta pra manter o que está salvo,")
    print("  ou digite um valor novo pra substituir.")
    print("=" * LARGURA)


def coletar_dados_sigef() -> dict:
    """
    Pergunta interativamente os dados necessários para as automações do
    SIGEF (CE, NL, PP, OB), mostra um resumo e só segue depois de
    confirmado (S/N). Repete a coleta se o usuário responder N.

    Esses dados são coletados aqui, na etapa do SEI (é lá que o operador
    consulta o processo para obter os valores), e depois são reutilizados
    em todas as etapas seguintes do SIGEF, sem precisar perguntar de novo.
    Valor e Nota de Empenho variam por lançamento (ver
    coletar_lancamentos()) -- o resto é compartilhado entre eles.

    Cada pergunta já oferece o último valor salvo (arquivo de sessão)
    como padrão — aperte Enter pra reaproveitar, ou digite um valor novo
    pra trocar. No final, os valores confirmados são salvos de novo na
    sessão (sobrescrevendo os anteriores) para uso nas próximas etapas.
    """
    sessao = carregar_sessao()
    _mostrar_dados_salvos(sessao)

    while True:
        _cabecalho("📝 DADOS DO PROCESSO")

        cnpj_cpf = perguntar_ou_reusar("👤 Digite o CNPJ/CPF", "cnpj_cpf", sessao)
        municipio = perguntar_ou_reusar("📍 Digite o nome do município", "municipio", sessao)
        escola = perguntar_ou_reusar("🏫 Digite o nome da escola", "escola", sessao)
        conta_pp = perguntar_ou_reusar("🏦 Digite a conta PP", "conta_pp", sessao)
        conta_ob = perguntar_ou_reusar("🏦 Digite a conta OB", "conta_ob", sessao)
        parcela = perguntar_ou_reusar("🔢 Digite a parcela", "parcela", sessao)

        while True:
            mes_digitado = perguntar_ou_reusar(
                "📅 Digite o mês de referência (1-12)", "mes_referencia", sessao
            )
            try:
                mes_referencia = padronizar_mes(mes_digitado)
                break
            except ValueError as erro:
                print(f"⚠️  {erro}")

        programa = perguntar_ou_reusar("📌 Digite o programa", "programa", sessao)

        # O Valor Total é o valor da CE (gerada uma única vez); os
        # lançamentos abaixo são as partes desse total, cada uma com sua
        # própria NL/PP/OB. Aceita qualquer formato (1.105,50 / 1105,50 /
        # 110550) -- padronizar_valor() garante que todos viram o mesmo.
        while True:
            valor_total_digitado = perguntar_ou_reusar(
                "💰 Digite o Valor Total da Parcela (usado na CE)", "valor_total", sessao
            )
            try:
                valor_total_padronizado, valor_total = padronizar_valor(valor_total_digitado)
                break
            except ValueError as erro:
                print(f"⚠️  {erro}")

        lancamentos = coletar_lancamentos(sessao, valor_total)

        # Atualiza os padrões usados acima, pro caso de o usuário responder
        # N e a coleta rodar de novo (reaproveita o que acabou de digitar).
        sessao.update(
            {
                "cnpj_cpf": cnpj_cpf,
                "municipio": municipio,
                "escola": escola,
                "conta_pp": conta_pp,
                "conta_ob": conta_ob,
                "parcela": parcela,
                "mes_referencia": mes_referencia,
                "programa": programa,
                "valor_total": valor_total,
                "lancamentos": lancamentos,
            }
        )

        _cabecalho("✅ CONFIRA OS DADOS", borda="-")
        print(f"  👤 CNPJ/CPF               : {cnpj_cpf}")
        print(f"  📍 Município              : {municipio}")
        print(f"  🏫 Escola                 : {escola}")
        print(f"  🏦 Conta PP               : {conta_pp}")
        print(f"  🏦 Conta OB               : {conta_ob}")
        print(f"  🔢 Parcela                : {parcela}")
        print(f"  📅 Mês de Referência      : {mes_referencia}")
        print(f"  📌 Programa               : {programa}")
        print(f"  💰 Valor Total (CE)       : {valor_total}")
        print(f"  💵 Lançamentos ({len(lancamentos)}):")
        _mostrar_lancamentos(lancamentos)
        _mostrar_total(lancamentos, valor_total)
        print("-" * LARGURA)

        if confirmar("Os dados acima estão certos? (S/N): "):
            break
        print("\n🔄 Ok, vamos preencher novamente.\n")

    dados = {
        "cnpj_cpf": cnpj_cpf,
        "municipio": municipio,
        "escola": escola,
        "conta_pp": conta_pp,
        "conta_ob": conta_ob,
        "parcela": parcela,
        "mes_referencia": mes_referencia,
        "programa": programa,
        "valor_total": valor_total,
        "valor_total_padronizado": valor_total_padronizado,
        "lancamentos": lancamentos,
    }
    salvar_sessao(**dados)
    return dados


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
        sessao = carregar_sessao()
        processo = perguntar_ou_reusar("Digite o processo do SEI", "processo", sessao)

    abrir_processo_sei(aba_sei, processo)
    salvar_sessao(processo=processo)

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
