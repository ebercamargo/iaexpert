# IAExpert — assistente de voz local

O IAExpert é um assistente conversacional público para Windows: você fala em português, a IA responde falando. A interface é **somente o rosto, flutuando sobre os programas abertos no computador**: sem chat, caixas de digitação, bordas ou fundo artificial. O restante da janela é realmente transparente. A boca abre/fecha em função do áudio que está saindo do alto-falante, o rosto se inclina suavemente e os olhos piscam.

## Instalar ou atualizar (Windows 10/11)

Pré-requisitos: microfone, alto-falantes, [Python 3.11 x64](https://www.python.org/downloads/windows/) e [Ollama](https://ollama.com/download/windows).

Primeiro uso: baixe ou clone este repositório e execute **IAExpert.cmd**. O inicializador instala as dependências em ambiente virtual e baixa automaticamente o modelo de IA **qwen3.5:2b** (mais leve que o 4B anterior).

Atualizar uma instalação já clonada:

~~~powershell
git pull origin main
.\IAExpert.cmd
~~~

Na primeira pergunta falada, os modelos de reconhecimento de voz e síntese são baixados; após os downloads, a conversa e a voz são processadas localmente.

## Conversar sem interface de chat

- **Ao abrir**: a escuta inicia automaticamente; basta falar e fazer uma pausa.
- **Clique esquerdo no rosto** ou **espaço**: pausar ou retomar escuta.
- **Clique direito no rosto**: trocar microfone, trocar modelo, ativar/desativar voz, limpar histórico ou sair.
- **Ctrl+M**: escolher microfone.
- **Arrastar o rosto**: mudar de posição, mantendo visíveis as janelas abertas atrás dele.
- **Esc**: encerrar IAExpert.

Por padrão, a escuta contínua fica ativa; depois de falar, a IA volta a ouvir. Use fones para evitar que a própria voz sintetizada seja capturada pelo microfone.

## Redução da latência e pronúncia

- O modelo padrão foi reduzido de **Qwen 3.5 4B para 2B** para favorecer máquinas sem GPU.
- As respostas são limitadas a poucas frases e a até 144 tokens por resposta, com contexto reduzido.
- **Síntese progressiva:** a primeira frase começa a ser sintetizada enquanto o modelo ainda está gerando o restante. Não é necessário aguardar a resposta inteira.
- Os caracteres de Markdown (asteriscos, marcações de negrito e tópicos) são removidos antes da leitura.
- O silêncio para encerrar a pergunta foi reduzido a 0,72 segundo.
- O texto da conversa não aparece na tela; o histórico continua salvo localmente para manter o contexto.

A velocidade final depende do processador, da saída de áudio e dos modelos instalados. O primeiro uso pode demorar pelo download dos modelos. O avatar utiliza deformações faciais 2D: abertura dos lábios acompanhando a amplitude real do áudio, piscadas e balanço de cabeça. **Isso não equivale a um modelo de vídeo facial com fonemas e músculos precisos**, mas o rosto deixa de ser estático. Para melhorar a qualidade do rosto, é possível salvar uma imagem RGBA de alta resolução em `assets/avatar-head.webp`. O arquivo anterior `assets/avatar.webp` continua funcionando como alternativa.

## Diagnóstico

Se ele não ouvir: clique com o botão direito no rosto, selecione **Escolher microfone** e confira se o Windows permite o acesso a ele. Se não falar: abra o menu e confira **Ativar voz**, além da saída de áudio padrão no Windows.

Ollama executa localmente por padrão em http://127.0.0.1:11434. O usuário pode selecionar um modelo mais pesado no menu após instalar com comando como **ollama pull qwen3.5:4b**. Se mudar o servidor para um Ollama remoto, a conversa poderá ser enviada àquele servidor.

## Desenvolvimento

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m iaexpert
~~~

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Código do repositório sob licença [Apache 2.0](LICENSE); dependências têm suas próprias licenças, incluindo o Piper TTS (GPL-3.0-or-later). Verificar as condições antes da redistribuição em binário. Sem API paga obrigatória.

Ainda não realiza comandos do computador ou buscas na internet automaticamente.

## Fundo transparente e sobreposição

A janela usa os atributos de transparência do Windows/Qt e a opção de permanecer acima das outras janelas. A transparência não é um fundo fictício: você verá o navegador ou qualquer outro aplicativo que estiver aberto atrás do rosto. Uma imagem com fundo opaco não é adequada; o retrato precisa possuir um canal alpha.
