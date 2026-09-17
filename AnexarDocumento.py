"""
Script antigo/legado -- era a versão original, monolítica (tudo num
arquivo só, sem reaproveitar código), do fluxo que hoje já está
modularizado e testado nos arquivos etapa_*.py:

    etapa_sei1.py  -> abrir processo + coletar dados
    etapa_ce.py    -> gerar a CE
    etapa_nl.py    -> gerar as NLs
    etapa_pp.py    -> gerar as PPs
    etapa_ob.py    -> gerar as OBs
    etapa_baixar.py -> baixar o relatório da CE e converter pra JPG

tudo orquestrado por main.py. Esse arquivo não deve mais ser executado.

A lógica de BAIXAR o relatório e converter pra JPG que existia aqui foi
preservada -- está funcionando, isolada e testada, em etapa_baixar.py
(função executar_baixar()). Nada foi perdido.

A nova automação de "anexar documento" (usando a tela de Listar
Preparação de Pagamento do SIGEF, CdTransacao=177) está sendo
construída do zero em etapa_anexar.py.

Mantido só de referência histórica -- pode ser removido do projeto
quando quiser (git já tem o histórico de qualquer forma).
"""
