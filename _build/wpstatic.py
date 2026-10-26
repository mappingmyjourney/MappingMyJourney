#!/usr/bin/env python3
"""Turn a wget mirror of a WordPress site into a clean static site for GitHub Pages.

usage: wpstatic.py MIRROR OUT DOMAIN BASE_URL POSTS_JSON PAGES_JSON
  BASE_URL is the new public address, ending in "/" (e.g. https://aaasapp.github.io/forthegoodhearts/)
  HIDDEN=1 in the environment: the copy stays out of search (noindex) and its canonical
  links name the real site (https://DOMAIN/...), for use while WordPress still serves the name.
"""
import html, json, os, posixpath, re, shutil, sys, urllib.parse
from datetime import datetime, timezone

src, out, domain, base, posts_json, pages_json = sys.argv[1:7]
HIDDEN = os.environ.get('HIDDEN') == '1'
dom = re.escape(domain)
ABS = re.compile(r'https?://(?:www\.)?' + dom + r'(/[^"\'\s)<>]*)?')
ABS_ESC = re.compile(r'https?:\\/\\/(?:www\\.)?' + dom.replace('\\.', '\\\\?\\.'))

if os.path.exists(out):
    shutil.rmtree(out)
shutil.copytree(src, out)

# 1. files saved with "?ver=..." in the name -> plain names
for root, dirs, files in os.walk(out):
    for f in files:
        if '?' in f:
            new = f.split('?', 1)[0]
            dst = os.path.join(root, new)
            if not os.path.exists(dst):
                os.rename(os.path.join(root, f), dst)
            else:
                os.remove(os.path.join(root, f))

QREF = re.compile(r'(\.[A-Za-z0-9]{1,5})%3F[^"\'\s)>]*')

def rel(from_file, target):
    """relative link from a file in OUT to a path in OUT (target relative to OUT root)"""
    d = posixpath.dirname(posixpath.relpath(from_file, out).replace(os.sep, '/'))
    r = posixpath.relpath(target or '.', d or '.')
    return r

def target_for(path):
    """map a site path (/about/) to a file in OUT, or None"""
    p = urllib.parse.unquote((path or '/').split('#')[0].split('?')[0])
    cands = [p.lstrip('/')]
    if p.endswith('/') or p == '':
        cands = [(p.lstrip('/') + 'index.html')]
    for c in cands:
        if os.path.isfile(os.path.join(out, c)):
            return c
    return None

DROP_HEAD = [
    re.compile(r'<link[^>]+rel=["\'](?:EditURI|pingback|shortlink|https://api\.w\.org/|alternate)["\'][^>]*>\s*', re.I),
    re.compile(r'<link[^>]+(?:wp-json|xmlrpc|/feed/|oembed)[^>]*>\s*', re.I),
    re.compile(r'<script[^>]*>(?:(?!</script>).)*?_wpemojiSettings.*?</script>\s*', re.S),
    re.compile(r'<script[^>]+wp-emoji[^>]*></script>\s*'),
    re.compile(r'<script id="wp-emoji-settings"[^>]*>.*?</script>\s*', re.S),
]
RESPOND = re.compile(r'<div id="respond" class="comment-respond">.*?</div><!-- #respond -->', re.S)

# values WordPress changes on every visit (security codes, cache stamps): fixed, so a weekly
# refresh only changes pages whose content really changed
VOLATILE = [
    (re.compile(r'(name=["\']_wpnonce["\'] value=["\'])[0-9a-f]+'), r'\1'),
    (re.compile(r'(_wpnonce=)[0-9a-f]{10}'), r'\1'),
    (re.compile(r'("(?:\w*_)?nonce"\s*:\s*")[0-9a-f]{10}(")'), r'\1\2'),
    (re.compile(r"(id='like-post-wrapper-\d+-\d+)-[0-9a-f]+'"), r"\1'"),
    (re.compile(r'(stats\.wp\.com/e-)\d{6}(\.js)'), r'\g<1>000000\2'),
    (re.compile(r'(\?ver=|#ver=)20\d{6}\b'), r'\g<1>0'),
    (re.compile(r'<!-- Page (?:cached|optimized|uncached) by LiteSpeed[^>]*-->'), ''),
    (re.compile(r'((?:obj_id=|like-post-frame-)\d+-\d+)-[0-9a-f]{13}'), r'\1'),
    (re.compile(r'(wp-embed-share-tab-(?:wordpress|html)-\d+)-\d+'), r'\1'),
]

