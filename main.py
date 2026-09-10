"""
Orquestra o fluxo completo de regularização, na ordem:

    SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)

Hoje só as etapas SEI(1) e CE estão implementadas; as demais (NL, PP, OB,
SEI(2)) ainda serão implementadas e por enquanto são apenas puladas (com
aviso) para não travar o fluxo durante os testes.
"""
from utils import conectar_chrome
from etapa_sei1 import executar_sei1
from etapa_ce import executar_ce
from etapa_nl import executar_nl
from etapa_pp import executar_pp
from etapa_ob import executar_ob
from etapa_sei2 import executar_sei2


def main() -> None:
    playwright, browser, context = conectar_chrome()
    try:
        input("Sua conta ja foi Aberta? (S/N) ")

        # ===== SEI (1) =====
        # Aqui já são coletados os dados (valor, CNPJ/CPF, contas etc.)
        # que serão reaproveitados em todas as etapas do SIGEF abaixo.
        aba_sei, processo, dados = executar_sei1(context)

        # ===== CE =====
        ce, arquivos_jpg = executar_ce(context, processo, dados)

        # ===== NL, PP, OB, SEI(2) - ainda a implementar =====
        etapas_restantes = (
            ("NL", executar_nl, (context, dados)),
            ("PP", executar_pp, (context, dados)),
            ("OB", executar_ob, (context, dados)),
            ("SEI(2)", executar_sei2, (aba_sei, dados, arquivos_jpg)),
        )
        for nome_etapa, funcao_etapa, argumentos in etapas_restantes:
            try:
                funcao_etapa(*argumentos)
            except NotImplementedError as erro:
                print(f"⚠️  Pulando etapa {nome_etapa}: {erro}")

    finally:
        playwright.stop()


if __name__ == "__main__":
    main()
