"""
Etapa SEI (2): depois de baixar os relatórios no SIGEF (Etapa Anexar
Documento -- CE, OB, NL e PP em JPG, salvos na pasta do processo), volta
pro SEI e reabre o processo, deixando pronta a árvore de pastas -- mesmo
jeito que a Etapa SEI (1) deixou no começo do fluxo.

Ainda EM CONSTRUÇÃO -- por enquanto faz: voltar pro SEI, reabrir o
processo, reabrir o processo se estiver arquivado, incluir um documento
do tipo "Despesa Certificada", preencher o Nível de Acesso/Hipótese
Legal e salvar. Falta ainda: fazer o upload do arquivo (JPG) dentro
desse documento recém-criado.

A página do SEI tem vários iframes aninhados, e o mesmo botão pode estar
em lugares diferentes dependendo da tela/momento (confirmado ao vivo:
"Reabrir Processo" e "Incluir Documento" às vezes não aparecem em
nenhum dos lugares óbvios) -- por isso _procurar_lugar() abaixo procura
cada elemento em uma LISTA de lugares candidatos (aba_sei direto, ou um
frame pelo nome, que aba_sei.frame(name=...) acha em qualquer nível de
aninhamento) em vez de fixar um seletor único.
"""
import glob
import os
import tempfile
import time

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from utils import (
    PASTA_BASE,
    URL_SEI,
    carregar_sessao,
    nome_pasta_valido,
    obter_ou_criar_aba,
    perguntar_ou_reusar,
)
from etapa_sei1 import abrir_processo_sei

# Lugares candidatos pra procurar os botões/links da tela do processo,
# na ordem em que vale a pena tentar. None = aba_sei direto; qualquer
# outro valor é o nome (name=) de um frame.
#
# Ordem otimizada com base no que já foi confirmado ao vivo: aba_sei
# direto NUNCA foi onde "Reabrir Processo", "Incluir Documento" ou
# "Despesa Certificada" apareceram -- só os frames. Por isso os frames
# vêm primeiro (ifrVisualizacao é o mais comum) e aba_sei direto fica
# por último, só como fallback.
CANDIDATOS_FRAMES = ("ifrVisualizacao", "ifrConteudoVisualizacao", "ifrArvore", "ifrPasta", None)


def _procurar_lugar(aba_sei, candidatos, seletor: str, timeout: int = 1500):
    """
    Procura `seletor` em cada um dos `candidatos`, na ordem, com um
    timeout curto em cada um (pra não demorar muito no total mesmo
    tentando vários lugares).

    Cada candidato pode ser: None (aba_sei direto), uma string (nome de
    um frame, resolvido via aba_sei.frame(name=...)), ou já um objeto
    Page/Frame pronto (útil pra tentar primeiro um lugar que já foi
    encontrado antes, sem precisar procurar o nome de novo).

    Retorna (lugar, locator, nome) assim que achar visível em algum
    deles -- `lugar` é o Page ou Frame onde achou (pra continuar
    procurando os PRÓXIMOS elementos da mesma tela nele) e `locator` já
    é o locator pronto pra usar (clicar, etc). Retorna (None, None,
    None) se não achar em nenhum candidato.

    timeout default reduzido de 5000ms pra 1500ms: o elemento já deve
    estar no DOM quando a página termina de carregar, então não vale a
    pena esperar muito em cada candidato errado -- isso é o que mais
    pesava quando um botão (ex: "Reabrir Processo") não aparecia em
    lugar nenhum e o código tinha que esgotar o timeout em TODOS os
    candidatos antes de desistir.

    Também tolera um frame "desconectar" no meio da espera (erro
    "Frame was detached") -- acontece quando o SEI ainda está
    recarregando um iframe (ex: logo depois de expandir a árvore) bem
    na hora que a busca chega nele. Nesse caso, se o candidato foi
    passado como nome (ou None), tenta resolver o frame DE NOVO (pega
    uma referência nova, já que a antiga morreu) e tenta mais uma vez,
    em vez de desistir desse candidato à toa.
    """
    for candidato in candidatos:
        # Só vale re-tentar quando dá pra resolver uma referência NOVA
        # do frame (nome ou None/aba_sei) -- um candidato já resolvido
        # de antes (objeto Page/Frame) não tem como ser "re-obtido" se
        # ele mesmo desconectou.
        tentativas = 2 if (candidato is None or isinstance(candidato, str)) else 1
        for tentativa in range(tentativas):
            if candidato is None:
                lugar = aba_sei
            elif isinstance(candidato, str):
                lugar = aba_sei.frame(name=candidato)
            else:
                lugar = candidato  # já é um Page/Frame encontrado antes
            if lugar is None:
                break
            locator = lugar.locator(seletor)
            try:
                locator.first.wait_for(state="visible", timeout=timeout)
                return lugar, locator, (getattr(lugar, "name", None) or "aba_sei")
            except PlaywrightTimeoutError:
                break
            except PlaywrightError as erro:
                if tentativa + 1 < tentativas and "detach" in str(erro).lower():
                    continue  # frame sumiu no meio do caminho -- tenta de novo com referência nova
                break
    return None, None, None


def _aguardar_rede(pagina, timeout: int = 1200):
    """
    Espera a rede ficar ociosa (`networkidle`), mas com timeout curto e
    sem propagar erro se não conseguir -- em algumas telas do SEI tem
    algo (ex: polling/refresh) que nunca deixa a rede totalmente
    ociosa, e esperar o timeout padrão (30s) nesses casos só trava a
    automação à toa. O `_procurar_lugar()` logo depois já garante que o
    elemento certo apareceu antes de continuar, então essa espera aqui
    é só uma cortesia pra dar tempo da página assentar -- não precisa
    ser garantida.

    Descoberta ao vivo (a pedido do usuário, otimizando a velocidade
    geral do fluxo): esse timeout era de 3000ms, e como várias telas do
    SEI NUNCA ficam realmente ociosas (o polling/refresh mencionado
    acima), essa função tava esperando o timeout INTEIRO toda vez que
    isso acontecia -- e ela é chamada várias vezes ao longo do fluxo.
    Reduzido pra 1200ms: continua dando um tempo curto pra página
    assentar quando a rede realmente fica ociosa rápido (caso comum),
    mas para de torrar segundos inteiros nas telas que nunca ficam.
    """
    try:
        pagina.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass


