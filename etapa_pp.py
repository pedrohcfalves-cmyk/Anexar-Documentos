"""
Etapa PP: Preparação de Pagamento da Despesa Empenhada no SIGEF.

Cada lançamento tem sua própria NL (gerada na Etapa NL), mas todas
compartilham a mesma CE. executar_pp_lote() abre a página da PP uma
única vez e repete, pra cada lançamento, o ciclo de localizar a NL/CE
na tela de Gerar Ordem Cronológica, confirmar o item encontrado e
preencher o tipo de Ordem Bancária + banco/agência/conta -- sem
recarregar a página inteira entre um lançamento e outro.

executar_pp_lote() recebe `ce`, a lista de lançamentos (já com "nl") e
`conta_pp` direto, pra dar pra testar essa etapa sozinha sem rodar as
anteriores de novo -- o bloco "__main__" abaixo carrega os últimos
valores salvos na sessão como padrão e testa com um lançamento só.
"""
import re
from datetime import date

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from utils import (
    URL_SIGEF_PP,
    carregar_sessao,
    obter_ou_criar_aba,
    perguntar_ou_reusar,
    salvar_sessao,
)


def _incluir_pp(aba_sigef, context, nl: str, ce: str, conta_pp: str) -> str | None:
    """
    Localiza o lançamento pelos números `nl` e `ce` na tela de Gerar
    Ordem Cronológica, confirma o item encontrado e prepara o pagamento
    na conta `conta_pp`.

    Retorna o número da PP gerado (com prefixo, ex: "2026PP047704"), ou
    None se não for possível gerar.
    """
    ano_atual = str(date.today().year)

    aba_sigef.locator("#txtGestao_SIGEFPesquisa").fill("00001")

    with context.expect_page() as nova_pagina_info:
        aba_sigef.locator("#txtNotaLancamento_BtnPesquisa").click()

    nova_pagina = nova_pagina_info.value
    nova_pagina.wait_for_load_state("networkidle")

    with context.expect_page() as nova_pagina1_info:
        nova_pagina.locator("#lnkNaoObedeceOrdemCronologica").click()

    nova_pagina1 = nova_pagina1_info.value
    nova_pagina1.wait_for_load_state("networkidle")

    nova_pagina1.locator("#txtNotaLancamentoSigla").fill(ano_atual)
    nova_pagina1.locator("#txtDespesaCertificadaSigla").fill(ano_atual)
    nova_pagina1.locator("#txtNotaLancamento_SIGEFPesquisa").fill(nl)
    nova_pagina1.locator("#txtDespesaCertificada_SIGEFPesquisa").fill(ce)
    nova_pagina1.locator("#btnConfirmar").click()
    nova_pagina1.locator("#divdtgGerarOrdemCronologica td.GridLink").first.click()

    for pagina_temp in (nova_pagina1, nova_pagina):
        try:
            pagina_temp.close()
        except Exception:
            pass

    aba_sigef.bring_to_front()
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.wait_for_selector("#cboTipoOrdemBancaria", state="visible", timeout=5000)

    # #cboTipoOrdemBancaria dispara um postback -- TEM que ser selecionado
    # ANTES de preencher banco/agência/conta, senão o postback limpa esses
    # campos de novo.
    aba_sigef.locator("#cboTipoOrdemBancaria").select_option(value="3")
    aba_sigef.wait_for_load_state("networkidle")

    aba_sigef.locator("#txtBanco").fill("001")
    aba_sigef.locator("#txtAgencia").fill("27570")
    aba_sigef.locator("#txtConta_SIGEFPesquisa").fill(conta_pp)

    aba_sigef.wait_for_selector("#txtConta_SIGEFPesquisa", state="visible", timeout=5000)
    aba_sigef.locator("#btnRetencoes").click()
    aba_sigef.wait_for_load_state("networkidle")
    aba_sigef.locator("img[src*='aba_confirmacao.gif']").click()

    aba_sigef.locator("#btnConfirmar").click()

    # O clique dispara um postback assíncrono -- conferir o elemento na
    # hora (sem esperar) pode achar que não tem nada lá ainda e devolver
    # None mesmo quando a PP FOI gerada no SIGEF. Isso é grave: o
    # lançamento fica marcado como falho e, na próxima execução, o
    # script tentaria gerar OUTRA PP pro mesmo lançamento -- duplicando.
    # Por isso espera a mensagem de sucesso aparecer antes de decidir.
    elemento_sucesso = aba_sigef.locator("td.SIGEFMensagemSucesso").first
    try:
        elemento_sucesso.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        return None

    texto_sucesso = elemento_sucesso.inner_text().strip()
    print(f"Mensagem de sucesso: {texto_sucesso}")

    # Extrai só o número COM prefixo (ex: "2026PP047704") -- é esse
    # formato que aparece na grade da Etapa OB, pra comparação lá bater.
    match = re.search(r"\d{4}PP\d+", texto_sucesso)
    pp = match.group(0) if match else texto_sucesso

    # Limpa a tela de PP de forma segura antes de devolver o número.
    try:
        aba_sigef.locator('img[src="/SIGEF/Recursos/Controles/Imagens/Limpar.GIF"]').click()
    except Exception:
        pass

    return pp


