# How this copy was made (Web project)

Free static copy of mappingmyjourney.com (WordPress), address /tmp/claude-0/-home-user/181e0847-a647-5c28-9780-64377768bf95/scratchpad/mmj. Hidden from search (noindex, canonical = the real site) until the name is moved here.

Big sites: `python3 -I wpcrawl.py mappingmyjourney.com mirror 4`; small sites: `smallsite.sh`. Then `HIDDEN=1 python3 -I wpstatic.py mirror OUT mappingmyjourney.com /tmp/claude-0/-home-user/181e0847-a647-5c28-9780-64377768bf95/scratchpad/mmj posts.json pages.json` (on move day drop HIDDEN=1 and use https://mappingmyjourney.com/ as the address). Check with linkcheck.py and shoot.js.
