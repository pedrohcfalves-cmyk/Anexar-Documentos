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
REM Uso: da um duplo-clique nesse arquivo ANTES de rodar qualquer
REM etapa_*.py (ou o main.py). Pode deixar seu Chrome normal aberto do
REM lado -- sao processos totalmente separados.

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeAutomacao"
