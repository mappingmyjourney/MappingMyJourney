#!/bin/bash
# Rebuild this site from its WordPress source (used by the weekly refresh and the Go-live button).
# usage: _build/refresh.sh DOMAIN BASE_URL MODE KIND
#   MODE: hidden (noindex, canonical = WordPress) | live (normal; on move day BASE_URL = https://DOMAIN/)
#   KIND: small (wget) | big (wpcrawl.py)
# Run from the repo root. Needs python3, wget, curl.
set -e
D=$1; BASE=$2; MODE=$3; KIND=$4
B=$(cd "$(dirname "$0")" && pwd); ROOT=$(pwd); W=$(mktemp -d)
cd "$W"
if [ "$KIND" = big ]; then
  python3 -I "$B/wpcrawl.py" "$D" "$W/mirror" 4
else
  : > urls.txt
  for sm in $(curl -sS "https://$D/sitemap.xml" | grep -oE "https://$D/[a-z_-]+-sitemap[0-9]*\.xml" || true); do curl -sS "$sm" | grep -oE "https://$D[^]<\"]*" | grep -v xsl >> urls.txt || true; done
  for k in posts pages categories tags; do for pg in 1 2 3; do curl -sS "https://$D/wp-json/wp/v2/$k?per_page=100&page=$pg&_fields=link" | grep -oE 'https:[^"]+' | sed 's#\\##g' >> urls.txt || true; done; done
  echo "https://$D/" >> urls.txt; sort -u urls.txt -o urls.txt
  WG=(wget -q -e robots=off --page-requisites --convert-links --adjust-extension --no-host-directories "--domains=$D" --span-hosts --reject-regex '(wp-admin|wp-json|xmlrpc|wp-login|/feed/|replytocom|\?p=|/embed/|oembed)')
  "${WG[@]}" -P mirror -i urls.txt || true
  grep -ohE "https://$D/(author|[0-9]{4}|category|tag|page)[^\"' )<]*/" -r --include=*.html mirror | grep -v /feed/ | sort -u > extra.txt || true
  cat urls.txt extra.txt | sort -u > all.txt
  if [ -s extra.txt ]; then rm -rf mirror; "${WG[@]}" -P mirror -i all.txt || true; fi
fi
# files WordPress loads only on demand (listed one path per line in _build/extra-files.txt)
for f in $(cat "$B/extra-files.txt" 2>/dev/null || true); do mkdir -p "mirror/$(dirname "$f")"; curl -sSf -o "mirror/$f" "https://$D/$f" || true; done
python3 -I - "$D" <<'P'
import json,sys,urllib.request
d=sys.argv[1]
for k in ('posts','pages'):
    out=[];p=1
    while True:
        try: j=json.load(urllib.request.urlopen(f'https://{d}/wp-json/wp/v2/{k}?per_page=100&page={p}&_fields=link,title,excerpt,content',timeout=120))
        except Exception: break
        if not j: break
        out+=j;p+=1
    json.dump(out,open(k+'.json','w'))
P
# safety: refuse to replace the site with an almost empty copy (WordPress down or blocking)
N=$(find mirror -name index.html | wc -l); OLD=$(find "$ROOT" -name index.html -not -path "$ROOT/.git/*" -not -path "$ROOT/_build/*" | wc -l)
if [ "$N" -lt $((OLD * 8 / 10)) ]; then echo "Only $N pages fetched (site has $OLD); keeping the current copy."; exit 1; fi
if [ "$MODE" = hidden ]; then export HIDDEN=1; else unset HIDDEN; fi
python3 -I "$B/wpstatic.py" mirror "$W/out" "$D" "$BASE" posts.json pages.json
# extra files kept across rebuilds: _build, CNAME, MOVE-DAY.md, .github, last-checked.txt, and anything listed in _build/keep.txt
cd "$ROOT"
KEEP="_build CNAME MOVE-DAY.md .github .git last-checked.txt $(cat _build/keep.txt 2>/dev/null || true)"
for f in $(ls -A); do case " $KEEP " in *" $f "*) ;; *) rm -rf "$f";; esac; done
cp -r "$W/out/." "$ROOT/"
python3 -I "$B/linkcheck.py" "$ROOT" | head -3
rm -rf "$W"
