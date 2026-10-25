const { chromium } = require('playwright');
const [,, outdir, ...pairs] = process.argv;
(async () => {
  const b = await chromium.launch();
  for (const vp of [{n:'desk',w:1366,h:900},{n:'phone',w:390,h:844}]) {
    const ctx = await b.newContext({viewport:{width:vp.w,height:vp.h}});
    const p = await ctx.newPage();
    const bad = [];
    p.on('response', r => { if (r.status() >= 400 && r.url().includes('localhost')) bad.push(r.status()+' '+r.url()); });
    for (const pr of pairs) {
      const [name, url] = pr.split('=');
      try { await p.goto(url, {waitUntil:'networkidle', timeout:45000}); } catch(e) { console.log('timeout', url); }
      await p.waitForTimeout(800);
      await p.screenshot({path:`${outdir}/${name}-${vp.n}.png`, fullPage:false});
    }
    if (bad.length) console.log(vp.n, 'BROKEN:', [...new Set(bad)].join('\n'));
    await ctx.close();
  }
  await b.close();
})();