def fix_html(fp, h):
    for rx, rep in VOLATILE:
        h = rx.sub(rep, h)
    h = QREF.sub(r'\1', h)
    for rx in DROP_HEAD:
        h = rx.sub('', h)
    h = RESPOND.sub('', h)
    # canonical / og / JSON-LD keep absolute, on the new address
    def canon(m):
        return m.group(0).replace(m.group(1), base.rstrip('/'))
    h = re.sub(r'<link rel="canonical" href="(https?://(?:www\.)?' + dom + r')', canon, h)
    h = re.sub(r'<meta property="og:url" content="(https?://(?:www\.)?' + dom + r')', canon, h)
    h = re.sub(r'(<script type="application/ld\+json"[^>]*>)(.*?)(</script>)',
               lambda m: m.group(1) + ABS_ESC.sub(base.rstrip('/').replace('/', '\\/'),
                                                  ABS.sub(lambda a: base.rstrip('/') + (a.group(1) or '/'), m.group(2))) + m.group(3),
               h, flags=re.S)
    # remaining absolute links: relative when we have the page/file, otherwise the new address
    def absfix(path):
        path = path or '/'
        t = target_for(path)
        if t:
            frag = '#' + path.split('#', 1)[1] if '#' in path else ''
            return rel(fp, t) + frag
        return base.rstrip('/') + path
    h = re.sub(r'((?:href|src|action|content)=["\'])https?://(?:www\.)?' + dom + r'(/[^"\'\s<>]*)?',
               lambda m: m.group(1) + absfix(m.group(2)), h)
    h = ABS_ESC.sub(base.rstrip('/').replace('/', '\\/'), h)
    h = re.sub(r'(/\*# sourceURL=)https?://(?:www\.)?' + dom, r'\1', h)
    # clean addresses: about/index.html -> about/
    h = re.sub(r'(href=["\'])((?:\.\./)*)index\.html(["\'#])', lambda m: m.group(1) + (m.group(2) or './') + m.group(3), h)
    h = re.sub(r'(href=["\'])([^"\'#:]*?/)index\.html(["\'#])', r'\1\2\3', h)
    # theme top-bar date was frozen by the page cache: show today's date instead
    h = re.sub(r'(<span class="ml-5">)(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day-[A-Z][a-z]+ \d{1,2}, \d{4}(</span>)',
               r'''\1<script>(function(d){document.write(d.toLocaleDateString('en-US',{weekday:'long'})+'-'+d.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}))})(new Date())</script>\2''', h)
    # site search -> static search page
    h = re.sub(r'(<form[^>]*(?:class="[^"]*search-form|class="[^"]*wp-block-search|role="search")[^>]*action=")[^"]*(")',
               lambda m: m.group(1) + rel(fp, 'search/') + '/' + m.group(2), h)
    page = posixpath.relpath(posixpath.dirname(posixpath.relpath(fp, out).replace(os.sep, '/')) or '.', '.')
    if not HIDDEN and os.path.basename(fp) == 'index.html':
        own = base + ('' if page == '.' else urllib.parse.quote(page) + '/')
        h = re.sub(r'<link rel=["\']canonical["\'][^>]*>', '<link rel="canonical" href="%s" />' % own, h, count=1)
    if HIDDEN:
        real = 'https://%s/%s' % (domain, '' if page == '.' else page + '/')
        h = re.sub(r'<link rel=["\']canonical["\'][^>]*>\s*', '', h)
        h = re.sub(r'<meta name=["\']robots["\'][^>]*>\s*', '', h)
        h = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + real, h)
        h = re.sub(r'(<head(?:\s[^>]*)?>)', lambda m: m.group(1) + '\n<meta name="robots" content="noindex, follow">\n<link rel="canonical" href="%s">' % real, h, count=1)
    return h

pages = []
for root, dirs, files in os.walk(out):
    for f in files:
        fp = os.path.join(root, f)
        if f.endswith('.html'):
            h = open(fp, encoding='utf-8', errors='replace').read()
            open(fp, 'w', encoding='utf-8').write(fix_html(fp, h))
            if f == 'index.html':
                pages.append(posixpath.relpath(root, out).replace(os.sep, '/'))
        elif f.endswith('.js') and os.path.basename(root) == 'shared':
            # shared tree scripts (wpcrawl.py): links are absolute, point them at the new address
            h = open(fp, encoding='utf-8').read()
            h = ABS_ESC.sub(base.rstrip('/').replace('/', '\\/'), h)
            h = ABS.sub(lambda a: base.rstrip('/') + (a.group(1) or '/'), h)
            open(fp, 'w', encoding='utf-8').write(h)
        elif f.endswith('.css'):
            h = open(fp, encoding='utf-8', errors='replace').read()
            h2 = QREF.sub(r'\1', h)
            if h2 != h:
                open(fp, 'w', encoding='utf-8').write(h2)

# 2. search index from the WordPress feed data
def text(s):
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()

