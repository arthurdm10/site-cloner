import requests
from bs4 import BeautifulSoup
from tldextract import extract
from os import path, makedirs
from pathlib import Path
import argparse
import threading
import validators
import time


argparser = argparse.ArgumentParser("python main.py --host http://hosturl.com --output path/to/output")

argparser.add_argument("--host", action="store", dest="host",
                       required=True,
                       help="Site to be cloned")

argparser.add_argument("--output", action="store", dest="output_path",
                       required=True,
                       help="Path where files will be saved")

args = argparser.parse_args()


BASE_PATH = args.output_path

init_url = None
site_path = None

urls = {"css": [],
        "js": [],
        "imgs": [],
        "pages": []}
lock = threading.Lock()
lock_print = threading.Lock()
lock_path = threading.Lock()


def get_file_path(url: str) -> tuple:

    split = url.split("/")
    file_name = split[-1] if len(split) > 3 else "index.html"
    file_path = "/".join(split[3:-1])

    if file_name == "":
        file_name = "index.html"

    if Path(file_name).suffix == "":
        file_name += ".html"

    return file_path, file_name.split("?")[0]


tags_config = {"css": ("link", {"rel": "stylesheet"}, "href"),
               "js": ("script", {}, "src"),
               "preload": ("link", {"rel": "preload"}, "href"),
               "pages": ("a", {}, "href"),
               "imgs": ("img", {}, "src")}

total_downloaded = 0

MAX_THREAD = 200


def get_page_urls(url: str, domain):
    try:
        html = requests.get(url).content
        parser = BeautifulSoup(html, "html.parser")
    except Exception as err:
        print(err)
    else:
        for key, config in tags_config.items():
            items = parser.find_all(config[0], config[1])

            for item in items:
                src = item.get(config[2])

                if src is not None:
                    if not validators.url(src) and len(src) > 1 and src[0] != "#":
                        global init_url
                        src = init_url + "/" + src if src[0] != "/" else init_url + src

                    url_info = extract(src)

                    if url_info.domain == domain:
                        if src not in urls[key]:

                            if url_info.subdomain != "www" and url_info.subdomain != "":
                                # skip subdomain pages
                                continue

                            urls[key].append(src)

                            while threading.active_count() >= MAX_THREAD:
                                time.sleep(0.5)

                            th_download = threading.Thread(target=thread_download, args=(src,),daemon=False)
                            th_download.start()

                            if key == "pages":
                                while threading.active_count() >= MAX_THREAD:
                                    time.sleep(0.5)

                                th_get_url = threading.Thread(target=get_page_urls, args=(src, domain,),daemon=False)
                                th_get_url.start()


def thread_download(url: str):
    global site_path
    file_path, filename = get_file_path(url)

    file_path = site_path + "\\" + file_path

    lock_path.acquire()
    if not path.exists(file_path):
        makedirs(file_path)
    lock_path.release()

    file_path += "\\" + filename

    lock_path.acquire()
    if not path.exists(file_path):
        try:
            global total_downloaded

            file = open(file_path, "wb")
            lock_path.release()

            req = requests.get(url, stream=True)

            if req.status_code == 200:
                print("[!!]Downloading ", url)

                file.write(req.content)
                for data in req.iter_content(chunk_size=1024):
                    if data:
                        file.write(data)

                lock.acquire()
                total_downloaded += len(req.content)
                lock.release()
        except Exception as err:
            lock_path.release()
    else:
        lock_path.release()


def main():
    global site_path
    global init_url
    if not validators.url(args.host):
        print("Invalid host")
        return

    init_url = args.host

    urls["pages"].append(init_url)

    domain = extract(init_url).domain

    site_path = BASE_PATH + "\\" + domain

    if not path.exists(BASE_PATH + "\\" + domain):
        makedirs(site_path)

    th_get_url = threading.Thread(target=get_page_urls, args=(init_url, domain, ), daemon=False)
    th_get_url.start()

    th_get_url.join()

    while threading.active_count() > 1:
        time.sleep(1)

    print("Done")
    print("Total downloaded: {} bytes".format(total_downloaded))


main()
