"""Pone nuestra portada como miniatura del Short que Buffer acaba de publicar en YouTube.
Uso (desde propuestas-mar/):
  python -I yt_miniatura.py                # hoy (hora de Madrid): espera al Short, pone la portada y descarga la miniatura final
  python -I yt_miniatura.py --comprobar    # sin internet: revisa que cada día de portadas-youtube.txt tiene su portada y pesa < 2 MB
Necesita en el entorno YT_CLIENT_ID, YT_CLIENT_SECRET y YT_REFRESH_TOKEN (nunca se imprimen).
Deja la miniatura que devuelve YouTube en miniatura-yt-<fecha>.jpg para mirarla."""
import datetime, json, os, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
API = "https://www.googleapis.com/youtube/v3"
LIMITE = 2 * 1024 * 1024  # thumbnails.set no admite más de 2 MB


def portadas():
    d = {}
    for linea in open("portadas-youtube.txt", encoding="utf-8"):
        if linea.strip() and not linea.startswith("#"):
            fecha, ruta = linea.split()
            d[fecha] = ruta
    return d


def comprobar():
    d = portadas()
    for fecha, ruta in sorted(d.items()):
        assert os.path.isfile(ruta), f"{fecha}: falta {ruta}"
        assert os.path.getsize(ruta) < LIMITE, f"{fecha}: {ruta} pesa más de 2 MB"
    print(len(d), "portadas bien")


def pide(url, datos=None, cab=None, metodo=None):
    r = urllib.request.Request(url, data=datos, headers=cab or {}, method=metodo)
    with urllib.request.urlopen(r, timeout=60) as resp:
        return resp.read()


def token():
    datos = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                    "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    return json.loads(pide("https://oauth2.googleapis.com/token", datos))["access_token"]


def get(ruta, tk, **q):
    return json.loads(pide(f"{API}/{ruta}?{urllib.parse.urlencode(q)}", cab={"Authorization": f"Bearer {tk}"}))


def short_de_hoy(tk, desde):
    lista = get("channels", tk, part="contentDetails", mine="true")["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    for it in get("playlistItems", tk, part="contentDetails", playlistId=lista, maxResults=5)["items"]:
        pub = it["contentDetails"].get("videoPublishedAt")
        if pub and datetime.datetime.fromisoformat(pub.replace("Z", "+00:00")) >= desde:
            return it["contentDetails"]["videoId"]
    return None


def main():
    ahora = datetime.datetime.now(MADRID)
    fecha = ahora.strftime("%Y-%m-%d")
    portada = portadas().get(fecha)
    if not portada:
        sys.exit(f"{fecha}: no hay portada en portadas-youtube.txt")
    desde = ahora.replace(hour=20, minute=55, second=0, microsecond=0)  # Buffer publica a las 21:00
    tk, t_tk, vid = token(), time.time(), None
    fin = time.time() + 45 * 60  # Buffer suele tardar 3-5 min y YouTube en procesar unos minutos más
    while time.time() < fin:
        if time.time() - t_tk > 40 * 60:
            tk, t_tk = token(), time.time()  # el permiso dura 1 h
        vid = vid or short_de_hoy(tk, desde)
        if vid:
            v = get("videos", tk, part="snippet,status", id=vid)["items"][0]
            if v["status"]["uploadStatus"] == "processed":
                break
        time.sleep(20)
    else:
        sys.exit(f"{fecha}: el Short no apareció o no terminó de procesarse en 45 min (vídeo: {vid})")
    img = open(portada, "rb").read()
    tipo = "image/png" if portada.endswith(".png") else "image/jpeg"
    r = json.loads(pide(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media", img,
                        {"Authorization": f"Bearer {tk}", "Content-Type": tipo}, "POST"))
    url = max(r["items"][0].values(), key=lambda x: x.get("width", 0))["url"]
    time.sleep(30)  # YouTube tarda un poco en servir la miniatura nueva
    open(f"miniatura-yt-{fecha}.jpg", "wb").write(pide(url))
    print(f"{fecha}: «{v['snippet']['title']}» portada puesta en https://youtube.com/shorts/{vid} — miniatura descargada en miniatura-yt-{fecha}.jpg ({url})")


if __name__ == "__main__":
    comprobar() if "--comprobar" in sys.argv else main()
