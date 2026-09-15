"""
Orquestra o fluxo completo de regularização, na ordem:

    SEI(1) -> CE (1x, Valor Total) -> NL (em lote) -> PP (em lote) -> OB (1x por lançamento)

O SEI(1) roda uma vez só: abre o processo e coleta os dados
compartilhados (CNPJ/CPF, contas, escola etc.), o Valor Total da
parcela e a lista de lançamentos desse processo -- de 1 a 20 pares de
Valor + Nota de Empenho que somados dão o Valor Total (ver
coletar_lancamentos() em etapa_sei1.py).

A CE é gerada uma única vez, com o Valor Total (é a mesma Despesas]s
Certificada pra todos os lançamentos). A partir dela, as NLs de todos os
lançamentos são geradas em sequência sem recarregar a página
(executar_nl_lote), e o mesmo vale para as PPs (executar_pp_lote) --
recarregar a página a cada lançamento seria lento e desnecessário, já
que a CE é sempre a mesma. Só a OB roda uma vez por lançamento, usando a
PP e o valor que cada um gerou.

Se um lançamento não conseguir gerar sua NL/PP/OB, ele fica marcado
como falho no resumo final e o loop segue pro próximo -- uma falha não
derruba os demais.

As etapas "Baixar" (download/conversão do relatório da CE) e "SEI(2)"
já existem como módulos (etapa_baixar.py, etapa_sei2.py) mas ainda não
fazem parte deste fluxo -- rodam isoladas até serem integradas.
"""
from utils import carregar_sessao, confirmar, conectar_chrome, salvar_sessao
from etapa_sei1 import executar_sei1
from etapa_ce import executar_ce
from etapa_nl import executar_nl_lote
from etapa_pp import executar_pp_lote
from etapa_ob import executar_ob


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
    saber se pode confiar nas NL/PP/OB já salvas (mesma CE) ou se elas
    pertencem a uma CE antiga e precisam ser refeitas (ver main()).
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


def main() -> None:
    playwright, browser, context = conectar_chrome()
    try:
        input("Sua conta já foi aberta no SEI? (S/N) ")

        aba_sei, processo, dados = executar_sei1(context)
        lancamentos = dados["lancamentos"]

        print(f"\n{'=' * 50}\nCE (Valor Total {dados['valor_total']})\n{'=' * 50}")
        dados_ce = {**dados, "valor_padronizado": dados["valor_total_padronizado"]}
        ce, ce_reaproveitada = obter_ce(context, processo, dados_ce)

        if not ce_reaproveitada:
            # CE nova -- qualquer NL/PP/OB salva de antes pertencia à CE
            # anterior e não vale mais pra essa. Limpa pra gerar tudo de
            # novo do zero (senão o "pular duplicado" da NL/PP/OB ia
            # pular achando que já tinha sido feito nessa CE).
            for item in lancamentos:
                item.pop("nl", None)
                item.pop("pp", None)
                item.pop("ob", None)

        print(f"\n{'=' * 50}\nNL -- {len(lancamentos)} lançamento(s)\n{'=' * 50}")
        lancamentos = executar_nl_lote(context, ce, lancamentos, dados)

        print(f"\n{'=' * 50}\nPP -- {len(lancamentos)} lançamento(s)\n{'=' * 50}")
        lancamentos = executar_pp_lote(context, ce, lancamentos, dados["conta_pp"], dados)

        print(f"\n{'=' * 50}\nOB -- {len(lancamentos)} lançamento(s)\n{'=' * 50}")
        lancamentos = gerar_obs(context, dados, lancamentos)

        print(f"\n{'=' * 50}\nRESUMO -- CE {ce}\n{'=' * 50}")
        for i, item in enumerate(lancamentos, start=1):
            status = "✅" if item.get("ob") else "⚠️ "
            print(
                f"{status} {i}) Valor {item['valor']} | NE {item['nota_de_empenho']} -- "
                f"NL {item.get('nl')} | PP {item.get('pp')} | OB {item.get('ob')}"
            )
    finally:
        playwright.stop()


if __name__ == "__main__":
    main()
