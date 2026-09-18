# Anexar Documentos — Automação SEI/SIGEF

Automação (Playwright, conectado a um Chrome real via CDP) do fluxo de
**regularização de parcelas** entre o SEI e o SIGEF da SEFIN-RO: abre o
processo no SEI, gera a Despesa Certificada (CE) e, para cada
lançamento (Valor + Nota de Empenho), gera a Nota de Liquidação (NL), a
Preparação de Pagamento (PP) e a Ordem Bancária (OB) no SIGEF — depois
baixa os relatórios de tudo isso e anexa de volta no processo do SEI.

> ⚠️ **Esta automação aponta pro SIGEF de PRODUÇÃO** (`sigef.sefin.ro.gov.br`)
> — tudo que ela gerar (CE, NL, PP, OB) vale de verdade, não é ambiente
> de teste. Ver [Ambiente: produção](#ambiente-produção) abaixo.

## O ciclo

```
Login (1x)  →  SEI (1)  →  CE  →  NL (lote)  →  PP (lote)  →  OB (lote)  →  Anexar Documento  →  SEI (2)
                  ↑                                                                                  │
                  └──────────────────────────── repete para o próximo processo ─────────────────────┘
```

| Etapa | Arquivo | O que faz |
|---|---|---|
| Login | `main.py` (`garantir_chrome_pronto` / `preparar_sessao_login`) | Abre o Chrome de depuração automaticamente (se ainda não estiver aberto), abre as abas do SEI e do SIGEF — sem nenhuma automação de preenchimento — e pede pra você confirmar que já entrou com sua conta nos dois. Roda só **uma vez**, ou de novo se esse Chrome for fechado no meio do uso. |
| SEI (1) | `etapa_sei1.py` | Abre/pesquisa o processo no SEI e coleta os dados do lote (CNPJ/CPF, contas, escola, parcela, mês, programa, Valor Total e a lista de lançamentos). |
| CE | `etapa_ce.py` | Preenche a Despesa Certificada no SIGEF com o Valor Total (uma vez por processo). |
| NL | `etapa_nl.py` | Gera a Nota de Liquidação de cada lançamento, vinculada à mesma CE. |
| PP | `etapa_pp.py` | Gera a Preparação de Pagamento de cada lançamento, a partir da sua NL. |
| OB | `etapa_ob.py` | Gera a Ordem Bancária de cada lançamento, a partir da sua PP. |
| Anexar Documento | `etapa_listar_baixar.py` | Baixa (em PDF, convertido para JPG) os relatórios de CE, OB, NL e PP de cada lançamento, direto do SIGEF, salvando na pasta do processo. |
| SEI (2) | `etapa_sei2.py` | Volta ao SEI, reabre o processo e inclui os JPGs baixados como documentos novos (CE, uma NL + uma PP por lançamento, e a OB), já com Nível de Acesso e Hipótese Legal preenchidos. |

`main.py` executa esse ciclo inteiro para **um processo** e, ao final,
pergunta se quer continuar com o próximo — o loop se repete até você
responder **N** ou fechar o programa (`Ctrl+C`). Uma falha em um
lançamento específico (NL/PP/OB/anexo) não interrompe os demais; ele
fica marcado como pendente no resumo e pode ser retomado numa próxima
execução (ver [Sessão salva](#sessão-salva-sessao_atualjson) abaixo).

Cada etapa também pode ser testada isoladamente, rodando o arquivo
`etapa_*.py` diretamente — o bloco `if __name__ == "__main__":` de cada
um pede só os dados daquela etapa (reaproveitando o que estiver salvo na
sessão), sem depender de rodar o fluxo inteiro de novo.

## Estrutura do projeto

```
Anexar Documentos/
├── main.py                    # orquestra o ciclo completo (ver acima)
├── utils.py                   # URLs, conexão com o Chrome, sessão, validações/formatação de valores
├── etapa_sei1.py
├── etapa_ce.py
├── etapa_nl.py
├── etapa_pp.py
├── etapa_ob.py
├── etapa_listar_baixar.py
├── etapa_sei2.py
├── abrir_chrome_automacao.bat # atalho manual opcional pro Chrome dedicado (porta 9222)
├── requirements.txt
├── legado/                    # versão antiga/monolítica, mantida só de referência histórica
├── sessao_atual.json          # gerado em tempo de execução (git-ignored)
└── <número do processo>/      # pasta criada por processo, com os JPGs baixados (git-ignored)
```

## Pré-requisitos

- Python 3.10+ (testado com 3.14)
- Google Chrome instalado em `C:\Program Files\Google\Chrome\Application\chrome.exe`
- Um ambiente virtual com as dependências do `requirements.txt`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Não é necessário rodar `playwright install`: a automação **não** abre um
navegador próprio do Playwright — ela se conecta, via CDP (protocolo de
depuração do Chrome), a um Chrome de verdade (ver próxima seção).

## Como rodar

1. **Rode a automação**:

```bash
.venv\Scripts\activate
python main.py
```

2. Se o Chrome dedicado (perfil próprio em `C:\ChromeAutomacao`, porta
   de depuração 9222) ainda não estiver aberto, o `main.py` abre ele
   sozinho automaticamente. Em seguida abre as abas do SEI e do SIGEF
   (só navega até elas — nenhum clique ou preenchimento automático
   ainda) e pausa, pedindo pra você **confirmar o login**: entre com sua
   conta no SEI e no SIGEF nessa janela (na primeira vez você vai
   precisar logar; depois disso o login fica salvo nesse perfil) e
   aperte Enter no terminal para continuar. Isso roda só uma vez por
   execução — só se repete se você fechar esse Chrome no meio do uso
   (a automação percebe e abre outro automaticamente).
3. Responda às perguntas no terminal (processo, CE, dados do lote,
   lançamentos etc.) — cada uma oferece o último valor salvo como
   padrão (aperte Enter para reaproveitar). Ao final de cada processo, a
   automação pergunta se você quer continuar com o próximo.

`abrir_chrome_automacao.bat` (2 cliques) continua funcionando como
atalho manual opcional — por exemplo, pra abrir o Chrome e já fazer
login antes de rodar `main.py`, sem esperar.

Para testar uma etapa isolada (sem rodar o fluxo inteiro):

```bash
python etapa_nl.py   # ou etapa_ce.py, etapa_pp.py, etapa_ob.py, etapa_listar_baixar.py, etapa_sei2.py...
```

Cada `etapa_*.py` também usa `conectar_chrome()` (`utils.py`), então
abre o Chrome dedicado sozinho se ele ainda não estiver aberto — mas,
diferente do `main.py`, não pede confirmação de login nem abre as abas
do SEI/SIGEF automaticamente; garanta que já entrou com sua conta antes
de testar uma etapa isolada.

## Sessão salva (`sessao_atual.json`)

Guarda os últimos valores usados (processo, dados do lote, CE, e cada
lançamento com sua NL/PP/OB/anexo) para não precisar redigitar tudo a
cada execução, e para retomar de onde parou se o script for fechado no
meio de um processo — nada que já tenha sido gerado com sucesso é
gerado de novo (duplicado). Ao terminar um processo e começar o
próximo, `main.py` limpa automaticamente os dados que pertencem só ao
processo concluído (processo, CE e lançamentos), mantendo os dados
reaproveitáveis (contas, escola, parcela etc.).

Esse arquivo tem dados reais (CNPJ, valores) e **não é versionado** (ver
`.gitignore`) — o mesmo vale para as pastas de processo geradas pelos
downloads.

## Ambiente: produção

Todas as URLs do SIGEF em `utils.py` (`URL_SIGEF`, `URL_SIGEF_NL`,
`URL_SIGEF_PP`, `URL_SIGEF_OB`, `URL_SIGEF_LISTAR_DESPESA_CERTIFICADA`,
`URL_SIGEF_LISTAR_PP`) apontam pro domínio de **produção**
(`sigef.sefin.ro.gov.br`, sem o "hom" de homologação) — tudo que a
automação gerar (CE, NL, PP, OB) é real.

Pra voltar a testar num ambiente seguro, sem afetar dados reais, troque
o domínio de volta pra homologação (`sigefhom.sefin.ro.gov.br`) nessas
constantes, em `utils.py`.

## Legado

`legado/AnexarDocumento.py` (e seu `.bak`) é a versão antiga e
monolítica do fluxo, anterior à modularização em `etapa_*.py`. Mantida
só como referência histórica — não é mais executada nem importada por
nada no projeto.
