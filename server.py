import os
import re
import json
import urllib.request

from urllib.error import URLError, HTTPError
from urllib.parse import unquote

from flask import Flask, request, render_template
from bs4 import BeautifulSoup
from waitress import serve

URL_REGEX = r"^https:\/\/(www|m).cda.pl\/video\/([^\/\s]+)"
HTTP_PROXY = os.environ.get("HTTP_PROXY")

# Init app
app = Flask(__name__, template_folder="")
app.config["SECRET_KEY"] = "#UqoQWUPB&n{:xo"
app.config["DEBUG"] = True


class FileDeletedError(Exception):
    """When video file has been deleted by the copyright owner or Administrator"""
    pass


class QualityError(Exception):
    """When selected by user quality does not exist"""
    pass


class PremiumOnlyError(Exception):
    """When video is only available for users with CDA Premium"""
    pass


def decrypt_file(a: str):
    b = []

    a = a.replace('_XDDD', '')
    a = a.replace('_CDA', '')
    a = a.replace('_ADC', '')

    for e in range(len(a)):
        f = ord(a[e])
        b.append(chr(33 + (f + 14) % 94) if 33 <= f and 126 >= f else chr(f))

    return "".join(b)


def extract_video(video_id: str, quality: str = None):
    url = "https://www.cda.pl/video/" + video_id + ("?wersja=" + quality if quality else "")

    # Trying to avoid as much trouble as possbile by "mocking" a real browser request
    request = urllib.request.Request(url, headers={
        "Referer": "http://www.cda.pl",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"
    })
    
    # Set proxy to avoid crappy CDNs
    if HTTP_PROXY:
        request.set_proxy(HTTP_PROXY, "http")

    try:
        response = urllib.request.urlopen(request).read()
    except HTTPError as e:
        response = e.read()
    except URLError as e:
        raise e

    # Parse HTML using BeautifulSoup4
    bs4 = BeautifulSoup(response, "html.parser")
    body = bs4.find("body")

    for tag in body.find_all(text=True):
        if tag.string == "Ten film jest dostępny dla użytkowników premium":
            raise PremiumOnlyError()
        elif tag.string == "Materiał został usunięty!":
            raise FileDeletedError()

    # Parse list of available video quality
    quality_list = [tag.string for tag in body.find_all("a", {"class": "quality-btn"})]

    if quality and quality not in quality_list:
        raise QualityError()

    title = body.find("span", {"class": "title-name"}).get_text()
    player_data = json.loads(body.find("div", {"player_data": True})["player_data"])

    return {
        "title": title,
        "src": "https://" + decrypt_file(unquote(player_data["video"]["file"])) + ".mp4"
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.values.get("url")
        quality = request.values.get("quality")

        if not url.startswith("https://www.cda.pl/video/"):
            render_template("index.html", error="Invalid link given.")

        # Grab video id from cda.pl url
        video_id = re.match(URL_REGEX, url)[2]

        try:
            video = extract_video(video_id, quality)
        except QualityError:
            video = extract_video(video_id)
        except PremiumOnlyError:
            return render_template("index.html", error="This video is only available for premium users with CDA Premium!")
        except FileDeletedError:
            return render_template("index.html", error="This video has been deleted by the copyright owner or Administrator!")
        except URLError as e:
            return render_template("index.html", error=e.reason)

        return render_template("index.html", video=video)
    else:
        return render_template("index.html")


if __name__ == "__main__":
    app.config["DEBUG"] = os.environ.get("DEBUG", "True").lower() in ("yes", "true", "t", "1")
    serve(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
