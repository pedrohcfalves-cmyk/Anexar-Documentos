"""
Orquestra o fluxo completo de regularização, na ordem:

    Login (1x) -> SEI(1) -> CE (1x, Valor Total) -> NL (em lote) ->
    PP (em lote) -> OB (1x por lançamento) -> Anexar Documento (baixa os
    relatórios do SIGEF) -> SEI(2) (anexa tudo de volta no processo)

O ciclo inteiro (executar_ciclo) roda pra UM processo por vez. main()
repete esse ciclo automaticamente pro PRÓXIMO processo -- perguntando,
ao final de cada um, se quer continuar -- até o usuário decidir parar
(respondendo "N", ou fechando o programa com Ctrl+C).

Antes do primeiro SEI(1), garantir_chrome_pronto() garante que existe um
Chrome de depuração aberto (abrindo um automaticamente se preciso -- ver
conectar_chrome() em utils.py) e preparar_sessao_login() abre as abas do
SEI e do SIGEF (sem nenhuma automação de preenchimento) e pede uma
confirmação de que o usuário já entrou com a própria conta nos dois.
Isso roda só UMA VEZ -- ou de novo, automaticamente, se o Chrome de
depuração tiver sido fechado nesse meio tempo (detectado no início de
cada ciclo novo).

O SEI(1) roda uma vez por processo: abre o processo e coleta os dados
compartilhados (CNPJ/CPF, contas, escola etc.), o Valor Total da
parcela e a lista de lançamentos desse processo -- de 1 a 20 pares de
Valor + Nota de Empenho que somados dão o Valor Total (ver
coletar_lancamentos() em etapa_sei1.py).

A CE é gerada uma única vez, com o Valor Total (é a mesma Despesa
Certificada pra todos os lançamentos). A partir dela, as NLs de todos os
lançamentos são geradas em sequência sem recarregar a página
(executar_nl_lote), e o mesmo vale para as PPs (executar_pp_lote) --
recarregar a página a cada lançamento seria lento e desnecessário, já
que a CE é sempre a mesma. Só a OB roda uma vez por lançamento, usando a
PP e o valor que cada um gerou.

Com CE + NL + PP + OB de todos os lançamentos prontos, a Etapa Anexar
Documento (etapa_listar_baixar.py) baixa os relatórios de cada um (CE,
OB, NL, PP) direto do SIGEF, já convertidos em JPG, na pasta do
processo (a CE e a OB são as mesmas pra todos os lançamentos, então só
são baixadas uma vez). Por fim, a Etapa SEI (2) (etapa_sei2.py) volta
pro SEI, reabre o processo e inclui esses JPGs como documentos novos
(CE, uma NL + uma PP por lançamento, e a OB), cada um já com Nível de
Acesso (Restrito) e Hipótese Legal (Documento Preparatório) preenchidos.

Se um lançamento não conseguir gerar sua NL/PP/OB (ou baixar/anexar o
relatório), ele fica marcado como pendente no resumo final e o loop
segue pro próximo -- uma falha não derruba os demais.
"""
from etapa_sei1 import executar_sei1
from etapa_ce import executar_ce
from etapa_nl import executar_nl_lote
from etapa_pp import executar_pp_lote
from etapa_ob import executar_ob
from etapa_listar_baixar import executar_anexar_lote
from etapa_sei2 import executar_sei2
from utils import (
    URL_SEI,
    URL_SIGEF,
    carregar_sessao,
    confirmar,
    conectar_chrome,
    obter_ou_criar_aba,
    salvar_sessao,
)


def obter_ce(context, processo: str, dados_ce: dict) -> tuple[str, bool]:
    """
    Antes de gerar uma CE nova, confere se já existe uma CE salva de uma
    execução anterior (mesmo mecanismo dos outros dados -- ver
    coletar_dados_sigef() em etapa_sei1.py). Se existir, pergunta se
    quer reaproveitá-la em vez de gerar outra -- evita duplicar a CE no
    SIGEF e economiza o tempo de preencher o formulário de novo.

    Responder N (ou não existir nenhuma CE salva) gera uma CE nova
    normalmente.

    Retorna (ce, reaproveitada) -- o chamador usa `reaproveitada` pra
    saber se pode confiar nas NL/PP/OB/anexos já salvos (mesma CE) ou se
    eles pertencem a uma CE antiga e precisam ser refeitos (ver
    executar_ciclo()).
    """
    sessao = carregar_sessao()
    ce_salvo = sessao.get("ce")

    if ce_salvo:
        print(f"\n{'=' * 50}")
        print("📦 JÁ EXISTE UMA CE GERADA ANTES")
        print(f"{'=' * 50}")
        print(f"  CE salvo          : {ce_salvo}")
        print(f"  Valor Total atual : R$ {dados_ce['valor_total']}")
        print(f"{'-' * 50}")
        print("  Se essa CE já foi gerada certinho pra esse Valor Total,")
        print("  não precisa gerar outra -- é só reaproveitar o número e")
        print("  seguir direto pra NL.")
        print(f"{'=' * 50}")
        if confirmar("Pular a geração da CE e reaproveitar esse número? (S/N): "):
            print(f"➡️  Reaproveitando a CE {ce_salvo} -- pulando direto para a NL.")
            return ce_salvo, True
        print("🔄 Ok, gerando uma CE nova.")

    return executar_ce(context, processo, dados_ce), False