def _encontrar_frame_editor(pagina_editor, timeout: int = 5000):
    """
    Espera o iframe do editor de texto (CKEditor) do SEI montar e devolve
    o Frame certo -- aquele que tem o <body contenteditable="true"> onde
    o texto do documento é digitado. O editor pode demorar um pouco pra
    montar o iframe depois da página carregar, por isso fica tentando em
    ciclos curtos até o timeout total, em vez de checar só uma vez.

    Caminho já confirmado (HTML completo dos dois documentos, comparado
    ao vivo pelo usuário): nessa janela só o frame do "Corpo do Texto"
    tem body[contenteditable="true"] -- o do "Cabeçalho" (e qualquer
    outra seção fixa) vem com contenteditable="false". Por isso pega
    direto o PRIMEIRO frame com corpo editável, sem tentar casar antes
    pelo texto do placeholder padrão ("Digite aqui o texto...") como
    fazia antes.
    Achado ao vivo (causa de lentidão): aquela comparação usava texto
    EXATO (`text="Digite aqui o texto"`, sem reticências) contra o
    placeholder de verdade, que pode não bater 100% -- nesse caso a
    função esperava os 15000ms INTEIROS antes de desistir e cair no
    "candidato alternativo", TODA vez que essa função rodava (bem antes
    do Ctrl+A/Delete), o que parecia (e de fato era) uma trava grande
    logo no começo de "apagar os dados". Timeout também reduzido de
    15000ms pra 5000ms -- suficiente de sobra pro iframe montar, sem
    deixar uma janela grande de espera desnecessária num caso de erro
    de verdade.

    Retorna None se não achar nenhum frame com corpo editável dentro do
    timeout.
    """
    prazo = time.monotonic() + timeout / 1000
    while time.monotonic() < prazo:
        for frame in pagina_editor.frames:
            try:
                if frame.locator('body[contenteditable="true"]').count() > 0:
                    return frame
            except Exception:
                continue
        pagina_editor.wait_for_timeout(100)
    return None


def _localizar_arquivos_ce(processo: str, pasta_base: str = PASTA_BASE) -> list[str]:
    """
    Procura o(s) arquivo(s) JPG da Despesa Certificada (CE) já baixados
    antes pela Etapa Anexar Documento, na pasta do processo (mesmo
    esquema de pasta usado lá: pasta_base/nome_pasta_valido(processo)).

    Só pega arquivos que começam com "Despesa Certificada" -- nunca a
    NL, a PP ou a OB, que ficam salvas na MESMA pasta mas com nomes
    diferentes (ver abrir_e_baixar() em etapa_anexar.py).

    Se o relatório da CE tiver mais de 1 página, tem mais de 1 arquivo
    (ex: "Despesa Certificada_1.jpg", "Despesa Certificada_2.jpg" --
    ver pdf_para_jpg() em utils.py) -- devolve todos, em ordem.
    """
    pasta_processo = os.path.join(pasta_base, nome_pasta_valido(processo))
    padrao = os.path.join(pasta_processo, "Despesa Certificada*.jpg")
    return sorted(glob.glob(padrao))


def _tipo_mime_arquivo(caminho_arquivo: str) -> str:
    """Chuta o tipo MIME pela extensão -- só os tipos que aparecem neste projeto (JPG)."""
    if caminho_arquivo.lower().endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if caminho_arquivo.lower().endswith(".png"):
        return "image/png"
    return "application/octet-stream"


def _preparar_imagem_para_insercao(caminho_arquivo: str, limite_bytes_arquivo: int = 45000) -> str:
    """
    Reduz a imagem (resolução e/ou qualidade JPEG) até ela caber com
    folga num limite seguro de tamanho, ANTES de ser inserida no editor
    como base64.

    Descoberta ao vivo (comparando o tamanho do arquivo original --
    "Despesa Certificada.jpg" com 369.413 bytes -- com o HTML que o
    botão "Salvar" de fato manda pro servidor -- 493.300 caracteres,
    quase exatamente o tamanho da imagem em base64): o servidor RESPONDE
    "OK 2" (sucesso, sem erro nenhum) mas, ao recarregar a página, a
    imagem simplesmente não está mais no documento. Essa é a assinatura
    clássica de um limite de tamanho no armazenamento do lado do
    servidor (por exemplo, uma coluna TEXT do MySQL, que trunca
    SILENCIOSAMENTE em 65.535 bytes sem lançar erro nenhum) -- o pedido
    "dá certo" mas o conteúdo salvo sai cortado, e uma imagem de ~493KB
    sozinha já estoura esse tipo de limite várias vezes.

    Por isso, reduz a imagem até o ARQUIVO (antes de virar base64) ficar
    abaixo de `limite_bytes_arquivo` (45.000 bytes por padrão -- vira
    ~60.000 bytes em base64, com boa folga pra caber junto com o resto
    do HTML do documento dentro de 64KB).

    NUNCA modifica o arquivo original -- devolve o caminho de uma cópia
    reduzida num arquivo temporário (ou o caminho original sem nenhuma
    mudança, se ele já estiver abaixo do limite).
    """
    tamanho_original = os.path.getsize(caminho_arquivo)
    if tamanho_original <= limite_bytes_arquivo:
        return caminho_arquivo

    try:
        from PIL import Image
    except ImportError:
        raise SystemExit(
            f"\n⚠️  A imagem '{os.path.basename(caminho_arquivo)}' tem "
            f"{tamanho_original} bytes -- grande demais pra ser inserida "
            "como base64 sem estourar o limite de tamanho do documento "
            "no SEI (confirmado ao vivo: o servidor responde sucesso mas "
            "descarta o conteúdo em silêncio quando o documento fica "
            "grande demais). Preciso reduzir essa imagem antes de "
            "inserir, mas isso requer a biblioteca Pillow, que não está "
            "instalada nesse ambiente. Roda `pip install Pillow` no "
            "mesmo .venv usado aqui e tenta de novo.\n"
        )

    imagem = Image.open(caminho_arquivo)
    if imagem.mode not in ("RGB", "L"):
        imagem = imagem.convert("RGB")

    nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    caminho_reduzido = os.path.join(tempfile.gettempdir(), f"{nome_base}_reduzida.jpg")

    largura, altura = imagem.size
    qualidade = 85
    tamanho_atual = tamanho_original

    for _tentativa in range(12):
        imagem_redimensionada = imagem.resize((max(1, largura), max(1, altura)), Image.LANCZOS)
        imagem_redimensionada.save(caminho_reduzido, format="JPEG", quality=qualidade, optimize=True)
        tamanho_atual = os.path.getsize(caminho_reduzido)

        if tamanho_atual <= limite_bytes_arquivo:
            print(
                f"Imagem da CE reduzida de {tamanho_original} para "
                f"{tamanho_atual} bytes ({largura}x{altura}, qualidade "
                f"{qualidade}) pra caber com folga no limite de tamanho "
                "do documento no SEI."
            )
            return caminho_reduzido

        # Reduz mais: primeiro baixa a qualidade JPEG; quando ela já
        # estiver bem baixa, passa a reduzir a resolução também.
        if qualidade > 40:
            qualidade -= 10
        else:
            largura = int(largura * 0.85)
            altura = int(altura * 0.85)

    raise SystemExit(
        f"\n⚠️  Não consegui reduzir '{os.path.basename(caminho_arquivo)}' "
        f"(originalmente {tamanho_original} bytes) pra menos de "
        f"{limite_bytes_arquivo} bytes mesmo depois de várias tentativas "
        f"(última: {tamanho_atual} bytes, {largura}x{altura}, qualidade "
        f"{qualidade}). Me avisa -- talvez esse limite precise ser "
        "diferente pra esse tipo de imagem.\n"
    )


