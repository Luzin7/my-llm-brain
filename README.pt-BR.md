# my-llm-brain

Um template de "cérebro" compartilhado para guiar agentes de código com LLM: regras, agentes por função, skills, memória e quadro de tarefas, mantidos fora de qualquer projeto e instalados na ferramenta que você já usa.

Esta é uma tradução do README. O inglês é canônico: [README.md](README.md). Em caso de diferença, vale o inglês.

## O que é

Três partes, todas substituíveis:

- **Core** (`core/`): regras neutras (postura, orquestração, casos de borda, guardrails, memória), 12 agentes por função, uma skill de quadro de tarefas, um modelo de spec e algumas lições de método. Nada nele cita empresa, linguagem ou fornecedor de modelo.
- **Side** (uma pasta sua, fora deste repositório): seu escopo, tabela de aprovações, preferências, memória e tarefas. Criada a partir de `templates/side/` pela instalação.
- **Adapters** (`adapters/`): como cada ferramenta carrega o core. Claude Code, Codex, opencode ou um único `AGENTS.md` para ferramentas que leem só isso. O `dist/` guarda a saída gerada de cada uma; `python3 tools/build-dist` a reconstrói.

## Por que funciona

A maioria das falhas de agente é falha de processo: o agente começa a codar antes de entender o pedido, diz "pronto" sem evidência, revisa o próprio trabalho ou esquece o que aconteceu ontem. O brain corrige o processo, não o modelo.

- Um **maestro** planeja e despacha; **workers** estreitos implementam; **juízes** independentes revisam com contexto novo. Veja [docs/concepts.md](docs/concepts.md).
- "Pronto" exige evidência: execução de teste, diff, dado real.
- A memória é um índice curto sempre carregado; os detalhes carregam sob demanda.
- Trabalho que passa de uma sessão vive num quadro de tarefas, não no chat.
- Limites importantes (só orquestrar, teto de dispatches) são impostos em código onde a ferramenta permite, e escritos como texto onde não permite.

## Ganho por ferramenta

A camada de texto vale em qualquer lugar. Imposição e independência dependem do que a ferramenta consegue fazer. Não há paridade entre ferramentas nem entre modelos: escolha a coluna que importa.

| Ganho | Claude Code | Codex | opencode | Só AGENTS.md (Gemini CLI, Cursor, Copilot) |
|---|---|---|---|---|
| Postura, guardrails, perguntas de borda, critérios de pronto (texto) | sim | sim | sim | sim |
| Índice de memória sempre carregado | `autoMemoryDirectory` e imports `@` | linha de leitura no início | `instructions` | linha de leitura no início |
| Quadro de tarefas, memory-lint, heavy-lock, secret-scan (scripts) | sim | se a ferramenta roda shell | sim | se a ferramenta roda shell |
| Prompts por função | subagentes | agentes customizados (TOML) | subagentes | modos sequenciais, um contexto |
| Juiz independente (contexto novo) | sim | sim | sim | não: autorrevisão, marcada como mais fraca |
| Modelo/esforço por função | sim | esforço por agente | só modelo | não |
| Sessão principal só orquestra | hook `maestro-guard` (L3) | não | permissão negada no agente `maestro` (L3) | não |
| Teto de dispatches | hook (L3) | não | plugin (L3) | n/a |
| Aviso de tamanho de contexto | hook (L3) | não | plugin (L3) | não |
| Skills sob demanda | plugin | sim | sim | depende da ferramenta |

O resultado também varia com o modelo por trás da ferramenta. Modelos pequenos seguem arquivos longos de regras com menos fidelidade; respeite os limites de palavras em [docs/customization.md](docs/customization.md).

## Instalação

Requisitos: git. Python 3.9+ é opcional e só liga os guards do L3. Linux, macOS e Windows (o opencode no Windows roda no WSL).

```bash
git clone https://github.com/Luzin7/my-llm-brain.git
cd my-llm-brain
```

Há uma checklist, o [INSTALL.md](INSTALL.md), e duas formas de executá-la.

### Peça para sua IA instalar