def gerar_obs(context, dados: dict, lancamentos: list[dict]) -> list[dict]:
    """
    Gera a OB de cada lançamento que já tem uma PP, usando o valor
    daquele lançamento e a conta OB compartilhada do SEI(1).

    Retorna a MESMA lista `lancamentos`, com a chave "ob" adicionada em
    cada item.
    """
    for item in lancamentos:
        if item.get("ob"):
            # Já tem OB de uma execução anterior -- pula pra não gerar
            # duplicado.
            print(f"⏭️  Lançamento do valor {item['valor']} já tem OB ({item['ob']}) -- pulando.")
            continue

        pp = item.get("pp")
        if not pp:
            print(f"⚠️  Lançamento sem PP (valor {item['valor']}) -- pulando a OB.")
            item["ob"] = None
            continue

        dados_lancamento = {**dados, **item}
        try:
            item["ob"] = executar_ob(context, pp, dados["conta_ob"], item["valor_padronizado"], dados_lancamento)
        except Exception as erro:
            # Um erro num lançamento (ex: PP não encontrada na grade) não
            # pode derrubar os outros -- registra a falha e segue pro
            # próximo, igual já funciona na NL e na PP.
            print(f"⚠️  Erro ao gerar a OB para o valor {item['valor']} (PP {pp}): {erro}")
            item["ob"] = None

        if item["ob"] is None:
            print(f"⚠️  Não foi possível gerar a OB para o valor {item['valor']}.")

        # Salva depois de CADA lançamento -- se o script parar no meio
        # (trava, é fechado, dá erro), as OBs já geradas com sucesso não
        # se perdem e não seriam geradas de novo (duplicadas) na próxima
        # execução.
        salvar_sessao(lancamentos=lancamentos)

    return lancamentos


def reiniciar_sessao_para_novo_processo() -> None:
    """
    Limpa, na sessão salva, só os dados que pertencem ao processo que
    ACABOU DE SER concluído (processo, CE, a OB avulsa e a lista de
    lançamentos com suas NL/PP/OB/anexos) -- antes de começar o ciclo do
    PRÓXIMO processo, no loop de main().

    Sem isso, a Etapa SEI (1) ofereceria reaproveitar a CE e os
    lançamentos (já com NL/PP/OB/anexos preenchidos) do processo
    ANTERIOR -- e as etapas seguintes pulariam tudo achando que o
    processo NOVO já tivesse sido feito, sem gerar nada de fato.

    Os demais dados (CNPJ/CPF, contas, escola, parcela, mês de
    referência, programa) continuam salvos e disponíveis pra
    reaproveitar -- cada pergunta da Etapa SEI (1) permite digitar um
    valor novo ou manter o anterior (apertando Enter).
    """
    salvar_sessao(processo="", ce="", ob="", lancamentos=[])


def preparar_sessao_login(context) -> None:
    """
    Abre (ou reaproveita, se já estiverem abertas) as abas do SEI e do
    SIGEF nesse Chrome -- só NAVEGA até elas (mesma obter_ou_criar_aba
    usada por todas as etapas), sem clicar em nada nem preencher nada --
    e pede uma confirmação de que o usuário já entrou com a própria
    conta nos dois sistemas antes de seguir com o resto do fluxo.

    Chamada por garantir_chrome_pronto() só quando o Chrome acabou de
    ser (re)conectado -- ou seja, uma vez por Chrome de depuração aberto,
    não uma vez por processo.
    """
    print(f"\n{'=' * 50}")
    print("🔐 LOGIN NO SEI E NO SIGEF")
    print(f"{'=' * 50}")
    print("Abrindo as abas do SEI e do SIGEF nesse Chrome...")

    obter_ou_criar_aba(context, dominio="sei.sistemas.ro.gov.br", url_navegacao=URL_SEI)
    obter_ou_criar_aba(context, dominio="sigef.sefin.ro.gov.br", url_navegacao=URL_SIGEF)

    print("-" * 50)
    print("Entre com a sua conta no SEI e no SIGEF nesse Chrome agora")
    print("(se ainda não tiver entrado) e deixe as duas abas prontas.")
    print("=" * 50)
    input("Pressione Enter aqui depois de confirmar o login nos dois sistemas... ")