def _abrir_dialogo_imagem(pagina_editor, frame_editor=None, corpo=None, timeout: int = 5000):
    """
    Abre o diálogo "Imagem" (plugin base64image do CKEditor) na
    instância CERTA -- a que corresponde a `frame_editor` (o corpo do
    texto) -- direto pela API do CKEditor (`editor.execCommand`), em
    vez de clicar num `<a>` da barra de ferramentas.

    Descoberta ao vivo confirmada pelo usuário (HTML completo dos dois
    documentos, lado a lado): essa janela tem VÁRIAS instâncias do
    CKEditor na mesma tela -- uma por seção do documento (Cabeçalho,
    Corpo do Texto, etc.), cada seção no seu próprio iframe
    "about:srcdoc". A do Cabeçalho tem `<body contenteditable="false">`
    (nem é editável de verdade) mas MESMO ASSIM tem sua própria barra
    de ferramentas/botão "Imagem" -- e é justamente pra lá que a imagem
    estava indo, mesmo depois de focar certinho a instância do corpo:
    clicar num `<a>` da barra de ferramentas depende de qual botão o
    Playwright encontra/considera clicável no DOM, o que se mostrou
    pouco confiável com várias barras na mesma tela (mais de uma
    tentativa anterior já esbarrou nisso: botão errado, botão
    "invisível" mesmo habilitado, etc.).

    Chamar `editor.execCommand('base64image')` direto na instância que
    já identificamos como a do corpo evita esse problema por completo:
    o diálogo abre JÁ amarrado a essa instância específica, não importa
    qual `<a>` estaria visualmente associado a ela.

    Retorna o Locator do diálogo já visível. Levanta SystemExit com
    diagnóstico se não achar a instância certa, o comando não existir,
    ou o diálogo não abrir.
    """
    if corpo is not None:
        corpo.click()

    # Descoberta ao vivo (erro real): esses iframes "about:srcdoc" NÃO
    # têm name/id nenhum (frame.name veio '' -- string vazia), então
    # comparar por name/id sempre "batia" com qualquer coisa e acabava
    # usando a PRIMEIRA instância da lista, não necessariamente a do
    # corpo. Em vez de name/id, pega o elemento <iframe> de VERDADE
    # (mesmo nó do DOM) que envolve `frame_editor` -- via
    # `frame_element()`, que devolve o handle desse <iframe> já no
    # contexto do documento PAI (a própria pagina_editor, já que esses
    # iframes são filhos diretos dela) -- e compara por IGUALDADE DE
    # REFERÊNCIA (===) dentro do próprio navegador, o que funciona
    # não importa se o elemento tem name/id ou não.
    iframe_alvo = None
    if frame_editor is not None:
        try:
            iframe_alvo = frame_editor.frame_element()
        except Exception as erro:
            print(f"\n⚠️  Aviso: não consegui pegar o elemento <iframe> de frame_editor: {erro}")

    resultado = pagina_editor.evaluate(
        """(iframeAlvo) => {
            if (typeof CKEDITOR === 'undefined') return {erro: 'CKEDITOR undefined'};
            const nomes = Object.keys(CKEDITOR.instances || {});
            for (const nome of nomes) {
                try {
                    const editor = CKEDITOR.instances[nome];
                    if (iframeAlvo) {
                        const janelaNativa = editor.window && editor.window.$;
                        const elementoIframe = janelaNativa ? janelaNativa.frameElement : null;
                        if (elementoIframe !== iframeAlvo) continue;
                    }
                    if (editor.readOnly) {
                        editor.setReadOnly(false);
                    }
                    if (editor.filter) {
                        editor.filter.allowedContent = true;
                    }
                    if (editor.config) {
                        editor.config.allowedContent = true;
                    }
                    editor.focus();

                    // Não confia no nome "base64image" -- acha o
                    // comando de verdade procurando por algo com
                    // "base64" ou "image" no nome, entre os comandos
                    // REGISTRADOS nessa instância (o nome exato do
                    // comando pode não bater com a classe CSS do
                    // botão).
                    const chavesComandos = Object.keys(editor.commands || {});
                    let nomeComando = chavesComandos.find((k) => /base64/i.test(k));
                    if (!nomeComando) {
                        nomeComando = chavesComandos.find((k) => /image/i.test(k));
                    }
                    if (!nomeComando) {
                        return {
                            erro: 'nenhum comando parecido com base64/image encontrado',
                            comandosDisponiveis: chavesComandos,
                            nome: nome,
                        };
                    }
                    const sucesso = editor.execCommand(nomeComando);
                    if (!sucesso) {
                        return {
                            erro: `execCommand(${nomeComando}) retornou false`,
                            comandosDisponiveis: chavesComandos,
                            nome: nome,
                        };
                    }
                    return {ok: true, nome: nome, comando: nomeComando};
                } catch (erro) {
                    return {erro: String(erro), nome: nome};
                }
            }
            return {erro: 'nenhuma instância do CKEDITOR bate com o iframe alvo', todasInstancias: nomes};
        }""",
        iframe_alvo,
    )

    if not resultado or not resultado.get("ok"):
        raise SystemExit(
            "\n⚠️  Não consegui abrir o diálogo 'Imagem' pela API do "
            f"CKEditor. Detalhe: {resultado!r}\n"
        )

    print(f"Diálogo 'Imagem' aberto via editor.execCommand({resultado.get('comando')!r}) na instância {resultado.get('nome')!r}.")

    # Usa ":visible" (extensão do Playwright) em vez de só ".first" --
    # o CKEditor pode deixar diálogos antigos/fechados ainda no DOM
    # (escondidos), e ".first" pegaria o PRIMEIRO em ordem no DOM, não
    # necessariamente o que está de fato visível na tela agora.
    dialogo = pagina_editor.locator(".cke_dialog:visible").first
    try:
        dialogo.wait_for(state="visible", timeout=timeout)
    except PlaywrightTimeoutError:
        raise SystemExit(
            f"\n⚠️  Rodei editor.execCommand({resultado.get('comando')!r}) na "
            f"instância {resultado.get('nome')!r} mas nenhum diálogo "
            f"(.cke_dialog) visível apareceu em até {timeout}ms.\n"
        )
    return dialogo


