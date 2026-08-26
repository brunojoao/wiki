# Wiki Boom — tema e taxonomia

Arquivos que definem o visual e a organização do Wiki.js interno (`http://localhost:7778`).

| Arquivo | O que é |
|---|---|
| `custom.css` | Custom CSS do tema escuro (Administration > Theme > Custom CSS) |
| `home.html` | Conteúdo da Home Page (grade de cards do portal) |
| `apply.py` | Taxonomia declarativa (`FOLDERS`, `MOVES`) + gerador dos índices |
| `apply_graphql.py` | Aplica tudo via GraphQL. Idempotente — pode rodar de novo |

## Aplicar

```bash
cd theme
WIKIJS_TOKEN='<api key do grupo Administrators>' python3 apply_graphql.py --dry-run
WIKIJS_TOKEN='<api key do grupo Administrators>' python3 apply_graphql.py
```

Cria a API key em **Administration > API**. `apply.py` sozinho faz o mesmo escrevendo
direto no SQLite (exige o container parado) — só use se a API não estiver disponível.

## Reverter

`data/wiki.db` é versionado: `git checkout data/wiki.db` e reinicie o container.

## Estrutura

```
/ (Home Page)                             portal com a grade de cards
├── apis/                     APIs        APIs próprias, gateway e coleções
│   ├── api-boom              API Boom
│   ├── kong                  Kong APIs
│   └── use-bruno             Use Bruno
├── aws/                      AWS         rede, security groups, IPs
│   ├── inbound-rules         Inbound Rules
│   └── ips                   IP White List
├── crm/                      CRM         leads, atendimento, captação
│   ├── carchat               CarChat
│   ├── finalizacao-de-leads  Finalização de Leads
│   ├── lead-zoho             Zoho - Leads
│   ├── meta                  Meta
│   └── olx                   OLX
├── infraestrutura/           Infraestrutura   monitoramento, servidores, jobs
│   ├── new-relic             New Relic
│   └── terminator            Terminator
├── integracoes/              Integrações      parceiros e serviços externos
│   ├── assinatura-eletronica          Assinatura Eletrônica
│   ├── credere-multibanco-simulacao   Credere - MultiBanco Simulação
│   ├── integrador-boom-veiculos       Integrador - Boom Veículos
│   ├── integrador-portais-veiculos    Integrador - Portais de Veículos
│   ├── one-signal                     OneSignal
│   └── renave-visao-geral             Renave - Visão Geral
├── sistemas/                 Sistemas    módulos internos e postmortems
│   ├── contratos                        Contratos - Arquitetura do Módulo
│   └── cron-horizon-followup-duplicado  Cron - Horizon Parado e Follow-up Duplicado
└── sql/                      SQL         manutenção e limpeza de base
    ├── database-clear        Limpeza de Database
    ├── limpeza-financeiro    Limpeza do Financeiro
    └── unificacao-de-filial  Unificação de Filial
```

## Convenções

- **Título em Title Case, sem repetir o nome da pasta.** `crm/olx` chama-se `OLX`, não
  `CRM - Olx` — a pasta já aparece no menu e no breadcrumb, e o prefixo repetido era o
  que estourava a largura do sidebar.
- **Path em `minusculo-com-hifens`**, sem acentos.
- Toda pasta tem uma **página-índice** no path da própria pasta (`/crm`, `/apis`, …),
  gerada por `render_index()` a partir de `MOVES` — título + descrição de cada filha.
- Cada página tem `description` preenchida: é o que alimenta os cards dos índices,
  a busca e o preview.

## Para adicionar uma página nova

1. Crie em `<pasta>/<slug>` pelo editor.
2. Acrescente a entrada em `MOVES` (`apply.py`) e rode `apply_graphql.py` — os índices
   e as contagens de páginas se atualizam sozinhos.

## Notas

- **Wiki.js não cria redirect ao mover páginas**: os paths antigos (`/New-Relic`,
  `/kong-api`, `/renave-overview`, `/integrador/*`, `/cron`) respondem 404. Links
  externos ou favoritos apontando para eles precisam ser atualizados.
- A Home usa o editor **`code`** (HTML puro), não o CKEditor — o editor visual
  reescreveria o markup dos cards e dos SVGs.
- O CSS é minificado pelo Wiki.js na gravação; a fonte legível é `custom.css`.
