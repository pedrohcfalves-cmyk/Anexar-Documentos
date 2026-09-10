"""
Este arquivo foi dividido em módulos menores, para facilitar testes e
organização enquanto as etapas que faltam (NL, PP, OB, SEI(2)) são
implementadas. O fluxo completo funciona nesta ordem:

    SEI(1) -> CE -> NL -> PP -> OB -> SEI(2)

Onde cada etapa agora mora no seu próprio arquivo:

    utils.py       -> funções e constantes compartilhadas (URLs, conectar
                       ao Chrome, conversão PDF->JPG, etc.)
    etapa_sei1.py  -> SEI (1): abrir/pesquisar o processo
    etapa_ce.py    -> CE: preencher a Despesa Certificada no SIGEF, obter
                       o número CE e gerar/salvar o JPG do relatório
    etapa_nl.py    -> NL: Liquidar Despesa Certificada (a implementar)
    etapa_pp.py    -> PP: Preparação de Pagamento (a implementar)
    etapa_ob.py    -> OB: Ordem Bancária (a implementar)
    etapa_sei2.py  -> SEI (2): anexar os documentos gerados de volta ao
                       processo do SEI (a implementar)
    main.py        -> orquestra o fluxo completo, chamando cada etapa
                       nessa ordem

Cada etapa_*.py também pode ser executada isoladamente (útil para testar
uma etapa por vez): basta rodar, por exemplo, "python etapa_sei1.py".

Este arquivo continua funcionando como antes (mesmo comando de sempre) e
só repassa a execução para main.py. A versão anterior, com tudo em um
arquivo só, foi preservada em AnexarDocumento.py.bak, caso precise
consultar.
"""
from main import main

if __name__ == "__main__":
    main()