def _preencher_e_confirmar_dialogo_imagem(
    pagina_editor, dialogo, caminho_arquivo: str, timeout: int = 5000
) -> None:
    """
    Preenche o campo de arquivo do diálogo "Imagem" do CKEditor (plugin
    base64image) com `caminho_arquivo` e clica em "OK" pra confirmar a
    inserção.

    Descoberta confirmada ao vivo (HTML completo do diálogo, enviado pelo
    usuário): o campo de arquivo NÃO é um <input> direto no DOM da
    página -- ele fica dentro de um
    <iframe class="cke_dialog_ui_input_file"> (padrão legado do CKEditor4
    pra isolar esse campo num documento próprio). É por isso que um
    `dialogo.locator("input")` direto sempre achava 0 elementos: a busca
    não atravessa a fronteira do iframe sozinha. Usa `frame_locator()`
    pra entrar nesse iframe antes de procurar o input -- o atributo
    `name="filArquivo"` sobrevive dentro dele (confirmado por inspeção
    manual do usuário: <input ... type="file" name="filArquivo" ...>).
    """
    campo_arquivo = pagina_editor.frame_locator(
        "iframe.cke_dialog_ui_input_file"
    ).locator('input[name="filArquivo"]')

    # Testado e descartado -- os TRÊS jeitos deram resultado idêntico ou
    # pior, provando que a forma de entregar o arquivo pro input NUNCA
    # foi o problema:
    #   1) `set_input_files()` direto;
    #   2) `expect_file_chooser()` (intercepta o evento nativo sem abrir
    #      janela nenhuma) -- deu o MESMO POST byte a byte que o (1);
    #   3) clicar sem interceptar, deixando o Explorador do Windows
    #      abrir DE VERDADE, e digitar o caminho -- confirmado ao vivo
    #      que a janela nativa realmente abre (é um Chrome real
    #      conectado por CDP), mas os comandos de teclado do Playwright
    #      NÃO alcançam essa janela nativa (só funcionam dentro da
    #      página do Chrome) -- resultado: nada é digitado, nenhum
    #      arquivo é escolhido. Esse caminho não dá pra automatizar.
    # Volta pro (1), que é o único 100% confiável por script.
    ultimo_erro = None
    for tentativa in range(3):
        try:
            campo_arquivo.set_input_files(caminho_arquivo, timeout=timeout)
            ultimo_erro = None
            break
        except PlaywrightTimeoutError as erro:
            ultimo_erro = erro
            dialogo.page.wait_for_timeout(250)

    if ultimo_erro is not None:
        # Diagnóstico: confirma se o iframe existe na página, se está
        # visível, e o que tem dentro dele (contagem de inputs e o HTML
        # do <body> interno, já que é same-origin e deveria ser
        # acessível).
        seletor_iframe = "iframe.cke_dialog_ui_input_file"
        qtd_iframes = pagina_editor.locator(seletor_iframe).count()
        print(f"\nTotal de <iframe class='cke_dialog_ui_input_file'> na página: {qtd_iframes}")
        for i in range(qtd_iframes):
            elemento_iframe = pagina_editor.locator(seletor_iframe).nth(i)
            try:
                print(f"  [{i}] visível={elemento_iframe.is_visible()}")
            except Exception as erro_diag:
                print(f"  [{i}] (erro ao inspecionar elemento <iframe>: {erro_diag})")
            try:
                fl = pagina_editor.frame_locator(seletor_iframe).nth(i)
                qtd_campo = fl.locator('input[name="filArquivo"]').count()
                qtd_inputs = fl.locator("input").count()
                print(
                    f"  [{i}] dentro do iframe: inputs(name=filArquivo)={qtd_campo} "
                    f"total_inputs={qtd_inputs}"
                )
                print(f"  [{i}] HTML do <body> interno:\n{fl.locator('body').first.inner_html()}")
            except Exception as erro_diag:
                print(f"  [{i}] (erro ao inspecionar conteúdo do iframe: {erro_diag})")
        raise SystemExit(
            "\n⚠️  Não encontrei o campo input[name=\"filArquivo\"] dentro do "
            f"<iframe class=\"cke_dialog_ui_input_file\"> em até {timeout}ms "
            "(tentei 3 vezes). Olha o diagnóstico acima (quantos iframes "
            "existem e o que tem dentro deles) e me diz o que aparece.\n"
        )

    botao_ok = dialogo.locator(
        '.cke_dialog_ui_button_ok, .cke_dialog_ui_button:has-text("OK")'
    ).first
    botao_ok.click()

    # O plugin base64image lê o arquivo com FileReader (assíncrono) e
    # insere a imagem convertida em base64 -- em vez de um sleep fixo
    # (que pode ser curto demais pra arquivos maiores/máquina mais
    # lenta), espera o diálogo fechar (sinal de que o onOk do plugin
    # rodou) e dá uma folga extra pro FileReader/insertHtml terminarem.
    fechou = True
    try:
        dialogo.wait_for(state="hidden", timeout=5000)
    except PlaywrightTimeoutError:
        fechou = False
    pagina_editor.wait_for_timeout(200)

    if not fechou:
        print(
            "\n⚠️  Aviso: cliquei em OK mas o diálogo 'Imagem' continua "
            "visível 5s depois -- pode ser que o clique não tenha "
            "registrado no botão certo, ou o plugin não fechou o diálogo "
            "(ex: alguma validação interna falhou)."
        )


