#!/usr/bin/env python3
"""
Aplica a reorganização do Wiki.js via GraphQL (mutations oficiais).

Uso:
    WIKIJS_TOKEN='<api key admin>' python3 apply_graphql.py [--dry-run]

Faz, nesta ordem:
  1. converte a Home para o editor `code` (o CKEditor destruiria o HTML dos cards)
  2. move/renomeia as páginas de conteúdo  (pages.update -> movePage)
  3. reescreve/move as páginas-índice e cria `apis` e `infraestrutura`
  4. substitui o conteúdo da Home pela grade de cards
  5. injeta o Custom CSS                    (theming.setConfig)
  6. popula o Main Menu em pt-br            (navigation.updateTree)
  7. rebuildTree + flushCache
"""
import json
import os
import re
import sqlite3
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply import FOLDERS, MOVES, INDEX_REUSE, LOCALE, render_index, DB, HERE  # noqa: E402

URL = os.environ.get('WIKIJS_URL', 'http://localhost:7778/graphql')
TOKEN = os.environ.get('WIKIJS_TOKEN', '')
DRY = '--dry-run' in sys.argv

if not TOKEN:
    sys.exit('Defina WIKIJS_TOKEN com uma API key do grupo Administrators.')


def gql(query, variables=None):
    body = json.dumps({'query': query, 'variables': variables or {}}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TOKEN}',
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if 'errors' in out:
        raise RuntimeError(json.dumps(out['errors'])[:400])
    return out['data']


def check(res, label):
    """Valida o responseResult padrão do Wiki.js."""
    node = res
    while isinstance(node, dict) and 'responseResult' not in node:
        node = next(iter(node.values()))
    rr = node['responseResult']
    if not rr['succeeded']:
        raise RuntimeError(f'{label}: [{rr["errorCode"]}] {rr["message"]}')
    return node


def norm_tags(raw):
    """'api, kong' (uma tag só) -> ['api','kong']"""
    out = []
    for t in raw:
        for part in re.split(r'[,\s]+', t):
            part = part.strip().lower()
            if part and part not in out:
                out.append(part)
    return out


# --- estado atual, direto do SQLite (conteúdo exato + tags) -----------------
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
PAGES = {r['id']: dict(r) for r in cur.execute(
    'select id, path, title, description, content, isPrivate, isPublished from pages')}
TAGS = {}
for r in cur.execute(
        'select pt.pageId, t.tag from pageTags pt join tags t on t.id = pt.tagId'):
    TAGS.setdefault(r['pageId'], []).append(r['tag'])
con.close()

UPDATE = '''mutation($id:Int!,$path:String!,$title:String!,$description:String!,
                     $content:String!,$tags:[String]!,$locale:String!){
  pages { update(id:$id, path:$path, title:$title, description:$description,
                 content:$content, tags:$tags, locale:$locale,
                 isPublished:true, isPrivate:false) {
    responseResult { succeeded errorCode message }
    page { id path title }
  } }
}'''

CREATE = '''mutation($path:String!,$title:String!,$description:String!,
                     $content:String!,$tags:[String]!,$locale:String!){
  pages { create(path:$path, title:$title, description:$description,
                 content:$content, tags:$tags, locale:$locale, editor:"code",
                 isPublished:true, isPrivate:false) {
    responseResult { succeeded errorCode message }
    page { id path title }
  } }
}'''


def do_update(pid, path, title, desc, content, tags):
    if DRY:
        print(f'  [dry] update #{pid:<3} {PAGES.get(pid, {}).get("path", "-"):<40} -> {path:<44} "{title}"')
        return
    r = gql(UPDATE, {'id': pid, 'path': path, 'title': title, 'description': desc,
                     'content': content, 'tags': tags, 'locale': LOCALE})
    check(r, f'update #{pid} {path}')
    src = PAGES.get(pid, {}).get('path', '-')
    print(f'  ok  update #{pid:<3} {src:<40} -> {path:<44} "{title}"')


def do_create(path, title, desc, content, tags):
    if DRY:
        print(f'  [dry] create      {"-":<40} -> {path:<44} "{title}"')
        return
    r = gql(CREATE, {'path': path, 'title': title, 'description': desc,
                     'content': content, 'tags': tags, 'locale': LOCALE})
    node = check(r, f'create {path}')
    print(f'  ok  create #{node["page"]["id"]:<3} {"-":<40} -> {path:<44} "{title}"')


