# How this site is made (Web project)

Free static copy of mappingmyjourney.com (WordPress), address https://mappingmyjourney.github.io/MappingMyJourney/, hidden from search until move day.
Move day steps: MOVE-DAY.md. Settings: _build/site.env.

- Weekly refresh (.github/workflows/refresh.yml) runs _build/refresh.sh: copies WordPress again
  (KIND small = wget, big = wpcrawl.py), then wpstatic.py turns it into this static site.
- Go live (.github/workflows/golive.yml): same, for https://mappingmyjourney.com/, without the hidden note, writes CNAME.
- Check by hand: python3 _build/linkcheck.py .