def _clicar_salvar_editor(pagina_editor, frame_editor=None, timeout: int = 5000) -> None:
    """
    Clica no botão "Salvar" (Ctrl+Alt+S) da barra de ferramentas do
    CKEditor, pra gravar o documento (imagem da CE já inserida) antes de
    voltar pra aba do SEI.

    Usa a classe estável do próprio plugin (`cke_button__save`) -- NUNCA
    o id (`cke_27`, visto numa sessão de teste), já que o CKEditor gera
    esses ids de novo (mudando) a cada carregamento da página, então um
    id fixo quebraria assim que essa mesma tela abrisse de novo com
    outro id.

    Confirmado ao vivo pelo usuário (numa tentativa BEM mais antiga,
    antes de existir o casamento de instância por identidade de DOM que
    usamos hoje pro botão "Imagem"): chamar a API do CKEditor
    (editor.focus() + seleção forçada, em loop por TODAS as instâncias)
    fazia o clique "ir" mas o SEI não reconhecia que salvou. Por isso a
    ação de salvar em si continua sendo um clique de VERDADE no `<a>` da
    barra de ferramentas (não um editor.execCommand solto).

    O que MUDOU agora: essa janela tem várias instâncias do CKEditor na
    mesma tela (uma por seção do documento -- Cabeçalho, Corpo do Texto,
    etc.), cada uma com sua PRÓPRIA barra de ferramentas/botão "Salvar".
    Erro visto ao vivo (idêntico ao que já tínhamos resolvido pro botão
    "Imagem"): o Playwright reportava o `<a class="cke_button__save">`
    como "hidden" mesmo com `aria-disabled="false"` -- porque, depois de
    fechar o diálogo "Imagem", o foco pode não estar mais na instância do
    corpo do texto, deixando a barra de ferramentas DELA (a que tem o
    "Salvar" que realmente importa) escondida. Sem `:visible` no
    seletor, `.first` sempre travava no MESMO `<a>` (o primeiro em ordem
    no DOM, não necessariamente visível) -- daí o "14 × locator resolved
    to hidden <a id=\"cke_27\" ...>" repetido.

    Fix (mesma ideia do botão "Imagem", em _abrir_dialogo_imagem): antes
    de procurar o botão, foca (só) a instância do CKEDITOR que bate --
    por igualdade de referência do elemento <iframe> -- com
    `frame_editor` (o corpo do texto, já identificado antes por quem
    chamou, sem precisar redescobrir do zero). Isso reativa a barra de
    ferramentas certa. Só DEPOIS disso procura o `<a>` "Salvar" -- e usa
    `:visible` direto no seletor (não só `.first` sem filtro), pra o
    Playwright reconsultar e aceitar qualquer botão que já esteja visível
    agora, em vez de ficar preso ao primeiro em ordem no DOM.
    """
    pagina_editor.bring_to_front()

    # Reidentifica o frame do corpo do texto só se quem chamou não
    # passou um já conhecido (fallback de segurança -- ver risco descrito
    # no retorno de _limpar_e_inserir_imagem_ce sobre o placeholder já
    # ter sumido a essa altura).
    if frame_editor is None:
        frame_editor = _encontrar_frame_editor(pagina_editor)

    if frame_editor is not None:
        try:
            iframe_alvo = frame_editor.frame_element()
        except Exception as erro:
            iframe_alvo = None
            print(
                "\n⚠️  Aviso: não consegui pegar o elemento <iframe> de "
                f"frame_editor pra focar a instância certa antes de salvar: {erro}"
            )

        resultado_foco = pagina_editor.evaluate(
            """(iframeAlvo) => {
                if (typeof CKEDITOR === 'undefined') return {erro: 'CKEDITOR undefined'};
                const nomes = Object.keys(CKEDITOR.instances || {});
                for (const nome of nomes) {
                    try {
                        const editor = CKEDITOR.instances[nome];
                        if (iframeAlvo) {
                            const janelaNativa = editor.window && editor.window.$;
                            const elementoIframe = janelaNativa ? janelaNativa.frameElement : null;
                            if (elementoIframe !== iframeAlvo) continue;
                        }
                        editor.focus();
                        return {ok: true, nome: nome};
                    } catch (erro) {
                        return {erro: String(erro), nome: nome};
                    }
                }
                return {erro: 'nenhuma instância do CKEDITOR bate com o iframe alvo', todasInstancias: nomes};
            }""",
            iframe_alvo,
        )

        if resultado_foco and resultado_foco.get("ok"):
            print(
                f"Foquei a instância {resultado_foco.get('nome')!r} do "
                "CKEditor (corpo do texto) antes de procurar o botão 'Salvar'."
            )
        else:
            print(
                "\n⚠️  Aviso: não consegui focar a instância certa do "
                f"CKEditor antes de salvar. Detalhe: {resultado_foco!r}"
            )
        pagina_editor.wait_for_timeout(150)
    else:
        print(
            "\n⚠️  Aviso: não achei o frame do corpo do texto pra focar a "
            "instância certa antes de salvar -- vou tentar clicar em "
            "'Salvar' mesmo assim."
        )

    botao_salvar = pagina_editor.locator(
        'a.cke_button__save:visible, a[title^="Salvar"]:visible'
    ).first

    try:
        botao_salvar.wait_for(state="visible", timeout=timeout)
    except PlaywrightTimeoutError:
        print("\nBotões .cke_button na barra de ferramentas do editor:")
        botoes = pagina_editor.locator("a.cke_button")
        for i in range(botoes.count()):
            try:
                print(
                    f"  - title={botoes.nth(i).get_attribute('title')!r} "
                    f"classe={botoes.nth(i).get_attribute('class')!r} "
                    f"visível={botoes.nth(i).is_visible()}"
                )
            except Exception as erro_diag:
                print(f"  - (erro ao inspecionar botão {i}: {erro_diag})")
        raise SystemExit(
            "\n⚠️  Não encontrei nenhum botão 'Salvar' VISÍVEL "
            "(a.cke_button__save) na barra de ferramentas do editor em "
            f"até {timeout}ms, mesmo depois de focar a instância do corpo "
            "do texto. Olha a lista de botões impressa acima (e se algum "
            "está visível=True) e me diz qual é o certo.\n"
        )

    # Caminho já confirmado -- não precisa mais capturar/decodificar
    # requisições de rede pra provar que a imagem sai no POST; só clica,
    # dá uma folga curta pra rede assentar e segue.
    botao_salvar.click()
    _aguardar_rede(pagina_editor)

    print("Cliquei em 'Salvar' no editor do documento.")


