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


## GPU (NVIDIA/AMD), reconhecimento e voz neural local

O IAExpert usa **Ollama**, que seleciona automaticamente aceleração por GPU compatível no Windows (NVIDIA ou AMD). Use `ollama ps` para confirmar se o modelo está na GPU. A quantidade de VRAM e a compatibilidade da placa determinam a aceleração real.

O reconhecimento **Faster-Whisper** inicia em modo **Automático**: procura CUDA/CTranslate2; se não estiver disponível, executa na CPU sem exigir instalação adicional. O suporte CUDA requer **NVIDIA**, CUDA 12, cuBLAS e cuDNN 9 compatíveis. Placas AMD/Intel ainda podem acelerar o Ollama, mas não esse caminho CUDA do Whisper. Clicar com o botão direito no rosto → **Reconhecimento: GPU/CPU...** permite escolher automático, CPU ou forçar CUDA.

### Voz mais humana, sem enviar texto a terceiros

Se houver GPU NVIDIA CUDA com VRAM suficiente (o consumo varia conforme driver e modelos), é possível instalar **Chatterbox Multilingual V3**, sintetizador neural local que suporta português brasileiro. A biblioteca Chatterbox é MIT, mas o download dos pesos pode consumir vários gigabytes, e a voz pode demorar na primeira execução. A instalação **não é automática** porque envolve PyTorch e pacotes CUDA grandes:

~~~powershell
.\Instalar-Voz-GPU.ps1
~~~

Após a instalação, reinicie o IAExpert, clique com o botão direito no rosto → **Voz e naturalidade...** → **Chatterbox — neural local NVIDIA GPU**. O primeiro uso baixa o modelo. O código usa `ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")` e gera texto em português usando `language_id="pt"`. Se o motor falhar, o IAExpert tenta continuar com o Piper local.

**Não há garantia de que Chatterbox será mais rápido que a voz online:** ele melhora a naturalidade, mas pode demandar mais processamento por frase. A versão V3 multilíngue tem aproximadamente 500M parâmetros. Se a GPU for antiga ou tiver pouca VRAM, mantenha o Piper local ou use a voz neural online opcional mediante autorização. O Ollama e o Chatterbox podem competir pela VRAM.

### Identificar gargalo

Na pasta do projeto, execute:

~~~powershell
.\Diagnosticar-GPU.ps1
~~~

O script identifica o adaptador gráfico, consulta `nvidia-smi` (quando disponível), verifica CUDA no CTranslate2 e PyTorch, mostra `ollama ps` e apresenta os últimos tempos registrados. A medição é feita sem registrar o texto do usuário. A primeira pergunta pode demorar pelo carregamento do modelo; o aplicativo pré-carrega o Ollama em paralelo à escuta do microfone. O desempenho real só pode ser medido no seu PC.


## Sincronização real de voz e encerramento

A boca do IAExpert não depende mais de uma estimativa externa ao áudio.
**Piper, Francisca/Antônio e Chatterbox** agora usam o mesmo `iaexpert/playback.py`, que envia buffers PCM16 para o PortAudio por meio de `sounddevice.OutputStream`.

O mesmo buffer usado para reprodução calcula o envelope RMS da boca e fornece o instante esperado de apresentação no dispositivo, usando `outputBufferDacTime`. A interface agenda o quadro facial conforme esse timestamp, com atualização de até 60 FPS. O atraso real pode variar com driver, Bluetooth e processamento do Windows. Isso é sincronização pelo áudio, **não análise de fonemas/visemas**: os lábios abrem e fecham com a energia sonora e podem não corresponder exatamente às letras pronunciadas.

Durante uma piscada, apenas a região dos olhos é substituída; a imagem da boca mantém o mesmo quadro de áudio.

### Encerrar com segurança

- **Clique com botão direito no rosto → Sair**, ou pressione **Esc** com o avatar em foco.
- A aplicação oferece um ícone na bandeja de notificações do Windows com a ação **Encerrar IAExpert**, útil quando o rosto não estiver em foco.
- O fechamento normal solicita interrupção do áudio e termina a janela assim que o trabalhador finaliza.
- Se um sintetizador neural estiver travado e ignorar cancelamento, o pedido explícito de saída finaliza o processo após aproximadamente 3 segundos. Isso também interrompe a geração em andamento.
- Quando iniciado por `IAExpert.cmd`/`Iniciar-IAExpert.ps1`, o aplicativo observa o processo PowerShell iniciador. Se o terminal for fechado e esse processo morrer, o aplicativo também encerra automaticamente, evitando continuar oculto no gerenciador de tarefas.

Ajustes de temporização e encerramento devem ser validados com o seu driver de som real no Windows. Os testes automatizados simulam o PortAudio e a renderização Qt; não medem a latência física de uma saída Bluetooth/USB.


### Ctrl+C no terminal — encerramento sem traceback

A aplicação instala um manipulador próprio para Ctrl+C (SIGINT e SIGBREAK
quando disponível). Ele não interrompe a função de animação do Qt; apenas
sinaliza o pedido de saída, processado por um temporizador Qt. O encerramento
normal cancela a gravação, a síntese e o worker; se uma biblioteca externa
ignorar o cancelamento, o processo é encerrado após o timeout de segurança.

Ao iniciar pelo IAExpert.cmd, Ctrl+C deve encerrar a interface sem exibir
"KeyboardInterrupt". Também pode usar Esc com o rosto em foco ou
"Encerrar IAExpert" na bandeja do Windows. Fechar o terminal iniciador
continua encerrando o aplicativo.