def garantir_chrome_pronto(estado: dict):
    """
    Garante que existe um Chrome de depuração aberto e conectado pra
    automação, guardando playwright/browser/context em `estado` (dict
    mutável, criado vazio em main() e reaproveitado a cada chamada) --
    e só pede a confirmação de login (preparar_sessao_login) na
    PRIMEIRA vez que conecta, ou de novo se o Chrome de depuração tiver
    sido fechado nesse meio tempo.

    Se o Chrome de depuração foi fechado (browser.is_connected() ==
    False), conectar_chrome() abre um Chrome novo automaticamente -- e
    como esse Chrome novo começa sem nenhuma aba aberta, o login
    também precisa ser refeito, por isso preparar_sessao_login() roda
    de novo nesse caso.

    Retorna o `context` pronto pra uso.
    """
    browser = estado.get("browser")
    if browser is not None and browser.is_connected():
        return estado["context"]

    if estado.get("playwright") is not None:
        # Chrome de depuração antigo caiu/foi fechado -- encerra essa
        # conexão do Playwright antes de abrir outra.
        try:
            estado["playwright"].stop()
        except Exception:
            pass
        print("\n⚠️  O Chrome de depuração foi fechado -- abrindo de novo.")

    playwright, browser, context = conectar_chrome()
    estado.update(playwright=playwright, browser=browser, context=context)

    preparar_sessao_login(context)

    return context


def executar_ciclo(context) -> None:
    """
    Executa o ciclo completo de regularização pra UM processo:

        SEI(1) -> CE -> NL -> PP -> OB -> Anexar Documento -> SEI(2)

    Ver o docstring do módulo para a visão geral de cada etapa. Chamada
    repetidamente por main(), uma vez por processo.
    """
    aba_sei, processo, dados = executar_sei1(context)
    lancamentos = dados["lancamentos"]

    print(f"\n{'=' * 50}\nCE (Valor Total {dados['valor_total']})\n{'=' * 50}")
    dados_ce = {**dados, "valor_padronizado": dados["valor_total_padronizado"]}
    ce, ce_reaproveitada = obter_ce(context, processo, dados_ce)

    if not ce_reaproveitada:
        # CE nova -- qualquer NL/PP/OB/anexo salvo de antes pertencia à
        # CE anterior e não vale mais pra essa. Limpa pra gerar tudo de
        # novo do zero (senão o "pular duplicado" de cada etapa ia pular
        # achando que já tinha sido feito nessa CE).
        for item in lancamentos:
            item.pop("nl", None)
            item.pop("pp", None)
            item.pop("ob", None)
            item.pop("anexo_baixado", None)
            item.pop("arquivos_anexar", None)

    print(f"\n{'=' * 50}\nNL -- {len(lancamentos)} lançamento(s)\n{'=' * 50}")
    lancamentos = executar_nl_lote(context, ce, lancamentos, dados)

    print(f"\n{'=' * 50}\nPP -- {len(lancamentos)} lançamento(s)\n{'=' * 50}")
    lancamentos = executar_pp_lote(context, ce, lancamentos, dados["conta_pp"], dados)

    print(f"\n{'=' * 50}\nOB -- {len(lancamentos)} lançamento(s)\n{'=' * 50}")
    lancamentos = gerar_obs(context, dados, lancamentos)

    print(f"\n{'=' * 50}\nANEXAR DOCUMENTO -- baixando relatórios do SIGEF\n{'=' * 50}")
    lancamentos = executar_anexar_lote(context, processo, lancamentos)

    print(f"\n{'=' * 50}\nSEI (2) -- anexando os documentos ao processo\n{'=' * 50}")
    executar_sei2(context, processo)

    print(f"\n{'=' * 50}\nRESUMO -- Processo {processo} | CE {ce}\n{'=' * 50}")
    for i, item in enumerate(lancamentos, start=1):
        concluido = bool(item.get("ob")) and bool(item.get("anexo_baixado"))
        status = "✅" if concluido else "⚠️ "
        print(
            f"{status} {i}) Valor {item['valor']} | NE {item['nota_de_empenho']} -- "
            f"NL {item.get('nl')} | PP {item.get('pp')} | OB {item.get('ob')} | "
            f"Anexado: {'sim' if item.get('anexo_baixado') else 'não'}"
        )


def main() -> None:
    """
    Ponto de entrada da automação.

    A cada volta do loop, garantir_chrome_pronto() garante o Chrome de
    depuração aberto e conectado -- abrindo um automaticamente se
    preciso, e pedindo a confirmação de login no SEI/SIGEF só na
    primeira vez (ou de novo, se o Chrome de depuração tiver sido
    fechado nesse meio tempo) -- e então executar_ciclo() roda pra um
    processo. Repete pro próximo processo até o usuário responder "N"
    quando perguntado se quer continuar, ou fechar o programa com
    Ctrl+C a qualquer momento.
    """
    estado_chrome: dict = {}
    try:
        while True:
            context = garantir_chrome_pronto(estado_chrome)

            executar_ciclo(context)

            print(f"\n{'=' * 50}")
            if not confirmar("🔁 Processar outro processo agora? (S/N): "):
                print("👋 Encerrando a automação. Até a próxima!")
                break
            reiniciar_sessao_para_novo_processo()
    except KeyboardInterrupt:
        print("\n\n⏹️  Automação interrompida pelo usuário (Ctrl+C).")
    finally:
        if estado_chrome.get("playwright") is not None:
            estado_chrome["playwright"].stop()


if __name__ == "__main__":
    main()
