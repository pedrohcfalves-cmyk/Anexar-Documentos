"""
Orquestra o fluxo completo de regularização, na ordem:

    SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)

Cada etapa alimenta a próxima com a variável que ela gera (CE alimenta
NL, NL alimenta PP, PP alimenta OB), além de todo mundo reaproveitar os
dados coletados no SEI(1). Hoje SEI(1), CE, NL e PP já estão
implementadas; OB e SEI(2) ainda serão implementadas e por enquanto são
apenas puladas (com aviso) para não travar o fluxo durante os testes —
quando uma etapa é pulada, a próxima recebe None no lugar do valor que
viria dela.
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

        # ===== NL (usa o CE gerado na Etapa CE) =====
        nl = None
        try:
            nl = executar_nl(context, ce, dados["valor_padronizado"], dados)
        except NotImplementedError as erro:
            print(f"⚠️  Pulando etapa NL: {erro}")

        # ===== PP (usa a NL e o CE, e a conta PP coletada no SEI(1)) =====
        pp = None
        try:
            pp = executar_pp(context, nl, ce, dados["conta_pp"], dados)
        except NotImplementedError as erro:
            print(f"⚠️  Pulando etapa PP: {erro}")

        # ===== OB (usa a PP gerada na Etapa PP, e a conta OB coletada no SEI(1)) =====
        ob = None
        try:
            ob = executar_ob(context, pp, dados["conta_ob"], dados)
        except NotImplementedError as erro:
            print(f"⚠️  Pulando etapa OB: {erro}")

        # ===== SEI (2) (anexa os documentos gerados de volta ao processo) =====
        try:
            executar_sei2(aba_sei, dados, arquivos_jpg)
        except NotImplementedError as erro:
            print(f"⚠️  Pulando etapa SEI(2): {erro}")

    finally:
        playwright.stop()


if __name__ == "__main__":
    main()