idx = []
for fn in (posts_json, pages_json):
    for it in json.load(open(fn)):
        path = ABS.match(it['link']).group(1) or '/'
        if not target_for(path):
            continue
        idx.append({'t': text(it['title']['rendered']), 'u': path.lstrip('/'),
                    'e': text(it.get('excerpt', {}).get('rendered', ''))[:220],
                    'x': text(it['content']['rendered'])})
os.makedirs(os.path.join(out, 'search'), exist_ok=True)
json.dump(idx, open(os.path.join(out, 'search', 'index.json'), 'w'), ensure_ascii=False)

SEARCH_BODY = '''<article class="page type-page hentry">
	<header class="entry-header"><h2 class="entry-title">Search</h2></header>
	<div class="entry-content">
		<form role="search" class="search-form" onsubmit="return false"><label><span class="screen-reader-text">Search for:</span>
		<input type="search" id="q" class="search-field" placeholder="Search &hellip;" name="s" autofocus></label></form>
		<div id="results" style="margin-top:1.5em"></div>
	</div>
<script>
(function(){
  var q=document.getElementById('q'),out=document.getElementById('results'),data=[];
  var p=new URLSearchParams(location.search).get('s')||'';q.value=p;
  function esc(s){return s.replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function run(){
    var w=q.value.toLowerCase().split(/\\s+/).filter(Boolean);
    if(!w.length){out.innerHTML='';return}
    var hits=data.filter(function(d){var s=(d.t+' '+d.x).toLowerCase();return w.every(function(x){return s.indexOf(x)>-1})});
    out.innerHTML=hits.length?hits.map(function(d){return '<div style="margin-bottom:1.4em"><h3 style="margin:0 0 .3em"><a href="../'+d.u+'">'+esc(d.t)+'</a></h3><p style="margin:0">'+esc(d.e||d.x.slice(0,200))+'</p></div>'}).join(''):'<p>Nothing found. Please try other words.</p>';
  }
  fetch('index.json').then(function(r){return r.json()}).then(function(j){data=j;run()});
  q.addEventListener('input',run);
})();
</script>
</article>'''

ART = re.compile(r'<article id="post-\d+".*?</article><!-- #post-\d+ -->', re.S)
tpl_file = next((os.path.join(out, c, 'index.html') for c in ('blog', 'about', 'contact')
                 if os.path.isfile(os.path.join(out, c, 'index.html'))), None)
if tpl_file:
    t = open(tpl_file, encoding='utf-8').read()
    t = ART.sub(lambda m: SEARCH_BODY, t, count=1)
    t = re.sub(r'\s(?:current-menu-item|current_page_item|current-page-ancestor)\b', '', t)
    t = t.replace(' aria-current="page"', '')
    t = re.sub(r'<title>.*?</title>', lambda m: '<title>Search - ' + m.group(0)[7:-8].split(' - ')[-1] + '</title>', t, count=1, flags=re.S)
    t = re.sub(r'<li class="breadcrumb-item fff">[^<]*</li>', '<li class="breadcrumb-item fff">Search</li>', t)
    open(os.path.join(out, 'search', 'index.html'), 'w', encoding='utf-8').write(t)

    # 3. 404 page (served for any missing address, so it uses a <base>)
    nf = t.replace('<h2 class="entry-title">Search</h2>', '<h2 class="entry-title">Page not found</h2>')
    nf = nf.replace('<div id="results"', '<p>Sorry, this page is not here. Try a search, or go to the <a href="./">home page</a>.</p><div id="results"')
    nf = nf.replace("fetch('index.json')", "fetch('search/index.json')").replace("'<a href=\"../'+d.u", "'<a href=\"'+d.u")
    nf = re.sub(r'((?:href|src)=["\'])\.\./', r'\1', nf)
    nf = re.sub(r'<li class="breadcrumb-item fff">[^<]*</li>', '<li class="breadcrumb-item fff">Not found</li>', nf)
    nf = re.sub(r'(<head(?:\s[^>]*)?>)', lambda m: m.group(1) + '\n<base href="' + base + '">', nf, count=1)
    open(os.path.join(out, '404.html'), 'w', encoding='utf-8').write(nf)

# 4. sitemap, robots, .nojekyll
now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
urls = sorted(p for p in pages if p != 'search')
if HIDDEN:
    urls = []  # no sitemap while hidden
with open(os.path.join(out, 'sitemap.xml'), 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    for p in urls:
        f.write('  <url><loc>%s%s</loc><lastmod>%s</lastmod></url>\n' % (base, '' if p == '.' else p + '/', now))
    f.write('</urlset>\n')
open(os.path.join(out, 'robots.txt'), 'w').write('User-agent: *\nAllow: /\n' + ('' if HIDDEN else 'Sitemap: %ssitemap.xml\n' % base))
open(os.path.join(out, '.nojekyll'), 'w').close()
print('pages', len(pages), 'search items', len(idx), 'hidden' if HIDDEN else '')