Abra sua ferramenta dentro do clone e cole este prompt. O agente segue o INSTALL.md, mostra o plano, espera o seu "sim", aplica, registra e verifica:

```text
Instale o "cérebro" my-llm-brain para mim a partir deste clone.

1. Leia o INSTALL.md na raiz do repositório e siga exatamente, passo a passo. Rode só os comandos escritos lá; use os blocos PowerShell no Windows e os blocos POSIX nos demais.
2. Detecte em qual ferramenta você está rodando (Claude Code, Codex, opencode ou uma ferramenta só com AGENTS.md). Instale só essa, a menos que eu peça outras.
3. Antes de escrever qualquer coisa, mostre o plano do passo 3: cada arquivo que vai criar ou editar, cada backup, a pasta side, o Python encontrado. Depois pare e espere eu responder "sim".
4. Depois do meu sim, aplique os passos em ordem. Em qualquer linha que comece com STOP, pare e me avise. Nunca edite texto fora dos marcadores my-llm-brain, nunca sobrescreva um side existente, faça backup de todo arquivo editado antes.
5. Registre o que fez no .install-record.md do side, rode os blocos de verificação e as checagens da ferramenta para a minha, e cole a saída. Não diga "pronto" sem essa saída.
```

### Instale à mão

Abra o [INSTALL.md](INSTALL.md) e rode os blocos POSIX ou PowerShell em ordem, num único terminal, a partir do clone. Você faz as mesmas escolhas que o agente faria: o caminho do side, a ferramenta, o sim ao plano.

### Marketplace do Claude Code

O Claude Code também pode pegar os plugins direto do marketplace; o bloco de regras e o side continuam vindo do INSTALL.md:

```text
/plugin marketplace add Luzin7/my-llm-brain
/plugin install brain --marketplace Luzin7/my-llm-brain
```

### Vindo do v1

O v1 (o instalador `brain-init`) é a tag `v1`. A instalação v2 detecta os manifestos do v1 e para. Desinstale o v1 a partir dessa tag, seguindo o README dela, e só então comece o INSTALL.md.

### Dicas

- Obsidian (opcional): a pasta side (padrão `~/my-brain`) é markdown puro, então você pode abri-la como um vault do Obsidian para navegar pela memória e pelas tarefas. A IA lê os arquivos direto, então isso não é obrigatório. O Obsidian só cria uma pasta `.obsidian/`, que é inofensiva.
- Backup: a side é a única cópia do seu cérebro. Faça dela um repositório git privado seu: rode `git init` dentro da pasta side e envie para um remoto privado. Nunca coloque em um repositório público nem dentro deste clone.

## Níveis

| Nível | Adiciona | Use quando |
|---|---|---|
| L1 | Regras, índice de memória, quadro de tarefas. Funciona em qualquer ferramenta. | Você quer o método sem agentes. Padrão das ferramentas só com AGENTS.md. |
| L2 (padrão) | Agentes por função e skills. | Você usa Claude Code, Codex ou opencode. |
| L3 | Hooks, plugins, permissões (precisa de Python no Claude Code). | Você quer só-orquestrar e o teto de dispatches impostos. |

O L3 altera as configurações da sua ferramenta. Veja os guias por ferramenta.

## Guias por ferramenta

- [Claude Code](docs/harness/claude-code.md)
- [Codex](docs/harness/codex.md)
- [opencode](docs/harness/opencode.md)
- [Ferramentas só com AGENTS.md](docs/harness/agents-md.md)

## Próximos passos

1. Edite `rules/side.md` (escopo, temas encerrados, aprovações) e `rules/preferences.md` no seu side. Ambos são seus; o core nunca sobrescreve.
2. Escolha preferências e padrões: [docs/customization.md](docs/customization.md).
3. Entenda o ciclo e as camadas de memória: [docs/concepts.md](docs/concepts.md).
4. Adicione skills de terceiros com segurança: [docs/skills.md](docs/skills.md).
5. Dúvidas: [docs/faq.md](docs/faq.md). Mudar o próprio template: [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

MIT, veja [LICENSE](LICENSE).
