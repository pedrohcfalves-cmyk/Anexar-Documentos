"""
Etapa Anexar Documento: baixa os relatórios de TODOS os lançamentos já
gerados (Despesa Certificada, Ordem Bancária, Nota de Lançamento e a
própria Preparação de Pagamento), partindo da tela de Listar Preparação
de Pagamento do SIGEF (FINListarPreparacaoPagamento.aspx), e salva tudo
na pasta do processo.

A CE e a OB são as MESMAS pra todos os lançamentos de um mesmo processo
(a CE é sempre a mesma Despesa Certificada com o Valor Total, e a OB
sai igual em todas as PPs do lote) -- por isso só precisam ser baixadas
UMA VEZ, na primeira PP processada. Da segunda em diante, baixa só a NL
e a própria PP de cada lançamento.

A sequência de telas/janelas foi confirmada ao vivo, pra CADA PP do
lote:

    Listar Preparação Pagamento
      -> pesquisa pela PP (#txtGestao_SIGEFPesquisa + #txtPrepPagSeq)
      -> clica na linha da grade (#dtgPP) -> abre "Detalhar Preparação
         Pagamento Despesa Empenhada" (pagina_pp)

      [SÓ NA PRIMEIRA PP DO LOTE -- CE e OB são as mesmas pras outras]
      -> clica no número da Despesa Certificada (#txtNuDespesaCertificada)
         -> abre "Detalhar Despesa Certificada" -> Imprimir -> "Selecione
         o tipo de arquivo" -> ícone de PDF -> baixa a CE
      -> de volta na pagina_pp, clica no número da Ordem Bancária
         (#txtNuOrdemBancaria) -> abre "Detalhar Ordem Bancária" ->
         Imprimir -> "Selecione o tipo de arquivo" -> ícone de PDF ->
         baixa a OB

      [TODA PP DO LOTE]
      -> de volta na pagina_pp, clica no número da Nota de Lançamento
         (#txtNotaLancamento) -> abre "Detalhar Nota de Lançamento" ->
         Imprimir -> "Selecione o tipo de arquivo" -> ícone de PDF ->
         baixa a NL
      -> de volta na pagina_pp, clica em Imprimir na própria tela (ela
         também tem botão de Imprimir) -> "Selecione o tipo de arquivo"
         -> ícone de PDF -> baixa a própria PP
      -> fecha a pagina_pp e volta o foco pra tela de Listar Preparação
         Pagamento, pronta pra pesquisar a PRÓXIMA PP do lote

Isso substitui a necessidade de etapa_baixar_ob.py (que baixava a OB
partindo da tela "Listar Ordem Bancária", com seletores ainda não
confirmados) -- aqui não precisa procurar a OB (nem a NL) em lugar
nenhum, porque #txtNuOrdemBancaria e #txtNotaLancamento na pagina_pp já
levam direto pro detalhe de cada uma.

AINDA EM ABERTO: essa etapa termina em baixar os relatórios -- não foi
identificada nenhuma tela de UPLOAD/anexar arquivo de volta ao SIGEF.
Como agora a pagina_pp é fechada ao final de cada PP (pra poder buscar a
próxima), esse eventual passo de anexar não pode mais continuar direto
dali -- se existir, precisa ser mapeado separadamente (em qual tela ele
acontece: na Listar Preparação Pagamento? No SEI, pela Etapa SEI (2)?).

Tudo isso está numa função SÓ (executar_anexar_lote) -- as partes que se
repetiam entre CE/OB/NL/PP viraram funções internas (baixar/abrir_e_baixar,
definidas dentro dela mesma) em vez de funções separadas no arquivo, pra
não duplicar código mas sem espalhar em vários `def` diferentes.

executar_anexar_lote() recebe `processo` e a lista `lancamentos` (a
MESMA lista usada em main.py/etapa_nl.py/etapa_pp.py/etapa_ob.py, cada
item já com a chave "pp" preenchida pela Etapa PP) -- o bloco
"__main__" abaixo carrega os últimos valores salvos na sessão como
padrão, pra testar essa etapa sozinha sem rodar as anteriores de novo.
"""
import os
import re

