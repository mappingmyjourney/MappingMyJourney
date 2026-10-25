import os,re,sys,urllib.parse
root=sys.argv[1]; bad={}
for d,_,fs in os.walk(root):
  for f in fs:
    if not f.endswith('.html') or f=='404.html': continue
    h=open(os.path.join(d,f),errors='replace').read()
    for u in re.findall(r'(?:href|src)=["\']([^"\'#]+)',h):
      if re.match(r'(https?:|mailto:|data:|image/||//|javascript:|tel:|\'\+)',u) or "'+" in u: continue
      p=os.path.normpath(os.path.join(d,urllib.parse.unquote(u.split('?')[0])))
      if os.path.isdir(p): p=os.path.join(p,'index.html')
      if not os.path.exists(p): bad.setdefault(u,os.path.relpath(os.path.join(d,f),root))
print('broken',len(bad))
for u,f in sorted(bad.items())[:15]: print(' ',u[:120],'<-',f[:80])