def executar_pp_lote(context, ce: str, lancamentos: list[dict], conta_pp: str, dados: dict = None) -> list[dict]:
    """
    Gera a PP de cada lançamento da lista (cada um já com sua "nl",
    vinda de executar_nl_lote), sem recarregar a página inteira entre
    um lançamento e outro.

    Retorna a MESMA lista `lancamentos`, com a chave "pp" adicionada em
    cada item (o número gerado, ou None se não foi possível gerar).
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigef.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_PP,
    )
    aba_sigef.goto(URL_SIGEF_PP)
    aba_sigef.wait_for_load_state("networkidle")

    for item in lancamentos:
        if item.get("pp"):
            # Já tem PP de uma execução anterior -- pula pra não gerar
            # duplicado.
            print(f"⏭️  Lançamento do valor {item['valor']} já tem PP ({item['pp']}) -- pulando.")
            continue

        nl = item.get("nl")
        if not nl:
            print(f"⚠️  Lançamento sem NL (valor {item['valor']}) -- pulando a PP.")
            item["pp"] = None
            continue

        item["pp"] = _incluir_pp(aba_sigef, context, nl, ce, conta_pp)
        if item["pp"]:
            print(f"PP gerada para o valor {item['valor']}: {item['pp']}")
        else:
            print(f"⚠️  Não foi possível gerar a PP para o valor {item['valor']}.")
        salvar_sessao(lancamentos=lancamentos)

    return lancamentos


if __name__ == "__main__":
    # Teste isolado da Etapa PP: conecta no Chrome já aberto e pede o
    # CE, a conta PP e um lançamento de teste (NL + valor) diretamente
    # pelo teclado — não precisa rodar as etapas anteriores de novo.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        ce = perguntar_ou_reusar("Digite o CE (gerado na Etapa CE)", "ce", sessao)
        conta_pp = perguntar_ou_reusar("Digite a conta PP", "conta_pp", sessao)
        nl = perguntar_ou_reusar("Digite a NL (gerada na Etapa NL)", "nl", sessao)
        valor_padronizado = perguntar_ou_reusar(
            "Digite o valor padronizado desse lançamento (ex: 787875)",
            "valor_padronizado",
            sessao,
        )
        item_teste = {"valor": valor_padronizado, "valor_padronizado": valor_padronizado, "nl": nl}
        resultado = executar_pp_lote(context, ce, [item_teste], conta_pp)
        print(f"OK: PP processada para a NL '{nl}'. Número da PP: {resultado[0]['pp']}")
    finally:
        playwright.stop()