from utils import (
    PASTA_BASE,
    URL_SIGEF_LISTAR_PP,
    carregar_sessao,
    nome_pasta_valido,
    obter_ou_criar_aba,
    pdf_para_jpg,
    perguntar_ou_reusar,
    salvar_sessao,
)


def executar_anexar_lote(
    context,
    processo: str,
    lancamentos: list[dict],
    pasta_base: str = PASTA_BASE,
    salvar_na_sessao: bool = True,
) -> list[dict]:
    """
    Roda a Etapa Anexar Documento pra TODOS os lançamentos que já têm
    uma PP gerada (item.get("pp")), um de cada vez -- sejam 3, sejam 20.

    A CE e a OB só são baixadas na primeira PP processada (são as
    mesmas pra todas as PPs desse processo); da segunda em diante, baixa
    só a NL e a própria PP de cada lançamento.

    Salva a lista de arquivos baixados em cada item
    (`item["arquivos_anexar"]`) e marca `item["anexo_baixado"] = True`
    depois de cada um. Se `salvar_na_sessao` for True (padrão), também
    salva a sessão a cada lançamento -- se o script parar no meio
    (trava, é fechado, dá erro), os que já foram baixados não são
    baixados de novo (nem a CE/OB duplicadas) na próxima execução.

    `salvar_na_sessao=False` é pra teste com uma lista de lançamentos
    "avulsa" (ex: PPs digitadas na hora, sem vir da sessão de verdade) --
    evita sobrescrever os lançamentos reais salvos em sessao_atual.json
    com esses dados de teste.

    Retorna a MESMA lista `lancamentos`.
    """
    aba_sigef = obter_ou_criar_aba(
        context,
        dominio="sigef.sefin.ro.gov.br",
        url_navegacao=URL_SIGEF_LISTAR_PP,
    )

    pasta_destino = os.path.join(pasta_base, nome_pasta_valido(processo))
    os.makedirs(pasta_destino, exist_ok=True)

    def baixar(pagina_detalhe, nome_arquivo: str, nome_temp: str) -> list[str]:
        """
        A partir de uma tela de detalhe já aberta (Despesa Certificada,
        Ordem Bancária, Nota de Lançamento ou a própria Preparação de
        Pagamento -- todas têm o mesmo botão "Imprimir"), clica em
        Imprimir, escolhe o formato PDF, baixa o relatório, converte pra
        JPG na `pasta_destino` e apaga o PDF temporário.

        Usa sempre o seletor por título (`a[title="Gerar Relatório"]`)
        em vez do id do botão -- confirmado ao vivo que o id bate em
        dois elementos (o <a> e o <img> dentro dele, porque a página
        trata id como não-sensível a maiúsculas/minúsculas), o que trava
        com "strict mode violation" se usado direto.

        Fecha só a popup do formato (aberta aqui); não fecha
        `pagina_detalhe`, já que quem chamou pode continuar usando ela.
        """
        with context.expect_page() as pagina_formato_info:
            pagina_detalhe.locator('a[title="Gerar Relatório"]').click()

        pagina_formato = pagina_formato_info.value
        pagina_formato.wait_for_load_state("networkidle")

        with context.expect_event("download") as download_info:
            pagina_formato.locator('img[alt="Imprime Arquivo Formato PostScript (.pdf)"]').click()

        download = download_info.value

        try:
            pagina_formato.close()
        except Exception:
            pass

        caminho_pdf_temp = os.path.join(pasta_destino, nome_temp)
        download.save_as(caminho_pdf_temp)

        arquivos_jpg = pdf_para_jpg(caminho_pdf_temp, pasta_destino, nome_arquivo=nome_arquivo)
        os.remove(caminho_pdf_temp)

        print(f"JPG pronto em: {arquivos_jpg}")

        return arquivos_jpg

    def abrir_e_baixar(seletor_campo: str, nome_arquivo: str, nome_temp: str) -> list[str]:
        """
        Clica em `seletor_campo` na pagina_pp (abre a tela de detalhe
        ligada -- CE, OB ou NL), baixa o relatório com baixar() e fecha
        a tela de detalhe no final.
        """
        with context.expect_page() as pagina_detalhe_info:
            pagina_pp.locator(seletor_campo).click()

        pagina_detalhe = pagina_detalhe_info.value
        pagina_detalhe.wait_for_load_state("networkidle")

        arquivos_jpg = baixar(pagina_detalhe, nome_arquivo, nome_temp)

        try:
            pagina_detalhe.close()
        except Exception:
            pass

        return arquivos_jpg

    # Se algum lançamento já passou por essa etapa antes (execução
    # anterior), a CE e a OB já foram baixadas -- não precisa de novo.
    ce_ob_ja_baixados = any(item.get("anexo_baixado") for item in lancamentos)

    for item in lancamentos:
        pp = item.get("pp")
        if not pp:
            print(f"⚠️  Lançamento sem PP (valor {item['valor']}) -- pulando o anexar.")
            continue

        if item.get("anexo_baixado"):
            print(f"⏭️  Lançamento do valor {item['valor']} (PP {pp}) já teve os relatórios baixados -- pulando.")
            continue

        print(f"\n📄 Baixando relatórios da PP {pp} (valor {item['valor']})...")

        try:
            # ------- Localiza a PP na tela de listagem -------
            aba_sigef.bring_to_front()
            aba_sigef.goto(URL_SIGEF_LISTAR_PP)
            aba_sigef.wait_for_load_state("networkidle")

            # O campo #txtPrepPagSeq só quer o número sequencial, sem o
            # prefixo de ano+"PP" que vem junto no valor salvo (ex:
            # "2026PP039777" -> "039777"). Usa regex em vez de recortar
            # um tamanho fixo de caracteres, pra funcionar também em anos
            # diferentes de 2026.
            pp_sequencial = re.sub(r"^\d+PP", "", pp)

            aba_sigef.locator("#txtGestao_SIGEFPesquisa").fill("00001")
            aba_sigef.locator("#txtPrepPagSeq").fill(pp_sequencial)
            aba_sigef.locator("#btnConfirmar").click()

            with context.expect_page() as pagina_pp_info:
                aba_sigef.locator(
                    "#dtgPP tr.GridLinhaPar, #dtgPP tr.GridLinhaImpar"
                ).first.locator("td.GridLink").first.click()

            pagina_pp = pagina_pp_info.value
            pagina_pp.wait_for_load_state("networkidle")

            arquivos_jpg = []

            if not ce_ob_ja_baixados:
                # ---- Despesa Certificada (CE) -- só na primeira PP ----
                arquivos_jpg += abrir_e_baixar("#txtNuDespesaCertificada", "Despesa Certificada", "temp_ce.pdf")
                pagina_pp.bring_to_front()
                pagina_pp.wait_for_load_state("networkidle")

                # ---- Ordem Bancária (OB) -- só na primeira PP ----
                arquivos_jpg += abrir_e_baixar("#txtNuOrdemBancaria", "Ordem Bancária", "temp_ob.pdf")
                pagina_pp.bring_to_front()
                pagina_pp.wait_for_load_state("networkidle")

            # ---- Nota de Lançamento (NL) -- toda PP ----
            # Nome do arquivo leva a PP junto pra não sobrescrever a NL
            # de um lançamento com a de outro na mesma pasta.
            arquivos_jpg += abrir_e_baixar("#txtNotaLancamento", f"Nota de Lançamento - PP {pp}", "temp_nl.pdf")
            pagina_pp.bring_to_front()
            pagina_pp.wait_for_load_state("networkidle")

            # ---- Preparação de Pagamento (PP) -- toda PP ----
            # A própria pagina_pp já tem seu botão "Imprimir" -- não
            # precisa abrir nenhuma tela de detalhe antes.
            arquivos_jpg += baixar(pagina_pp, f"Preparação de Pagamento - PP {pp}", "temp_pp.pdf")

            # Fecha a página de detalhe da PP e volta pra tela de
            # listagem -- pronta pra pesquisar a próxima PP do lote.
            try:
                pagina_pp.close()
            except Exception:
                pass

            aba_sigef.bring_to_front()
            aba_sigef.wait_for_load_state("networkidle")
        except Exception as erro:
            print(f"⚠️  Erro ao baixar os relatórios da PP {pp} (valor {item['valor']}): {erro}")
            continue

        item["arquivos_anexar"] = arquivos_jpg
        item["anexo_baixado"] = True
        if salvar_na_sessao:
            # Salva depois de CADA lançamento -- ver docstring acima.
            salvar_sessao(lancamentos=lancamentos)

        ce_ob_ja_baixados = True

        print(f"✅ PP {pp}: {len(arquivos_jpg)} arquivo(s) pronto(s) em {pasta_destino}")

    return lancamentos


