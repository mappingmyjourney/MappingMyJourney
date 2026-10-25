#!/bin/bash
# usage: smallsite.sh DOMAIN REPO   -> builds $S/srv/REPO from a wget mirror
set -e
S=/tmp/claude-0/-home-user/181e0847-a647-5c28-9780-64377768bf95/scratchpad
D=$1; R=$2; W=$S/src-$R; mkdir -p $W; cd $W
: > urls.txt
for sm in $(curl -sS https://$D/sitemap.xml | grep -oE "https://$D/[a-z_-]+-sitemap[0-9]*\.xml"); do curl -sS $sm | grep -oE "https://$D[^]<\"]*" | grep -v xsl >> urls.txt; done
for k in posts pages categories tags; do for pg in 1 2 3; do curl -sS "https://$D/wp-json/wp/v2/$k?per_page=100&page=$pg&_fields=link" | grep -oE 'https:[^"]+' | sed 's#\\##g' >> urls.txt || true; done; done
echo https://$D/ >> urls.txt; sort -u urls.txt -o urls.txt
rm -rf mirror
wget -q -e robots=off --page-requisites --convert-links --adjust-extension --no-host-directories -P mirror --domains=$D --span-hosts --reject-regex '(wp-admin|wp-json|xmlrpc|wp-login|/feed/|replytocom|\?p=|/embed/|oembed)' -i urls.txt || true
# second pass: archive pages linked from the first pass
grep -ohE "https://$D/(author|[0-9]{4}|category|tag|page)[^\"' )<]*/" -r --include=*.html mirror | grep -v /feed/ | sort -u > extra.txt || true
cat urls.txt extra.txt | sort -u > all.txt
if [ -s extra.txt ]; then rm -rf mirror; wget -q -e robots=off --page-requisites --convert-links --adjust-extension --no-host-directories -P mirror --domains=$D --span-hosts --reject-regex '(wp-admin|wp-json|xmlrpc|wp-login|/feed/|replytocom|\?p=|/embed/|oembed)' -i all.txt || true; fi
curl -sS "https://$D/wp-json/wp/v2/posts?per_page=100&_fields=link,title,excerpt,content" > posts.json
curl -sS "https://$D/wp-json/wp/v2/pages?per_page=100&_fields=link,title,excerpt,content" > pages.json
python3 -I $S/tools/wpstatic.py mirror $S/srv/$R $D https://aaasapp.github.io/$R/ posts.json pages.json
echo "urls $(wc -l < all.txt)  size $(du -sh $S/srv/$R | cut -f1)"
