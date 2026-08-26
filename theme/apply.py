#!/usr/bin/env python3
"""
Reorganiza a taxonomia do Wiki.js, injeta o Custom CSS e reescreve a Home Page.

Uso (com o container PARADO):
    python3 apply.py            # aplica
    python3 apply.py --dry-run  # apenas mostra o que faria
"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(HERE), 'data', 'wiki.db')
LOCALE = 'pt-br'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + \
      f'{datetime.now(timezone.utc).microsecond // 1000:03d}Z'

DRY = '--dry-run' in sys.argv


def page_hash(path, locale=LOCALE, private_ns=''):
    """Espelha pageHelper.generateHash() do Wiki.js."""
    return hashlib.sha1(f'{locale}|{path}|{private_ns}'.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 1. Pastas de alto nível (páginas-índice)
# ---------------------------------------------------------------------------
FOLDERS = [
    # path,             título,           descrição,                                                       ícone mdi
    ('infraestrutura', 'Infraestrutura', 'Monitoramento, acesso a servidores e execução de jobs.',          'mdi-server'),
    ('integracoes',    'Integrações',    'Parceiros e serviços externos conectados ao ecossistema Boom.',   'mdi-transit-connection-variant'),
    ('apis',           'APIs',           'APIs próprias, gateway e coleções de endpoints.',                 'mdi-api'),
    ('sistemas',       'Sistemas',       'Arquitetura dos módulos internos e postmortems.',                 'mdi-application-braces'),
    ('crm',            'CRM',            'Leads, atendimento e integrações de captação.',                   'mdi-account-group'),
    ('sql',            'SQL',            'Rotinas de manutenção e limpeza de base.',                        'mdi-database'),
    ('aws',            'AWS',            'Rede, security groups e liberação de IPs.',                       'mdi-cloud'),
]

# páginas-índice já existentes que serão reaproveitadas: path atual -> novo path
INDEX_REUSE = {'crm': 25, 'sql': 26, 'aws': 27, 'integracoes': 28, 'sistemas': 29}

# ---------------------------------------------------------------------------
# 2. Movimentação / padronização das páginas de conteúdo
#    id: (novo path, novo título, descrição)
# ---------------------------------------------------------------------------
MOVES = {
    # Home
    2:  ('home', 'Home Page', 'Portal central da documentação técnica do time de desenvolvimento.'),

    # APIs
    10: ('apis/api-boom',  'API Boom',   'API pública da Boom para parceiros e clientes.'),
    12: ('apis/kong',      'Kong APIs',  'Gateway Kong: services, routes e plugins.'),
    3:  ('apis/use-bruno', 'Use Bruno',  'Compartilhamento das coleções de endpoints no Bruno.'),

    # AWS
    6:  ('aws/inbound-rules', 'Inbound Rules', 'Regras de entrada dos security groups.'),
    13: ('aws/ips',           'IP White List', 'IPs liberados no ambiente de produção.'),

    # CRM
    9:  ('crm/carchat',              'CarChat',              'Integração de atendimento CarChat.'),
    1:  ('crm/finalizacao-de-leads', 'Finalização de Leads', 'Finalização de leads usando SQL.'),
    19: ('crm/lead-zoho',            'Zoho - Leads',         'Entrada de leads vindos do Zoho.'),
    17: ('crm/meta',                 'Meta',                 'Captação de leads via Meta (Facebook/Instagram).'),
    16: ('crm/olx',                  'OLX',                  'Captação de leads via OLX.'),

    # Infraestrutura
    20: ('infraestrutura/new-relic',  'New Relic',  'Monitoramento de performance, erros e incidentes.'),
    11: ('infraestrutura/terminator', 'Terminator', 'Configuração do terminal e acesso aos servidores.'),

    # Integrações
    15: ('integracoes/assinatura-eletronica',         'Assinatura Eletrônica',          'Fluxo de assinatura eletrônica de documentos.'),
    22: ('integracoes/credere-multibanco-simulacao',  'Credere - MultiBanco Simulação', 'Simulador e propostas de financiamento (MultiBanco / Credere).'),
    18: ('integracoes/integrador-boom-veiculos',      'Integrador - Boom Veículos',     'Hospedagem e publicação do Boom Veículos.'),
    21: ('integracoes/integrador-portais-veiculos',   'Integrador - Portais de Veículos', 'Arquitetura do módulo de integração com portais de veículos.'),
    14: ('integracoes/one-signal',                    'OneSignal',                      'Envio de notificações push via OneSignal.'),
    7:  ('integracoes/renave-visao-geral',            'Renave - Visão Geral',           'Visão geral da integração com o Renave.'),

    # Sistemas
    23: ('sistemas/contratos',                        'Contratos - Arquitetura do Módulo',           'Geração de contratos, placeholders, cláusulas e pegadinhas.'),
    24: ('sistemas/cron-horizon-followup-duplicado',  'Cron - Horizon Parado e Follow-up Duplicado', 'Postmortem (ago/2026): Horizon sem supervisor gerou follow-up de IA duplicado.'),

    # SQL
    8:  ('sql/database-clear',        'Limpeza de Database',   'Rotina de limpeza geral da base.'),
    4:  ('sql/limpeza-financeiro',    'Limpeza do Financeiro', 'Rotina de limpeza dos registros financeiros.'),
    5:  ('sql/unificacao-de-filial',  'Unificação de Filial',  'Procedimento de unificação de filiais.'),
}


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def render_index(folder_path, folder_title, folder_desc, children):
    """Monta o HTML de uma página-índice com a mesma grade de cards da Home."""
    cards = []
    for path, title, desc in children:
        cards.append(
            f'  <a class="hub-card" href="/{path}">'
            f'<span class="hub-title">{esc(title)}</span>'
            f'<span class="hub-desc">{esc(desc)}</span></a>'
        )
    grid = '\n'.join(cards)
    n = len(children)
    plural = 'página' if n == 1 else 'páginas'
    # h1 sem âncora: o renderer htmlCore injeta id + <a class="toc-anchor"> sozinho
    return (
        f'<h1>{esc(folder_title)}</h1>\n'
        f'<p class="hub-sub">{esc(folder_desc)} &mdash; {n} {plural}.</p>\n'
        f'<div class="hub-grid">\n{grid}\n</div>\n'
    )


def main():
    if not os.path.exists(DB):
        sys.exit(f'DB não encontrado: {DB}')

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ---- valida que nada foi movido ainda ---------------------------------
    existing = {r['id']: r['path'] for r in cur.execute('select id, path from pages')}
    for pid in MOVES:
        if pid not in existing:
            sys.exit(f'Página id={pid} não existe mais. Abortando.')

    # ---- 1. renomeia/move as páginas de conteúdo --------------------------
    for pid, (path, title, desc) in MOVES.items():
        print(f'  mv  {existing[pid]:<42} -> {path:<44} "{title}"')
        if not DRY:
            cur.execute(
                'update pages set path=?, hash=?, title=?, description=?, updatedAt=? where id=?',
                (path, page_hash(path), title, desc, NOW, pid))

    # a Home passa a usar o editor de código (o CKEditor destruiria o HTML dos cards)
    if not DRY:
        cur.execute("update pages set editorKey='code' where id=2")

    # ---- 2. páginas-índice das pastas -------------------------------------
    children = {f[0]: [] for f in FOLDERS}
    for pid, (path, title, desc) in MOVES.items():
        if '/' in path:
            children[path.split('/')[0]].append((path, title, desc))
    for k in children:
        children[k].sort(key=lambda c: c[1].lower())

    for path, title, desc, _icon in FOLDERS:
        html = render_index(path, title, desc, children[path])
        toc = json.dumps([{'title': title, 'anchor': f'#{path}', 'children': []}],
                         ensure_ascii=False)
        pid = INDEX_REUSE.get(path)
        if pid:
            old = existing[pid]
            print(f'  idx {old:<42} -> {path:<44} "{title}" ({len(children[path])} filhas)')
            if not DRY:
                cur.execute(
                    'update pages set path=?, hash=?, title=?, description=?, content=?, '
                    'render=?, toc=?, editorKey=?, updatedAt=? where id=?',
                    (path, page_hash(path), title, desc, html, html, toc, 'code', NOW, pid))
        else:
            print(f'  new {"-":<42} -> {path:<44} "{title}" ({len(children[path])} filhas)')
            if not DRY:
                cur.execute(
                    'insert into pages (path, hash, title, description, isPrivate, isPublished, '
                    'content, render, toc, contentType, createdAt, updatedAt, editorKey, '
                    'localeCode, authorId, creatorId, extra) '
                    "values (?,?,?,?,0,1,?,?,?,'html',?,?,'code',?,1,1,'{\"js\":\"\",\"css\":\"\"}')",
                    (path, page_hash(path), title, desc, html, html, toc, NOW, NOW, LOCALE))

    # ---- 3. Home Page ------------------------------------------------------
    home = open(os.path.join(HERE, 'home.html'), encoding='utf-8').read()
    home_render = home
    for anchor, text in (('wiki-de-desenvolvimento', 'Wiki de Desenvolvimento'),):
        home_render = home_render.replace(
            f'<h1>{text}</h1>',
            f'<h1 id="{anchor}" class="toc-header">'
            f'<a class="toc-anchor" href="#{anchor}">&#xB6;</a> {text}</h1>')
    for anchor, text in (('atalhos-rápidos', 'Atalhos rápidos'),
                         ('como-contribuir', 'Como contribuir')):
        home_render = home_render.replace(
            f'<h2>{text}</h2>',
            f'<h2 id="{anchor}" class="toc-header">'
            f'<a class="toc-anchor" href="#{anchor}">&#xB6;</a> {text}</h2>')
    home_toc = json.dumps([{
        'title': 'Wiki de Desenvolvimento', 'anchor': '#wiki-de-desenvolvimento',
        'children': [
            {'title': 'Atalhos rápidos', 'anchor': '#atalhos-rápidos', 'children': []},
            {'title': 'Como contribuir', 'anchor': '#como-contribuir', 'children': []},
        ]}], ensure_ascii=False)
    print('  home  conteúdo substituído pela grade de cards')
    if not DRY:
        cur.execute('update pages set content=?, render=?, toc=?, updatedAt=? where id=2',
                    (home, home_render, home_toc, NOW))

    # ---- 4. rebuild do pageTree -------------------------------------------
    if not DRY:
        rows = list(cur.execute(
            'select id, path, title, isPrivate, privateNS, localeCode from pages order by path'))
        nodes, order = {}, []
        for r in rows:
            parts = r['path'].split('/')
            for depth in range(1, len(parts) + 1):
                sub = '/'.join(parts[:depth])
                if sub not in nodes:
                    nodes[sub] = {
                        'path': sub, 'depth': depth, 'title': parts[depth - 1],
                        'isPrivate': 0, 'isFolder': 0, 'privateNS': None,
                        'pageId': None, 'localeCode': r['localeCode'],
                    }
                    order.append(sub)
            nodes[r['path']].update(
                title=r['title'], pageId=r['id'],
                isPrivate=r['isPrivate'], privateNS=r['privateNS'],
                localeCode=r['localeCode'])
        for sub in order:
            if any(o.startswith(sub + '/') for o in order):
                nodes[sub]['isFolder'] = 1

        order.sort()
        ids = {sub: i for i, sub in enumerate(order, start=1)}
        cur.execute('delete from pageTree')
        for sub in order:
            n = nodes[sub]
            parts = sub.split('/')
            ancestors = [ids['/'.join(parts[:d])] for d in range(1, len(parts))]
            cur.execute(
                'insert into pageTree (id, path, depth, title, isPrivate, isFolder, privateNS, '
                'parent, pageId, localeCode, ancestors) values (?,?,?,?,?,?,?,?,?,?,?)',
                (ids[sub], sub, n['depth'], n['title'], n['isPrivate'], n['isFolder'],
                 n['privateNS'], ancestors[-1] if ancestors else None, n['pageId'],
                 n['localeCode'], json.dumps(ancestors)))
        print(f'  tree  {len(order)} nós reconstruídos')

        # ---- 5. rebuild do pageLinks --------------------------------------
        import re
        cur.execute('delete from pageLinks')
        for r in cur.execute('select id, content, localeCode from pages').fetchall():
            seen = set()
            for m in re.findall(r'href="/([^"#?]+)"', r['content'] or ''):
                if m and m not in seen:
                    seen.add(m)
                    cur.execute(
                        'insert into pageLinks (pageId, path, localeCode) values (?,?,?)',
                        (r['id'], m, r['localeCode']))
        print('  links reconstruídos')

        # ---- 6. menu customizado (Main Menu) ------------------------------
        import uuid
        items = [{'id': str(uuid.uuid4()), 'icon': 'mdi-home', 'kind': 'link',
                  'label': 'Home Page', 'target': '/', 'targetType': 'home',
                  'visibilityMode': 'all', 'visibilityGroups': None},
                 {'id': str(uuid.uuid4()), 'kind': 'divider'},
                 {'id': str(uuid.uuid4()), 'kind': 'header', 'label': 'Documentação'}]
        for path, title, _desc, icon in FOLDERS:
            items.append({'id': str(uuid.uuid4()), 'icon': icon, 'kind': 'link',
                          'label': title, 'target': f'/{path}', 'targetType': 'page',
                          'visibilityMode': 'all', 'visibilityGroups': None})
        cur.execute('update navigation set config=? where key=?',
                    (json.dumps([{'locale': LOCALE, 'items': items},
                                 {'locale': 'en', 'items': items}], ensure_ascii=False), 'site'))
        print(f'  menu  {len(items)} itens no Main Menu')

        # ---- 7. Custom CSS ------------------------------------------------
        css = open(os.path.join(HERE, 'custom.css'), encoding='utf-8').read()
        theming = json.loads(cur.execute(
            "select value from settings where key='theming'").fetchone()[0])
        theming['injectCSS'] = css
        theming['darkMode'] = True
        cur.execute("update settings set value=?, updatedAt=? where key='theming'",
                    (json.dumps(theming, ensure_ascii=False), NOW))
        print(f'  css   {len(css)} bytes injetados no tema')

    if DRY:
        print('\n[dry-run] nada foi gravado.')
        con.rollback()
    else:
        con.commit()
        print('\nOK — commit efetuado.')
    con.close()


if __name__ == '__main__':
    main()
