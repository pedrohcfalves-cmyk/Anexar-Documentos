@echo off
REM Abre um Chrome separado, isolado, so pra rodar a automacao SEI/SIGEF.
REM Esse Chrome fica com um perfil proprio (pasta C:\ChromeAutomacao),
REM sem nenhuma das suas abas do dia a dia (GitHub, planilhas, portal
REM etc.) -- e' por isso que ele conecta rapido: o Playwright nao
REM precisa disputar recursos com um monte de outras abas pesadas.
REM
REM Na primeira vez voce vai precisar logar de novo no SEI e no SIGEF
REM nessa janela. Depois disso o login fica salvo nessa pasta e voce
REM nao precisa refazer.
REM
REM OPCIONAL: o main.py agora abre esse mesmo Chrome sozinho, automa-
REM ticamente, se ele ainda nao estiver aberto quando voce rodar
REM "python main.py" -- entao normalmente nao precisa mais rodar este
REM arquivo antes. Ele continua aqui como atalho manual (por exemplo,
REM pra abrir o Chrome e logar ANTES de rodar o main.py, sem esperar).
REM
REM Uso: da um duplo-clique nesse arquivo ANTES de rodar qualquer
REM etapa_*.py (ou o main.py). Pode deixar seu Chrome normal aberto do
REM lado -- sao processos totalmente separados.

REM --remote-allow-origins=* evita que o Chrome aceite a conexao mas
REM trave sem responder ao protocolo (erro "<ws connected>" seguido de
REM timeout) -- protecao de origem que o Chrome passou a aplicar no
REM DevTools Protocol nas versoes mais recentes.
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeAutomacao" --remote-allow-origins=*
