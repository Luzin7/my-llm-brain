# my-llm-brain

Um template de "cérebro" compartilhado para guiar agentes de código com LLM: regras, agentes por função, skills, memória e quadro de tarefas, mantidos fora de qualquer projeto e instalados na ferramenta que você já usa.

Esta é uma tradução do README. O inglês é canônico: [README.md](README.md). Em caso de diferença, vale o inglês.

## O que é

Três partes, todas substituíveis:

- **Core** (`core/`): regras neutras (postura, orquestração, casos de borda, guardrails, memória), 12 agentes por função, uma skill de quadro de tarefas, um modelo de spec e algumas lições de método. Nada nele cita empresa, linguagem ou fornecedor de modelo.
- **Side** (uma pasta sua, fora deste repositório): seu escopo, tabela de aprovações, preferências, memória e tarefas. O `bin/brain-init` cria a partir de `templates/side/`.
- **Adapters** (`adapters/`): como cada ferramenta carrega o core. Claude Code, opencode ou um único `AGENTS.md` para ferramentas que leem só isso.

## Por que funciona

A maioria das falhas de agente é falha de processo: o agente começa a codar antes de entender o pedido, diz "pronto" sem evidência, revisa o próprio trabalho ou esquece o que aconteceu ontem. O brain corrige o processo, não o modelo.

- Um **maestro** planeja e despacha; **workers** estreitos implementam; **juízes** independentes revisam com contexto novo. Veja [docs/concepts.md](docs/concepts.md).
- "Pronto" exige evidência: execução de teste, diff, dado real.
- A memória é um índice curto sempre carregado; os detalhes carregam sob demanda.
- Trabalho que passa de uma sessão vive num quadro de tarefas, não no chat.
- Limites importantes (só orquestrar, teto de dispatches) são impostos em código onde a ferramenta permite, e escritos como texto onde não permite.

## Ganho por ferramenta

A camada de texto vale em qualquer lugar. Imposição e independência dependem do que a ferramenta consegue fazer. Não há paridade entre ferramentas nem entre modelos: escolha a coluna que importa.

| Ganho | Claude Code | opencode | Só AGENTS.md (Codex CLI, Gemini CLI, Cursor, Copilot) |
|---|---|---|---|
| Postura, guardrails, perguntas de borda, critérios de pronto (texto) | sim | sim | sim |
| Índice de memória sempre carregado | `autoMemoryDirectory` | trecho `instructions` | linha de leitura no início |
| Quadro de tarefas, memory-lint, heavy-lock, secret-scan (scripts) | sim | sim | se a ferramenta roda shell |
| Prompts por função | subagentes | subagentes | modos sequenciais, um contexto |
| Juiz independente (contexto novo) | sim | sim | não: autorrevisão, marcada como mais fraca |
| Modelo/esforço por função | sim | só modelo | não |
| Sessão principal só orquestra | hook `maestro-guard` (L3) | permissão negada no agente `maestro` (L3) | não |
| Teto de dispatches | hook (L3) | plugin (L3) | n/a |
| Aviso de tamanho de contexto | hook (L3) | plugin (L3) | não |
| Skills sob demanda | sim | sim | depende da ferramenta |

O resultado também varia com o modelo por trás da ferramenta. Modelos pequenos seguem arquivos longos de regras com menos fidelidade; respeite os limites de palavras em [docs/customization.md](docs/customization.md).

## Início rápido

Requisitos: Linux ou macOS (Windows via WSL), Python 3.9+, git. Não há nada para instalar: os scripts usam só a biblioteca padrão.

```bash
git clone <repo-url> my-llm-brain
cd my-llm-brain
```

Instale para o Claude Code no nível 2, num side novo em `~/brain/work`:

```bash
bin/brain-init ~/brain/work --harness claude-code --level 2
bin/brain-init ~/brain/work --verify
bin/tasks ~/brain/work/tasks new "First task"
bin/memory-lint ~/brain/work/memory
```

O que aconteceu:

- `~/brain/work` agora tem `rules/side.md`, `rules/preferences.md`, `memory/MEMORY.md`, `tasks/` e `specs/`. Preencha os campos nos dois arquivos de regras.
- As regras renderizadas foram para `~/brain/work/.generated/CLAUDE.md`; seu `~/.claude/CLAUDE.md` recebeu uma linha de import com `@` (um backup com data fica se o arquivo já existia).
- 12 agentes e a skill `task-board` foram escritos em `~/.claude/`.
- `--verify` sai com 0 quando tudo está ligado; um checkout movido é reportado com o caminho morto.

Depois abra o `claude` em qualquer projeto. Peça algo pequeno e observe o ciclo: plano, dispatch, revisão, relatório. Veja qualquer instalação antes com `--dry-run`. Para opencode ou um único `AGENTS.md`, use os guias abaixo.

## Níveis

| Nível | Adiciona | Use quando |
|---|---|---|
| L1 | Regras, índice de memória, quadro de tarefas. Funciona em qualquer ferramenta. | Você quer o método sem agentes. Padrão do `agents-md`. |
| L2 (padrão) | Agentes por função e skills. | Você usa Claude Code ou opencode. |
| L3 | Hooks, plugins, permissões (`--level 3`, opcional). | Você quer só-orquestrar e o teto de dispatches impostos. |

O L3 altera as configurações da sua ferramenta. O `brain-init` mescla apenas entradas ausentes, faz backup antes e nunca edita o JSONC do opencode. Veja os guias por ferramenta.

## Guias por ferramenta

- [Claude Code](docs/harness/claude-code.md)
- [opencode](docs/harness/opencode.md)
- [Ferramentas só com AGENTS.md](docs/harness/agents-md.md)

## Próximos passos

1. Edite `rules/side.md` (escopo, temas encerrados, aprovações) e `rules/preferences.md`. Ambos são seus; o core nunca sobrescreve.
2. Escolha preferências e padrões: [docs/customization.md](docs/customization.md).
3. Entenda o ciclo e as camadas de memória: [docs/concepts.md](docs/concepts.md).
4. Adicione skills de terceiros com segurança: [docs/skills.md](docs/skills.md).
5. Dúvidas: [docs/faq.md](docs/faq.md). Mudar o próprio template: [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

MIT, veja [LICENSE](LICENSE).
