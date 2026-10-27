# Como contribuir com IAExpert

Obrigado por colaborar com um assistente pessoal de IA gratuito, local e aberto.

1. Abra uma issue para bugs e sugestões.
2. Crie um branch e um PR pequeno, com descrição e passos de teste.
3. Execute os testes Python antes de enviar o PR.
4. Não inclua na contribuição áudio de pessoas, modelos binários, credenciais, históricos ou caches.
5. Para mudanças de interface, envie capturas de tela e teste no Windows.

## Estrutura

- iaexpert/config.py: preferências da aplicação.
- iaexpert/history.py: histórico local em JSON.
- iaexpert/ollama_client.py: chat via HTTP local e streaming.
- iaexpert/audio.py: captura de voz, STT e síntese offline.
- iaexpert/worker.py: processamento em QThread para não bloquear Qt.
- iaexpert/ui.py: interface desktop e visualização vetorial.
- tests/: testes sem dependência dos modelos de IA.

## Princípios

- Privacidade por padrão: microfone e transcrição locais.
- Nenhuma ação perigosa no PC sem consentimento explícito.
- Nenhuma API paga obrigatória.
- Documentar downloads, limitações e licenças dos modelos usados.
- Cuidar da acessibilidade, erros compreensíveis e responsividade da interface.

### Testar

~~~shell
python -m compileall -q iaexpert tests
python -m unittest discover -s tests -v
~~~