def main():
    # -- 1. Home para o editor de código -----------------------------------
    print('\n[1] editor da Home -> code')
    if not DRY:
        r = gql('mutation{ pages { convert(id:2, editor:"code") { '
                'responseResult { succeeded errorCode message } } } }')
        try:
            check(r, 'convert home')
        except RuntimeError as e:
            if 'already using this editor' not in str(e):
                raise
            print('  --  já estava no editor `code`')
    print('  ok  pages.convert(id:2, editor:"code")')

    # -- 2. páginas de conteúdo (filhas primeiro) --------------------------
    print('\n[2] movendo e padronizando as páginas de conteúdo')
    for pid, (path, title, desc) in MOVES.items():
        if pid == 2:
            continue  # a Home é tratada no passo 4
        do_update(pid, path, title, desc, PAGES[pid]['content'],
                  norm_tags(TAGS.get(pid, [])))

    # -- 3. páginas-índice das pastas --------------------------------------
    print('\n[3] páginas-índice das pastas')
    children = {f[0]: [] for f in FOLDERS}
    for pid, (path, title, desc) in MOVES.items():
        if '/' in path:
            children[path.split('/')[0]].append((path, title, desc))
    for k in children:
        children[k].sort(key=lambda c: c[1].lower())

    by_path = {pg['path']: pid for pid, pg in PAGES.items()}
    for path, title, desc, _icon in FOLDERS:
        html = render_index(path, title, desc, children[path])
        # id histórico (1ª execução) ou o que já existe nesse path (re-execução)
        pid = INDEX_REUSE.get(path) or by_path.get(path)
        tags = [path, 'indice']   # tag da pasta, sem herdar tags antigas
        if pid:
            do_update(pid, path, title, desc, html, tags)
        else:
            do_create(path, title, desc, html, tags)

    # -- 4. Home Page -------------------------------------------------------
    print('\n[4] Home Page')
    home = open(os.path.join(HERE, 'home.html'), encoding='utf-8').read()
    hpath, htitle, hdesc = MOVES[2]
    do_update(2, hpath, htitle, hdesc, home, ['home', 'portal', 'indice'])

    # -- 5. Custom CSS ------------------------------------------------------
    print('\n[5] Custom CSS')
    css = open(os.path.join(HERE, 'custom.css'), encoding='utf-8').read()
    if not DRY:
        cfg = gql('{ theming { config { theme iconset darkMode tocPosition '
                  'injectHead injectBody } } }')['theming']['config']
        r = gql('''mutation($theme:String!,$iconset:String!,$darkMode:Boolean!,
                            $tocPosition:String,$injectCSS:String,
                            $injectHead:String,$injectBody:String){
          theming { setConfig(theme:$theme, iconset:$iconset, darkMode:$darkMode,
                              tocPosition:$tocPosition, injectCSS:$injectCSS,
                              injectHead:$injectHead, injectBody:$injectBody) {
            responseResult { succeeded errorCode message }
          } }
        }''', {'theme': cfg['theme'], 'iconset': cfg['iconset'], 'darkMode': True,
               'tocPosition': cfg['tocPosition'] or 'left', 'injectCSS': css,
               'injectHead': cfg['injectHead'] or '', 'injectBody': cfg['injectBody'] or ''})
        check(r, 'theming.setConfig')
    print(f'  ok  {len(css)} bytes de CSS injetados (darkMode=true)')

    # -- 6. Main Menu -------------------------------------------------------
    print('\n[6] Main Menu (pt-br)')
    import uuid
    items = [
        {'id': str(uuid.uuid4()), 'kind': 'link', 'label': 'Home Page',
         'icon': 'mdi-home', 'targetType': 'home', 'target': '/',
         'visibilityMode': 'all', 'visibilityGroups': []},
        {'id': str(uuid.uuid4()), 'kind': 'divider', 'label': '', 'icon': '',
         'targetType': 'none', 'target': '', 'visibilityMode': 'all', 'visibilityGroups': []},
        {'id': str(uuid.uuid4()), 'kind': 'header', 'label': 'Documentação', 'icon': '',
         'targetType': 'none', 'target': '', 'visibilityMode': 'all', 'visibilityGroups': []},
    ]
    for path, title, _desc, icon in FOLDERS:
        items.append({'id': str(uuid.uuid4()), 'kind': 'link', 'label': title,
                      'icon': icon, 'targetType': 'page', 'target': f'/{LOCALE}/{path}',
                      'visibilityMode': 'all', 'visibilityGroups': []})
    if not DRY:
        r = gql('''mutation($tree:[NavigationTreeInput]!){
          navigation { updateTree(tree:$tree) {
            responseResult { succeeded errorCode message } } }
        }''', {'tree': [{'locale': LOCALE, 'items': items},
                        {'locale': 'en', 'items': items}]})
        check(r, 'navigation.updateTree')
    print(f'  ok  {len(items)} itens ({len(FOLDERS)} pastas + Home)')

    # -- 7. rebuild -------------------------------------------------------
    print('\n[7] rebuild')
    if not DRY:
        for m in ('rebuildTree', 'flushCache'):
            r = gql('mutation{ pages { %s { responseResult { succeeded errorCode message } } } }' % m)
            check(r, m)
            print(f'  ok  pages.{m}')

    print('\nConcluído.' if not DRY else '\n[dry-run] nada foi enviado.')


if __name__ == '__main__':
    main()
