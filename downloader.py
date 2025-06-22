import requests
import requests.adapters
import re
import os
import threading
import json
from multiprocessing.pool import ThreadPool
from tqdm import tqdm

BASE_URL = "https://danbooru.donmai.us"
PATH = "posts"
API_URL = f"{BASE_URL}/{PATH}"
TAG_LIST = [
    "mery_(yangmalgage)",
    "hyouka",
]
TAG_PARAMS = f"tags={"+".join(TAG_LIST)}"
req_url = f"{API_URL}?{TAG_PARAMS}"
CACHE_PAGE_URL_FILE = "./cache_page_urls.json"
CACHE_IMG_URL_FILE = "./cache_image_urls.json"
DOWNLOAD_PATH = "./downloads"

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning) # type: ignore

def crawl(url: str, pat: re.Pattern) -> list:
    try:
        resp = requests.request(
            method="GET",
            url=url,
            verify=False,
            timeout=10,
        )
        # 如果失败自动重试一次
        if resp.status_code != 200:
            resp = requests.request(
                method="GET",
                url=url,
                verify=False,
                timeout=10,
            )
    except Exception as e:
        print(f"请求失败 {url}: {str(e)}")
        return []
    respCode = resp.status_code
    if respCode != 200:
        print(f"请求失败，状态码：{respCode}")
        return []

    content = resp.text
    hrefs = re.findall(pat, content)
    return hrefs

list_file_lock = threading.Lock()
def dumpListToFile(dataList: list, fileName: str, firstWrite: bool = True) -> None:
    with list_file_lock:
        if firstWrite:
            if os.path.exists(fileName):
                os.remove(fileName)
            if not os.path.exists(os.path.dirname(fileName)):
                os.makedirs(os.path.dirname(fileName))
        if dataList is not None and dataList != []:
            with open(fileName, 'a', encoding='utf-8') as f:
                dataList = [item for item in dataList if item != '']
                f.seek(0)
                f.truncate()
                json.dump(dataList, f, ensure_ascii=False, indent=4)

def readJson(filePath: str) -> list:
    with open(filePath, 'r', encoding='utf-8') as jsonFile:
        jsonContent = json.load(jsonFile)
    return jsonContent if isinstance(jsonContent, list) else []

def fetch_page_urls(url: str) -> None:
    if not os.path.exists(CACHE_PAGE_URL_FILE):
        page_num_pattern = re.compile("<a class=\"paginator-page desktop-only\" href=\".*\">(.*?)</a>")
        page_list = crawl(url, page_num_pattern)
        page_num = int(page_list[-1]) if page_list and len(page_list) > 0 else 0

        image_page_links = []
        pool = ThreadPool(processes=3)
        href_pat = re.compile("<a class=\"post-preview-link\" draggable=\"false\" href=\"(.*?)\">")
        async_results = []
        for page in range(1, page_num + 1):
            page_url = f"{url}&page={page}"
            async_results.append(pool.apply_async(crawl, (page_url, href_pat)))

        for result in tqdm(async_results):
            image_page_links.extend(result.get())

        image_page_links = [f"{BASE_URL}{link}" for link in image_page_links]
        dumpListToFile(image_page_links, CACHE_PAGE_URL_FILE)

"""
<section class="image-container note-container blacklisted" data-id="7885265" data-tags="1girl arms_behind_back arms_up artist_logo bad_id bad_pixiv_id bikini black_hair blush breasts chitanda_eru cleavage commentary_request hand_up highres hyouka kamiyama_high_school_uniform_(hyouka) logo long_hair looking_at_viewer mery_(yangmalgage) midriff_peek multiple_views navel neckerchief pleated_skirt ponytail purple_eyes sailor_collar school_uniform serafuku short_sleeves skirt smile stomach stretching summer_uniform swimsuit wading white_background" data-rating="s" data-large-width="850" data-large-height="927" data-width="1319" data-height="1440" data-flags="" data-score="117" data-uploader-id="890672" data-source="https://i.pximg.net/img-original/img/2020/08/31/00/20/29/84048740_p16.png" data-normalized-source="https://www.pixiv.net/artworks/84048740" data-can-have-notes="true" data-file-url="https://cdn.donmai.us/original/f6/19/f619f501ca318c8aa81096172cf5da8b.png" style="--note-font-size: 155.17529411764707%;">      <picture>
        <source media="(max-width: 660px)" srcset="https://cdn.donmai.us/sample/f6/19/__chitanda_eru_hyouka_drawn_by_mery_yangmalgage__sample-f619f501ca318c8aa81096172cf5da8b.jpg">
        <img width="850" height="927" id="image" class="fit-width" alt="chitanda eru (hyouka) drawn by mery_(yangmalgage)" src="https://cdn.donmai.us/original/f6/19/__chitanda_eru_hyouka_drawn_by_mery_yangmalgage__f619f501ca318c8aa81096172cf5da8b.png" style="filter: blur(8px); width: 1319px; height: 1440px; animation: 0.5s ease 0s 1 normal forwards running sharpen;">
      </picture>

    <div id="note-preview"></div>
</section>
"""

def fetch_each_url_page() -> None:
    if not os.path.exists(CACHE_IMG_URL_FILE):
        url_list = readJson(CACHE_PAGE_URL_FILE)
        image_urls = []
        pool = ThreadPool(processes=5)
        img_pat = re.compile(r'<section .* data-file-url="(.*?)">.*?</section>', flags=re.S)

        async_results = []
        for url in url_list:
            async_results.append(pool.apply_async(crawl, (url, img_pat)))

        for result in tqdm(async_results):
            image_urls.extend(result.get())

        if image_urls:
            dumpListToFile(image_urls, CACHE_IMG_URL_FILE)

def download_images(url_list: list, output_dir: str = DOWNLOAD_PATH) -> None:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=20,
        pool_maxsize=20,
        max_retries=3
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    def download_file(url: str) -> None:
        try:
            filename = os.path.basename(url)
            filepath = os.path.join(output_dir, filename)

            if os.path.exists(filepath):
                return

            with session.get(url, stream=True, verify=False, timeout=10) as response:
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(8192):  # 增大chunk大小
                            f.write(chunk)
                else:
                    print(f"下载失败 {url}: HTTP {response.status_code}")
        except Exception as e:
            print(f"下载失败 {url}: {str(e)}")

    with ThreadPool(processes=5) as pool: # 增加线程数
        # 使用map替代imap确保并发执行
        results = pool.map(download_file, url_list)
        # 仍然使用tqdm显示进度
        for _ in tqdm(results, total=len(url_list)):
            pass

if __name__ == "__main__":
    fetch_page_urls(req_url)
    fetch_each_url_page()
    download_images(readJson(CACHE_IMG_URL_FILE))