if __name__ == "__main__":
    # Teste isolado da Etapa Anexar Documento: conecta no Chrome já
    # aberto e roda o lote inteiro usando os lançamentos já salvos na
    # sessão (os mesmos preenchidos por main.py / etapa_nl.py /
    # etapa_pp.py / etapa_ob.py, cada um já com a chave "pp") -- não
    # precisa rodar as etapas anteriores de novo.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        processo = perguntar_ou_reusar(
            "Digite o processo do SEI (para nomear a pasta)", "processo", sessao
        )
        # Modo de teste: pergunta as PPs UMA DE CADA VEZ (aperta Enter em
        # branco quando terminar de digitar) -- evita confusão com
        # separador (vírgula, espaço etc.) e deixa óbvio quantas PPs
        # entraram na lista antes de rodar. Se não digitar nenhuma
        # (Enter na primeira já), usa os lançamentos salvos na sessão.
        print(
            "Digite as PPs pra testar, uma de cada vez (Enter em branco "
            "quando terminar) -- ou Enter direto pra usar os lançamentos "
            "salvos na sessão:"
        )
        pps_digitadas = []
        while True:
            pp_digitada = input(f"  PP #{len(pps_digitadas) + 1} (ou Enter pra terminar): ").strip()
            if not pp_digitada:
                break
            pps_digitadas.append(pp_digitada)

        if pps_digitadas:
            print(f"➡️  {len(pps_digitadas)} PP(s) digitada(s): {', '.join(pps_digitadas)}")
            # Modo de teste: monta uma lista de lançamentos "avulsa" só
            # com as PPs digitadas, sem mexer na sessão de verdade --
            # útil pra testar uma ou mais PPs sem depender do que já
            # está (ou não) salvo em sessao_atual.json.
            lancamentos = [
                {"pp": pp, "valor": f"TESTE PP {pp}"}
                for pp in pps_digitadas
            ]
            salvar_na_sessao = False
        else:
            lancamentos = sessao.get("lancamentos") or []
            salvar_na_sessao = True

        if not lancamentos:
            print("⚠️  Nenhuma PP digitada e nenhum lançamento salvo na sessão (chave 'lancamentos' vazia ou ausente).")
        else:
            lancamentos = executar_anexar_lote(context, processo, lancamentos, salvar_na_sessao=salvar_na_sessao)
            print(f"\n{'=' * 50}\nRESUMO\n{'=' * 50}")
            for i, item in enumerate(lancamentos, start=1):
                status = "✅" if item.get("anexo_baixado") else "⚠️ "
                print(f"{status} {i}) Valor {item['valor']} | PP {item.get('pp')} | arquivos: {item.get('arquivos_anexar')}")
    finally:
        playwright.stop()
