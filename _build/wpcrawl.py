#!/usr/bin/env python3
"""Polite crawler for a big WordPress site -> a mirror folder that wpstatic.py can finish.

usage: wpcrawl.py DOMAIN OUT [WORKERS]
- seeds: home, REST lists of posts/pages/categories/tags; follows internal links found on pages
  (pagination, date archives, author) but never feeds, wp-admin, wp-json, ?queries
- large inline scripts that are the same on every page (category/archive trees) are saved once
  as shared/<name>.js and replaced by a <script src> placeholder
- downloads the CSS/JS/images/fonts the pages use (srcset dropped: one picture size only)
"""
import concurrent.futures as cf, hashlib, json, os, re, sys, threading, time, urllib.parse, urllib.request

domain, out = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
root = 'https://' + domain
D = re.escape(domain)
UA = {'User-Agent': 'Mozilla/5.0 (static-copy for owner; Web project)'}
lock = threading.Lock()

def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.status, r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return e.code, b'', url
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    return 0, b'', url

def rest_links(kind):
    links, page = [], 1
    while True:
        st, body, _ = get('%s/wp-json/wp/v2/%s?per_page=100&page=%d&_fields=link' % (root, kind, page))
        if st != 200:
            break
        items = json.loads(body)
        if not items:
            break
        links += [i['link'] for i in items]
        page += 1
    return links

def norm(u):
    u = u.split('#')[0]
    if '?' in u:
        return None
    m = re.match(r'https?://(?:www\.)?' + D + r'(/.*)?$', u)
    if not m:
        return None
    p = m.group(1) or '/'
    if re.search(r'/(feed|wp-admin|wp-json|wp-content|wp-includes|embed|trackback|amp)(/|$)|\.(php|xml|txt|jpe?g|png|gif|webp|svg|pdf|mp3|mp4|zip|docx?)$', p, re.I):
        return None
    if not p.endswith('/'):
        p += '/'
    return p

TREE = re.compile(r"<script type='text/javascript'>\s*/\* <!\[CDATA\[ \*/\s*try\{\s*if\(document\.getElementById && document\.getElementById\('(\w+)'\).*?</script>", re.S)
shared = {}

def page_file(p):
    return os.path.join(out, urllib.parse.unquote(p).lstrip('/'), 'index.html')

assets = set()
ASSET = re.compile(r'''(?:src|href|data-src)=["'](https?://(?:www\.)?''' + D + r'''/wp-(?:content|includes)/[^"'\s>]+)''')
LINK = re.compile(r'''href=["'](https?://(?:www\.)?''' + D + r'''[^"'\s>]*)''')

def process(p):
    f = page_file(p)
    if os.path.exists(f):
        h = open(f, encoding='utf-8').read()
    else:
        st, body, final = get(root + p)
        if st != 200:
            return p, st, []
        h = body.decode('utf-8', 'replace')
        def tree(m):
            name = m.group(1)
            s = m.group(0)
            with lock:
                if name not in shared or len(s) > 20000:
                    shared.setdefault(name, s)
            if len(s) < 20000:
                return s
            return '<script src="%s/shared/%s.js"></script>' % (root, name)
        found_tree_links = set()
        for m in TREE.finditer(h):
            if len(m.group(0)) > 20000:
                found_tree_links.update(re.findall(r'https?:\\?/\\?/(?:www\.)?' + D + r'[^"\'\s<>]*', m.group(0)))
        h = TREE.sub(tree, h)
        h = re.sub(r'\s(?:srcset|sizes)=("[^"]*"|\'[^\']*\')', '', h)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, 'w', encoding='utf-8').write(h)
        if found_tree_links:
            with open(os.path.join(out, '.treelinks'), 'a') as t:
                t.write('\n'.join(l.replace('\\/', '/') for l in found_tree_links) + '\n')
    with lock:
        for a in ASSET.findall(h):
            assets.add(a)
    links = [norm(l) for l in LINK.findall(h)]
    return p, 200, [l for l in links if l]

def main():
    os.makedirs(out, exist_ok=True)
    seeds = {'/'}
    for kind in ('posts', 'pages', 'categories', 'tags'):
        for l in rest_links(kind):
            n = norm(l)
            if n:
                seeds.add(n)
    print('seeds', len(seeds), flush=True)
    seen, todo, fails, n = set(seeds), list(seeds), [], 0
    with cf.ThreadPoolExecutor(workers) as ex:
        while todo:
            batch, todo = todo, []
            for p, st, links in ex.map(process, batch):
                n += 1
                if st != 200:
                    fails.append((st, p))
                for l in links:
                    if l not in seen:
                        seen.add(l)
                        todo.append(l)
                if n % 200 == 0:
                    print('pages', n, 'queued', len(todo), flush=True)
    # tree links (categories/archives hidden in the shared scripts)
    tl = os.path.join(out, '.treelinks')
    extra = set()
    if os.path.exists(tl):
        extra = {norm(l) for l in open(tl).read().split()} - {None} - seen
    with cf.ThreadPoolExecutor(workers) as ex:
        for p, st, links in ex.map(process, sorted(extra)):
            if st != 200:
                fails.append((st, p))
    for name, s in shared.items():
        if len(s) > 20000:
            js = re.sub(r"^<script[^>]*>|</script>$", '', s.strip())
            os.makedirs(os.path.join(out, 'shared'), exist_ok=True)
            open(os.path.join(out, 'shared', name + '.js'), 'w', encoding='utf-8').write(js)
    print('pages done', n + len(extra), 'fails', len(fails), flush=True)
    json.dump(fails, open(os.path.join(out, '.fails.json'), 'w'))
    # assets
    def dl(a):
        u = a.split('#')[0]
        path = urllib.parse.unquote(urllib.parse.urlparse(u).path)
        f = os.path.join(out, path.lstrip('/'))
        if os.path.exists(f):
            return 0
        st, body, _ = get(u.split('?')[0] if not path.endswith('.css') else u)
        if st == 200:
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, 'wb').write(body)
            if f.endswith('.css'):
                for ref in re.findall(r'url\(\s*["\']?([^"\')]+)', body.decode('utf-8', 'replace')):
                    if ref.startswith('data:'):
                        continue
                    full = urllib.parse.urljoin(u, ref)
                    if re.match(r'https?://(?:www\.)?' + D + '/', full):
                        dl(full)
            return len(body)
        return 0
    al = sorted(assets)
    print('assets', len(al), flush=True)
    with cf.ThreadPoolExecutor(workers) as ex:
        total = sum(ex.map(dl, al))
    print('asset bytes', total, flush=True)

main()
