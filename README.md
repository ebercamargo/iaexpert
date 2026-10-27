# IAExpert 🎙️

Assistente de voz **open source para Windows**, em português do Brasil, com execução local. Você fala, ele transcreve, responde com inteligência artificial e fala de volta. O modo contínuo retoma a escuta depois de cada resposta.

> **Versão inicial (MVP):** este assistente conversa, mas ainda não executa comandos do Windows nem pesquisa na internet. A imagem de referência é apenas conceitual.

## Tecnologias

| Componente | Tecnologia | Papel |
| --- | --- | --- |
| Interface | Python 3.11, PySide6 / Qt 6 | Aplicativo desktop |
| IA | Ollama, Qwen 3.5 4B | Respostas conversacionais em português |
| Reconhecimento | Faster-Whisper, modelo base, CPU int8 | Voz para texto |
| Síntese | Piper, voz pt_BR-faber-medium | Texto para voz brasileira |
| Microfone/alto-falante | sounddevice / PortAudio | Entrada e saída de áudio |
| Conversas | JSON local | Histórico entre sessões |

Não requer chave de API paga nem GPU. Processamento de fala e da conversa fica no computador; **internet é necessária para instalar dependências e baixar os modelos pela primeira vez**. A qualidade/velocidade depende do hardware.

## Como executar no Windows

Pré-requisitos:

1. Windows 10 ou 11 de 64 bits, microfone e saída de áudio.
2. [Python 3.11 (64 bits)](https://www.python.org/downloads/windows/) com o launcher Python (comando py).
3. [Ollama para Windows](https://ollama.com/download/windows), instalado e aberto.
4. Internet durante a primeira instalação.

Clone o repositório, ou baixe o ZIP do GitHub e extraia. Na pasta do projeto, dê **dois cliques em IAExpert.cmd**.

O inicializador cria o ambiente virtual, instala bibliotecas e baixa o modelo qwen3.5:4b caso necessário. Na primeira fala, o Faster-Whisper baixa seu modelo de reconhecimento e o Piper baixa uma voz em português brasileiro.

~~~powershell
git clone https://github.com/ebercamargo/iaexpert.git
cd iaexpert
.\IAExpert.cmd
~~~

### Conversando

- Clique em **Iniciar conversa**, fale normalmente e faça uma pausa. O assistente transcreve sua pergunta e responde.
- Marque **Conversa contínua (mãos livres)** para retomar a escuta automaticamente após cada resposta. Clique em **Interromper** para parar.
- Também pode digitar na caixa de texto. Desmarque **Responder falando** para ler respostas sem áudio.
- Para melhorar a velocidade em CPUs, execute antes **ollama pull qwen3.5:2b** e selecione esse modelo na interface. Para hardware mais robusto, use qwen3.5:9b.
- **Limpar histórico** apaga os registros da conversa no computador.

Use fones para o microfone não capturar a voz sintetizada. No modo normal, ele aguarda até 15 segundos pelo início de uma fala; no contínuo, continua aguardando até ser interrompido.

### Configuração e privacidade

As configurações, histórico e arquivos de voz ficam em **%LOCALAPPDATA%\IAExpert**. Os modelos do Ollama e o cache do Whisper usam as pastas padrão dessas ferramentas.

Para ambientes ruidosos, altere microphone_threshold (padrão 0.014) em settings.json. Para transcrição mais precisa, altere whisper_model de base para small. A alteração exige reiniciar a aplicação.

O Ollama é acessado em http://127.0.0.1:11434 por padrão. Mudar ollama_url para um endereço remoto poderá enviar mensagens a esse servidor. Os JSON locais não têm criptografia; evite digitar segredos ou dados confidenciais.

## Solução de problemas

| Sintoma | Solução |
| --- | --- |
| Ollama não encontrado | Instale o Ollama, abra-o e reinicie IAExpert.cmd |
| Modelo de IA ausente | Execute no terminal: ollama pull qwen3.5:4b |
| Microfone silencioso | Verifique o microfone padrão e as permissões em Configurações → Privacidade → Microfone |
| Não reproduz áudio | Verifique o dispositivo de saída e a opção Responder falando |
| Detecta sons do ambiente | Ajuste microphone_threshold no settings.json |
| Primeiro uso lento | A primeira utilização baixa Whisper e Piper; na CPU a inferência demanda mais tempo |
| Respostas lentas | Tente o modelo qwen3.5:2b |

## Para contribuir

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m iaexpert
~~~

Veja [CONTRIBUTING.md](CONTRIBUTING.md).

**Evoluções possíveis:** hotword opcional, troca de dispositivos de som, indicador de volume, pesquisa na web com consentimento, ferramentas do computador com confirmação explícita e executável instalável.

Licença: [Apache 2.0](LICENSE).