def _limpar_e_inserir_imagem_ce(
    pagina_editor, processo: str, pasta_base: str = PASTA_BASE
):
    """
    No editor de texto do documento "Despesa Certificada" recém-criado:
    apaga todo o conteúdo padrão do corpo do texto (o "Digite aqui o
    texto...", a data e o nome do assinante que o SEI já preenche) e
    insere a(s) imagem(ns) da CE -- baixada(s) antes na Etapa Anexar
    Documento e salva(s) na pasta do MESMO processo -- pra dentro do
    campo de texto, via diálogo "Imagem" do CKEditor.

    Esse trecho é especificamente do documento da Despesa Certificada,
    então só usa arquivo(s) "Despesa Certificada*.jpg" -- nunca NL, PP
    ou OB, mesmo que estejam salvos na mesma pasta.

    Sequência de cliques EXATA pedida pelo usuário (depois de várias
    tentativas via API do CKEditor -- editor.focus(),
    moveToElementEditablePosition, e até tentar casar a instância certa
    do CKEDITOR -- não resolverem de vez o problema da imagem caindo no
    parágrafo errado): clica DE VERDADE no corpo do texto, clica DE
    VERDADE no ícone do botão "Imagem", escolhe o arquivo, clica OK,
    espera salvar e clica em "Salvar" -- sem nenhuma chamada extra pela
    API do CKEditor no meio do caminho.
    """
    frame_editor = _encontrar_frame_editor(pagina_editor)
    if frame_editor is None:
        raise SystemExit(
            "\n⚠️  Não encontrei o campo de texto (editor) do documento "
            "'Despesa Certificada' pra apagar e colar a imagem. A janela "
            f"do editor abriu em: {pagina_editor.url}\n"
        )

    corpo = frame_editor.locator('body[contenteditable="true"]').first
    corpo.click()

    # Apaga TUDO que já vem no corpo do texto -- seleciona tudo e apaga,
    # do mesmo jeito que um usuário faria com Ctrl+A / Delete. Envia
    # pelo teclado da PÁGINA (não do frame) porque o foco é o que manda
    # -- funciona através de iframes, já que o corpo.click() logo acima
    # garante que o foco está no campo certo.
    #
    # Caminho já confirmado -- não confere mais se o texto realmente
    # sumiu depois (era uma verificação de segurança de quando ainda
    # tentávamos descobrir o frame certo); isso tirava um
    # `inner_text()` + um `wait_for_timeout(150)` fixo do meio do
    # caminho a cada execução, sem nenhum ganho agora que o frame certo
    # já é sempre encontrado.
    pagina_editor.keyboard.press("Control+A")
    pagina_editor.keyboard.press("Delete")

    arquivos_ce = _localizar_arquivos_ce(processo, pasta_base)
    if not arquivos_ce:
        raise SystemExit(
            "\n⚠️  Não encontrei nenhum arquivo 'Despesa Certificada*.jpg' "
            f"na pasta do processo '{processo}' (dentro de {pasta_base}). "
            "A Etapa Anexar Documento precisa ter baixado a CE antes de "
            "rodar a Etapa SEI (2).\n"
        )

    # O drag-and-drop (simulado E manual/de verdade, confirmado num
    # vídeo de teste) NÃO funciona nesse campo -- o "fantasma" do
    # arquivo sendo arrastado some ao soltar, mas nenhuma <img> aparece.
    # O jeito de verdade, confirmado ao vivo: o botão "Imagem" da barra
    # de ferramentas do CKEditor (plugin base64image) abre um diálogo
    # com um campo de arquivo (name="filArquivo") que insere a imagem
    # direto como base64, sem precisar de upload pra um servidor.
    qtd_imagens_antes = corpo.locator("img").count()

    for caminho_arquivo in arquivos_ce:
        # Reduz a imagem ANTES de inserir, se for grande demais -- ver
        # _preparar_imagem_para_insercao() pra entender por quê (limite
        # de tamanho no lado do servidor, confirmado ao vivo).
        caminho_para_inserir = _preparar_imagem_para_insercao(caminho_arquivo)
        # _abrir_dialogo_imagem() clica no `corpo` primeiro, depois foca
        # (só) a instância do CKEDITOR correspondente a `frame_editor` e
        # clica no botão "Imagem" da barra de ferramentas DELA -- essa
        # janela tem várias instâncias/barras na mesma tela (uma por
        # seção do documento), então precisa saber qual é a certa.
        dialogo = _abrir_dialogo_imagem(pagina_editor, frame_editor=frame_editor, corpo=corpo)
        _preencher_e_confirmar_dialogo_imagem(pagina_editor, dialogo, caminho_para_inserir)
        print(f"Imagem da CE inserida no editor (diálogo 'Imagem' do CKEditor): {os.path.basename(caminho_arquivo)}")

    # Nota: NÃO trava a execução se essa contagem não bater -- na prática
    # (confirmado pelo usuário) a imagem já está sendo inserida
    # corretamente no documento, mesmo quando esse `corpo.locator("img")`
    # (referência do frame pega antes de abrir o diálogo) não reflete
    # isso -- só avisa, sem interromper o fluxo.
    qtd_imagens_depois = corpo.locator("img").count()
    if qtd_imagens_depois <= qtd_imagens_antes:
        print(
            f"\nAviso: a contagem de <img> no corpo não aumentou (tinha "
            f"{qtd_imagens_antes}, continua {qtd_imagens_depois}), mas "
            "seguindo em frente -- na prática a imagem já é inserida "
            "corretamente."
        )
    else:
        print(f"\n✅ Imagem da CE inserida com sucesso no documento (tinha {qtd_imagens_antes}, agora {qtd_imagens_depois}).")

    # Descoberta ao vivo (comparando um vídeo da automação com um vídeo
    # da mesma ação feita manualmente): a imagem aparece na tela igual
    # nos dois casos, mas quando o clique em "Salvar" acontece rápido
    # demais depois da inserção, a versão salva no servidor sai SEM a
    # imagem -- ou seja, o `editor.getData()` que o botão "Salvar"
    # realmente envia ainda não reflete a imagem no exato instante do
    # clique (o DOM já mostra a <img>, mas o "snapshot"/estado interno
    # do CKEditor pode demorar um pouco mais pra reconhecer a mudança).
    # Na hora manual, a pessoa naturalmente demora alguns segundos entre
    # inserir a imagem e clicar em Salvar, dando tempo suficiente.
    #
    # Por isso, antes de seguir (e antes do botão "Salvar" ser clicado
    # lá em executar_sei2), força o CKEditor a registrar a mudança AGORA
    # (dispara 'change' e salva um snapshot pro undo) e espera até
    # `getData()` realmente conter a imagem em base64 -- só depois
    # disso é seguro dizer que o clique em "Salvar" vai gravar o
    # conteúdo certo. Passa `frame_editor` pra conferir a instância
    # CERTA do CKEditor (ver comentário dentro da função sobre o bug de
    # sempre checar a instância errada).
    _esperar_getData_conter_imagem(pagina_editor, frame_editor=frame_editor)

    # Devolve o frame do corpo do texto já identificado aqui -- assim
    # quem chamar (executar_sei2) pode passar ESSE MESMO frame pra
    # _clicar_salvar_editor() em vez de descobrir de novo do zero (evita
    # um round-trip de busca por frame repetido à toa).
    return frame_editor


