# IAExpert — assistente de voz local

O IAExpert é um assistente conversacional para Windows: você fala em português, a IA responde falando. Oferece Piper totalmente local e vozes neurais brasileiras opcionais que requerem conexão e autorização. A interface é **somente o rosto, flutuando sobre os programas abertos no computador**: sem chat, caixas de digitação, bordas ou fundo artificial. O restante da janela é realmente transparente. A boca abre/fecha em função do áudio que está saindo do alto-falante, o rosto se inclina suavemente e os olhos piscam.

## Instalar ou atualizar (Windows 10/11)

Pré-requisitos: microfone, alto-falantes, [Python 3.11 x64](https://www.python.org/downloads/windows/) e [Ollama](https://ollama.com/download/windows).

Primeiro uso: baixe ou clone este repositório e execute **IAExpert.cmd**. O inicializador instala as dependências em ambiente virtual e baixa automaticamente o modelo de IA **qwen3.5:2b** (mais leve que o 4B anterior).

Atualizar uma instalação já clonada:

~~~powershell
git pull origin main
.\IAExpert.cmd
~~~

Na primeira pergunta falada, os modelos de reconhecimento são baixados. A conversa com o Ollama e o reconhecimento do microfone permanecem locais por padrão. Se escolher uma voz neural online, o texto das respostas será enviado ao serviço de TTS selecionado.

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

A velocidade final depende do processador, da saída de áudio e dos modelos instalados. O primeiro uso pode demorar pelo download dos modelos. O avatar utiliza deformações faciais 2D: abertura dos lábios acompanhando a amplitude real do áudio, piscadas e balanço de cabeça. **Isso não equivale a um modelo de vídeo facial com fonemas e músculos precisos**, mas o rosto deixa de ser estático. Para melhorar a qualidade do rosto, é possível substituir a imagem padrão de alta resolução em `assets/avatar-v2.webp`. O novo arquivo `assets/avatar-v2.webp` é incluído automaticamente pela atualização da branch principal. A imagem antiga não é mais escolhida por padrão.

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

## Retrato v2 corrigido

A partir desta versão, `assets/avatar-v2.webp` é a imagem padrão: 818 × 1131 pixels, cor e transparência reais. O retrato antigo não é ampliado. A deformação da boca foi restringida aos lábios para evitar alongamento do queixo e do nariz. Se você já havia colocado um `assets/avatar-head.webp` manualmente, ele deixa de ter prioridade. Feche o IAExpert e use `git pull origin main` seguido de `IAExpert.cmd`.

A animação facial continua sendo uma aproximação 2D guiada pela amplitude, não uma representação realista de fonemas ou músculos em 3D.

---

## Voz neural, qualidade e velocidade

### Configuração ao iniciar

No primeiro início após a atualização, o IAExpert pergunta qual motor de voz usar.

- **Sim — Francisca Neural (online):** voz brasileira mais natural, selecionada somente se você autorizar. **O texto de cada resposta falada é transmitido ao serviço on-line de voz da Microsoft** por uma integração `edge-tts`. O áudio do microfone, a transcrição de suas perguntas e o histórico de conversas não são transmitidos por esta funcionalidade. Requer internet; a disponibilidade não é garantida, pois essa biblioteca não usa uma API oficial com contrato de disponibilidade.
- **Não — Piper (offline):** mantém a síntese de fala local, sem envio de texto para serviços de terceiros. É mais leve, mas costuma soar mais artificial.

Para alterar depois, clique com o botão direito no rosto e escolha **Voz e naturalidade...**, onde poderá selecionar Francisca, Antônio ou Piper. A passagem do modo local para o online exige confirmação de consentimento.

### Menor demora

O IAExpert faz streaming do Ollama e inicia a síntese da primeira frase assim que ela é produzida. Para reduzir o atraso foram ajustados:

- Reconhecimento Faster-Whisper modelo `tiny` por padrão em novas instalações. Para quem já tinha `base` configurado, a escolha antiga é mantida. Use **Reconhecimento: velocidade...** para escolher `tiny`, `base` ou `small`.
- Modelo de conversa `qwen3.5:2b` já existente, mantendo o modelo carregado no Ollama por 30 minutos.
- Contexto menor (últimas 8 mensagens, janela de 1536 tokens) e até 104 tokens por resposta. Isso prioriza respostas curtas e pode reduzir a lembrança de conversas antigas.
- Reprodução do primeiro trecho de voz enquanto o resto da resposta ainda é gerado.

**A velocidade depende do processador e da conexão.** Uma voz online pode ficar mais lenta se a conexão ou o serviço estiver indisponível. A troca de `base` para `tiny` pode diminuir a precisão do reconhecimento.

### Medir onde está lento

Ative a opção `performance_log` (padrão ligado) no `%LOCALAPPDATA%IAExpertsettings.json`. O arquivo `%LOCALAPPDATA%IAExpertperformance.log` registra os tempos em milissegundos:

- `stt_ms`: tempo para converter sua voz em texto.
- `first_token_ms`: tempo desde a pergunta até o primeiro texto do modelo.
- `first_audio_ms`: tempo até começar o áudio.
- `total_ms`: até o fim do turno, incluindo reprodução.

O log **não armazena o conteúdo das suas perguntas ou respostas**. Para verificar o diagnóstico no PowerShell:

~~~powershell
Get-Content "$env:LOCALAPPDATA\IAExpert\performance.log" -Tail 8
~~~

### Atualizar

Feche a aplicação e execute na pasta do projeto:

~~~powershell
git checkout main
git pull origin main
.\IAExpert.cmd
~~~

O inicializador instala as novas bibliotecas automaticamente quando o `requirements.txt` é alterado.
