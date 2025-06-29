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

# Do not make it too big or you'll get 403 err.
PAGE_FETCHING_THREADS = 3 # fetching data from pages
URL_FETCHING_THREADS = 5 # fetching data from urls

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
        print(f"Request fail {url}: {str(e)}")
        return []
    respCode = resp.status_code
    if respCode != 200:
        print(f"Request fail, status code：{respCode}")
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
                f.flush()

def readJson(filePath: str) -> list:
    with open(filePath, 'r', encoding='utf-8') as jsonFile:
        jsonContent = json.load(jsonFile)
    return jsonContent if isinstance(jsonContent, list) else []

def fetch_page_urls(url: str) -> None:
    if not os.path.exists(CACHE_PAGE_URL_FILE):
        print(f"{CACHE_PAGE_URL_FILE} not exists.")
        page_num_pattern = re.compile("<a class=\"paginator-page desktop-only\" href=\".*\">(.*?)</a>")
        page_list = crawl(url, page_num_pattern)
        page_num = int(page_list[-1]) if page_list and len(page_list) > 0 else 0

        image_page_links = []
        pool = ThreadPool(processes=PAGE_FETCHING_THREADS)
        href_pat = re.compile("<a class=\"post-preview-link\" draggable=\"false\" href=\"(.*?)\">")
        async_results = []
        # print(f"crawling image page url in result page range: {1}~{page_num}")
        for page in range(1, page_num + 1):
            page_url = f"{url}&page={page}"
            async_results.append(pool.apply_async(crawl, (page_url, href_pat)))

        for result in tqdm(async_results, desc="Crawling image page urls"):
            image_page_links.extend(result.get())

        image_page_links = [f"{BASE_URL}{link}" for link in image_page_links]
        print(f"{CACHE_PAGE_URL_FILE} url list cached.")
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
        print(f"{CACHE_IMG_URL_FILE} not exists.")
        url_list = readJson(CACHE_PAGE_URL_FILE)
        image_urls = []
        pool = ThreadPool(processes=URL_FETCHING_THREADS)
        img_pat = re.compile(r'<section .* data-file-url="(.*?)">.*?</section>', flags=re.S)

        async_results = []
        # print("crawling raw image urls.")
        for url in url_list:
            async_results.append(pool.apply_async(crawl, (url, img_pat)))

        for result in tqdm(async_results, desc="Crawling raw image urls"):
            image_urls.extend(result.get())

        if image_urls:
            dumpListToFile(image_urls, CACHE_IMG_URL_FILE)
            print(f"{CACHE_IMG_URL_FILE} img url list cached.")

def download_images(url_list: list, output_dir: str = DOWNLOAD_PATH) -> None:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    session = requests.Session()
    # 配置重试策略
    retries = requests.adapters.Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    def download_file(url: str) -> None:
        filename = os.path.basename(url)
        filepath = os.path.join(output_dir, filename)
        temp_filepath = filepath + ".part" # 使用临时文件后缀

        try:
            # 检查是否已完成下载（通过临时文件判断）
            if os.path.exists(filepath):
                print(f"The file already exists. Skip the download: {filename}")
                return

            headers = {}
            mode = 'wb'
            start_byte = 0

            # 尝试断点续传
            if os.path.exists(temp_filepath):
                start_byte = os.path.getsize(temp_filepath)
                headers = {'Range': f'bytes={start_byte}-'}
                mode = 'ab' # 追加写入模式
                print(f"Resume download: {filename} from byte {start_byte}")

            with session.get(url, stream=True, verify=False, timeout=30, headers=headers) as response:
                if response.status_code == 200: # 首次下载或服务器不支持Range
                    if start_byte > 0: # 如果之前有下载部分，但服务器不支持Range，则重新下载
                        start_byte = 0
                        mode = 'wb'
                        print(f"The server does not support resuming from breakpoint or re-downloading if the file has been updated: {filename}")

                elif response.status_code == 206: # 服务器支持断点续传
                    # 检查已下载部分是否完整且与服务器端文件长度一致
                    content_range = response.headers.get('Content-Range')
                    if content_range:
                        import re
                        match = re.match(r'bytes (\d+)-(\d+)/(\d+)', content_range)
                        if match:
                            range_start, range_end, total_size = map(int, match.groups())
                            if range_start != start_byte:
                                print(f"Warning: The starting byte of the request does not match the server response. Download again: {filename}")
                                start_byte = 0
                                mode = 'wb'
                            # 可以在这里进一步检查文件总大小，如果本地文件大小加上本次下载内容超过总大小，可能需要重新下载

                else:
                    print(f"Download fail {url}: HTTP {response.status_code}")
                    return

                # 打开或创建临时文件
                with open(temp_filepath, mode) as f:
                    for chunk in response.iter_content(8192):
                        if chunk: # 确保接收到的数据块不为空
                            f.write(chunk)
                            f.flush() # 强制刷新文件缓冲到磁盘

                # 下载完成后，重命名临时文件为正式文件
                os.rename(temp_filepath, filepath)
                # print(f"下载成功: {filename}")

        except requests.exceptions.RequestException as req_e:
            print(f"Download request err {url}: {req_e}")
            # 如果请求错误，临时文件会保留，以便下次继续下载
        except Exception as e:
            print(f"Download unknown err {url}: {str(e)}")
            # 发生其他错误时，临时文件也会保留

    with ThreadPool(processes=URL_FETCHING_THREADS) as pool:
        results = []
        # 使用map替代imap确保并发执行，并直接收集结果
        results = list(tqdm(pool.imap_unordered(download_file, url_list), total=len(url_list), desc="Downloading images"))
        # 仍然使用tqdm显示进度
        for _ in tqdm(results, total=len(url_list)):
            pass

if __name__ == "__main__":
    fetch_page_urls(req_url)
    fetch_each_url_page()
    download_images(readJson(CACHE_IMG_URL_FILE))