def _esperar_getData_conter_imagem(
    pagina_editor, frame_editor=None, timeout_ms: int = 5000
) -> None:
    """
    Espera até que `CKEDITOR.instances[...].getData()` -- o HTML que o
    botão "Salvar" de fato vai enviar pro servidor -- contenha uma
    imagem em base64 (`<img ... src="data:`).

    Isso é diferente de conferir `corpo.locator("img").count()`: aquilo
    olha o DOM renderizado (que já mostra a imagem na hora), enquanto
    `getData()` reflete o estado INTERNO que o CKEditor considera "dado
    salvo" -- os dois podem estar temporariamente dessincronizados logo
    depois da inserção. Clicar em Salvar antes dessa sincronização
    terminar é a explicação mais provável, confirmada comparando um
    vídeo da automação com um vídeo da mesma ação feita manualmente,
    pra por que a imagem aparece na tela mas não fica salva.

    Achado ao vivo (causa da "demora grande" bem antes do clique em
    "Salvar"): sem `frame_editor`, essa função sempre checava
    `Object.keys(CKEDITOR.instances)[0]` -- a PRIMEIRA instância nessa
    lista, que não é necessariamente a do corpo do texto (essa janela
    tem uma instância por seção do documento). Como a imagem só existe
    na instância do corpo, checar a instância errada nunca encontra a
    imagem -- e a função ficava esperando os `timeout_ms` INTEIROS (8s)
    à toa em TODA execução antes de desistir com o aviso de
    "getData() ainda não mostra a imagem". Agora casa a instância CERTA
    pelo mesmo jeito já usado em `_abrir_dialogo_imagem`/
    `_clicar_salvar_editor`: identidade do elemento <iframe> de
    `frame_editor`, não o nome. Com a instância certa, a confirmação
    normalmente sai já na primeira ou segunda tentativa (150-300ms), em
    vez do timeout inteiro.
    """
    iframe_alvo = None
    if frame_editor is not None:
        try:
            iframe_alvo = frame_editor.frame_element()
        except Exception as erro:
            print(
                "\n⚠️  Aviso: não consegui pegar o elemento <iframe> de "
                f"frame_editor pra conferir getData() da instância certa: {erro}"
            )

    intervalo_ms = 150
    tentativas = max(1, timeout_ms // intervalo_ms)

    for tentativa in range(tentativas):
        resultado = pagina_editor.evaluate(
            """(iframeAlvo) => {
                if (typeof CKEDITOR === 'undefined') return null;
                const nomes = Object.keys(CKEDITOR.instances || {});
                if (nomes.length === 0) return null;
                let editor = null;
                if (iframeAlvo) {
                    for (const nome of nomes) {
                        const candidato = CKEDITOR.instances[nome];
                        const janelaNativa = candidato.window && candidato.window.$;
                        const elementoIframe = janelaNativa ? janelaNativa.frameElement : null;
                        if (elementoIframe === iframeAlvo) {
                            editor = candidato;
                            break;
                        }
                    }
                }
                if (!editor) {
                    editor = CKEDITOR.instances[nomes[0]];
                }
                // Força o CKEditor a registrar a mudança AGORA, em vez
                // de esperar o próprio ciclo de detecção (baseado em
                // polling/typing buffer) perceber sozinho.
                try {
                    editor.fire('change');
                    editor.fire('saveSnapshot');
                } catch (erro) {
                    console.error('não deu pra forçar change/saveSnapshot:', erro);
                }
                const dados = editor.getData();
                return {
                    tamanho: dados.length,
                    temImg: dados.indexOf('<img') !== -1,
                    temBase64: dados.indexOf('base64') !== -1,
                };
            }""",
            iframe_alvo,
        )

        if resultado is None:
            pagina_editor.wait_for_timeout(intervalo_ms)
            continue

        if resultado["temImg"] and resultado["temBase64"]:
            print(
                "Confirmado: editor.getData() já contém a imagem em "
                f"base64 (tamanho do HTML: {resultado['tamanho']} "
                f"caracteres) -- seguro clicar em 'Salvar' agora."
            )
            return

        pagina_editor.wait_for_timeout(intervalo_ms)

    # Não conseguiu confirmar depois de esperar bastante -- avisa (sem
    # travar a execução, já que a contagem de <img> no DOM indicou que a
    # inserção visual funcionou) pra pelo menos deixar claro no log que
    # o "Salvar" pode não gravar a imagem dessa vez.
    print(
        f"\n⚠️  Aviso: depois de esperar {timeout_ms}ms, editor.getData() "
        "ainda não mostra a imagem em base64 -- o clique em 'Salvar' "
        "pode gravar a versão SEM a imagem. Seguindo em frente mesmo "
        "assim, mas se a imagem sumir depois de salvar, esse é o motivo."
    )


def executar_sei2(context, processo: str, arquivos: list[str] = None):
    """
    Volta pra aba do SEI -- encontra a que já está aberta (a mesma usada
    na Etapa SEI (1), se ainda estiver aberta no mesmo Chrome) ou abre
    uma nova se precisar -- e reabre o `processo`, pesquisando de novo e
    expandindo a árvore de pastas (mesma lógica de abrir_processo_sei(),
    da Etapa SEI (1); funciona mesmo se o processo já estiver aberto).

    Na sequência: clica em "Reabrir Processo" se o processo estiver
    arquivado, inclui um documento "Despesa Certificada", preenche
    Nível de Acesso (Restrito) + Hipótese Legal (Documento Preparatório)
    e salva.

    `arquivos` (opcional) é a lista de caminhos dos JPGs já baixados na
    Etapa Anexar Documento (ex: o item["arquivos_anexar"] de cada
    lançamento, devolvido por executar_anexar_lote()) -- ainda não é
    usada aqui, só já está reservada pro próximo passo (fazer o upload
    de verdade).

    Retorna a aba do SEI (Page), pronta pro próximo passo.
    """
    aba_sei = obter_ou_criar_aba(
        context,
        dominio="sei.sistemas.ro.gov.br",
        url_navegacao=URL_SEI,
    )
    aba_sei.bring_to_front()

    abrir_processo_sei(aba_sei, processo)

    # Dá um respiro pra rede/iframes assentarem antes de começar a
    # procurar botões -- logo depois de reabrir/expandir a árvore, os
    # iframes (ifrArvore, ifrConteudoVisualizacao, etc.) podem ainda
    # estar recarregando, e começar a busca nesse instante é o que
    # causa o erro "Frame was detached" (o frame que a busca pegou foi
    # destruído no meio do caminho porque ainda estava em navegação).
    _aguardar_rede(aba_sei)

    print(f"De volta no SEI, processo '{processo}' aberto.")

    # Se o processo estiver arquivado/encerrado, o SEI mostra o botão
    # "Reabrir Processo" -- clica nele pra poder anexar documento novo.
    # Se não achar em NENHUM lugar candidato, considera que "já foi
    # clicado" (processo já deve estar aberto) -- não é um erro fatal.
    _, locator_reabrir, nome_reabrir = _procurar_lugar(
        aba_sei, CANDIDATOS_FRAMES, 'img[title="Reabrir Processo"]:visible'
    )
    if locator_reabrir is not None:
        locator_reabrir.click()
        print(f"Processo estava arquivado -- cliquei em 'Reabrir Processo' (achado em '{nome_reabrir}').")
    else:
        print("Botão 'Reabrir Processo' não apareceu em nenhum lugar candidato -- processo já deve estar aberto.")

    # Botão "Incluir Documento" -- abre a tela de escolha do tipo de
    # documento a incluir no processo.
    frame_incluir, locator_incluir, nome_frame_incluir = _procurar_lugar(
        aba_sei, CANDIDATOS_FRAMES, 'img[title="Incluir Documento"]:visible'
    )
    if frame_incluir is None:
        print("\nFrames abertos nesta página do SEI:")
        for frame in aba_sei.frames:
            print(f"  - name={frame.name!r} url={frame.url}")
        raise SystemExit(
            "\n⚠️  Não encontrei o botão 'Incluir Documento' em nenhum "
            "lugar candidato. Inspeciona o botão no navegador (botão "
            "direito -> Inspecionar) e me diz dentro de qual <iframe> "
            "(pelo atributo name) ele está -- a lista de frames "
            "impressa acima também ajuda.\n"
        )

    print(f"Botão 'Incluir Documento' encontrado em '{nome_frame_incluir}'.")
    locator_incluir.click()
    _aguardar_rede(aba_sei)

    # Na tela de escolha do tipo de documento, seleciona "Despesa
    # Certificada" -- é o primeiro documento a ser incluído.
    #
    # Tenta primeiro no MESMO lugar (frame_incluir) onde "Incluir
    # Documento" acabou de ser encontrado -- é o candidato mais
    # provável, já que normalmente é a mesma área da tela que troca de
    # conteúdo depois do clique -- e só cai pros outros candidatos se
    # não for esse.
    candidatos_despesa = (frame_incluir,) + CANDIDATOS_FRAMES
    frame_despesa, locator_despesa, nome_frame_despesa = _procurar_lugar(
        aba_sei, candidatos_despesa, 'a.ancoraOpcao:has-text("Despesa Certificada")'
    )
    if frame_despesa is None:
        print("\nFrames abertos nesta página do SEI (depois de clicar em 'Incluir Documento'):")
        for frame in aba_sei.frames:
            print(f"  - name={frame.name!r} url={frame.url}")
        raise SystemExit(
            "\n⚠️  Não encontrei o link 'Despesa Certificada' em nenhum "
            "lugar candidato. Manda a lista de frames impressa acima "
            "(os nomes/urls podem ter mudado depois do clique em "
            "'Incluir Documento') que eu ajusto.\n"
        )

    print(f"Link 'Despesa Certificada' encontrado em '{nome_frame_despesa}'.")
    locator_despesa.click()
    _aguardar_rede(aba_sei)

    # Formulário de inclusão do documento "Despesa Certificada": clica
    # em "Nenhum" e, na sequência, em "Restrito" -- é o clique em
    # "Restrito" que faz aparecer o combo de Hipótese Legal
    # (#selHipoteseLegal) logo depois.
    #
    # Assume que esse formulário carrega no MESMO lugar onde
    # "Despesa Certificada" foi encontrado (`frame_despesa`) -- ainda
    # não confirmado ao vivo; se der timeout aqui, é só mandar o erro
    # que eu aplico a mesma busca por lugares candidatos nesses campos
    # também.
    frame_despesa.locator('label.infraRadioLabel[for="optNenhum"]').click()
    frame_despesa.locator('label.infraRadioLabel[for="optRestrito"]').click()

    # Hipótese Legal: "Documento Preparatório" (value="3").
    frame_despesa.locator("#selHipoteseLegal").select_option("3")

    # Salva o documento.
    #
    # Confirmado ao vivo que o SEI duplica esse botão -- tem um
    # "#btnSalvar" na barra de comandos de CIMA (divInfraBarraComandosSuperior)
    # e outro igual na de BAIXO (divInfraBarraComandosInferior), os dois
    # com o mesmo id (o que é inválido em HTML, mas o SEI faz assim) e o
    # mesmo onclick="confirmarDados()" -- clicar em qualquer um dos dois
    # tem o mesmo efeito, então usa `.first` pra não travar com "strict
    # mode violation" por achar mais de um elemento.
    # Salvar abre uma NOVA aba/janela -- o editor de texto do documento
    # "Despesa Certificada" recém-criado (URL com "acao=editor_montar")
    # -- por isso o clique precisa estar dentro de um
    # context.expect_page(), do mesmo jeito que as outras etapas
    # capturam os popups do SIGEF.
    with context.expect_page() as pagina_editor_info:
        frame_despesa.locator("#btnSalvar").first.click()

    pagina_editor = pagina_editor_info.value
    _aguardar_rede(pagina_editor)

    print(f"Editor do documento 'Despesa Certificada' aberto: {pagina_editor.url}")

    # Apaga o conteúdo padrão do documento e insere a(s) imagem(ns) da
    # CE (baixada(s) na Etapa Anexar Documento, na pasta do mesmo
    # processo) pra dentro do campo de texto -- sequência de cliques DE
    # VERDADE (corpo -> ícone "Imagem" -> arquivo -> OK), sem nenhuma
    # chamada pela API do CKEditor no meio (ver _abrir_dialogo_imagem).
    #
    # >>> TODO: falta ainda repetir esse mesmo passo (Incluir Documento
    # -> NL/PP/OB) pros outros documentos -- por enquanto só faz a CE.
    frame_editor_ce = _limpar_e_inserir_imagem_ce(pagina_editor, processo)

    # Clica em "Salvar" -- passa o MESMO frame do corpo do texto já
    # identificado acima, pra _clicar_salvar_editor() focar a instância
    # certa do CKEditor (a barra de ferramentas dela) antes de procurar o
    # botão -- mesma causa raiz (várias instâncias/barras na mesma
    # janela) já resolvida antes pro botão "Imagem".
    # Caminho já confirmado -- não recarrega mais a página só pra
    # conferir se salvou (era um "F5" de verificação; _clicar_salvar_editor
    # já espera a rede assentar depois do clique, então é seguro seguir
    # direto).
    _clicar_salvar_editor(pagina_editor, frame_editor=frame_editor_ce)

    pagina_editor.close()

    aba_sei.bring_to_front()
    return aba_sei


if __name__ == "__main__":
    # Teste isolado da Etapa SEI (2): conecta no Chrome já aberto e pede
    # só o processo diretamente pelo teclado -- não precisa rodar as
    # etapas anteriores de novo.
    from utils import conectar_chrome

    playwright, browser, context = conectar_chrome()
    try:
        sessao = carregar_sessao()
        processo = perguntar_ou_reusar(
            "Digite o processo do SEI (para reabrir)", "processo", sessao
        )
        aba_sei = executar_sei2(context, processo)
        print(f"OK: de volta no SEI. Página: {aba_sei.url}")
    finally:
        playwright.stop()
