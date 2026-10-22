from pathlib import Path
import urllib.request
target=Path(__file__).resolve().parents[1]/"landscope/static/vendor"
ASSETS={"https://unpkg.com/leaflet@1.9.4/dist/"+name:name for name in
        ("leaflet.js","leaflet.css","images/layers.png","images/layers-2x.png","images/marker-icon.png","images/marker-icon-2x.png","images/marker-shadow.png")}
# Poppins (SIL Open Font License) with latin-ext for Polish letters.
for weight in (400,500,600,700):
    for subset in ("latin","latin-ext"):
        name=f"poppins-{subset}-{weight}-normal.woff2"
        ASSETS[f"https://unpkg.com/@fontsource/poppins@5.1.0/files/{name}"]="fonts/"+name
for url,name in ASSETS.items():
    path=target/name
    path.parent.mkdir(parents=True,exist_ok=True)
    data=urllib.request.urlopen(url,timeout=45).read()
    if len(data)<100: raise RuntimeError("Niekompletny zasób: "+name)
    path.write_bytes(data)
    print(name,len(data))
