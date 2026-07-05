from curl_cffi import requests as curl_requests
import os
import threading
import time
from multiprocessing.pool import ThreadPool
from tqdm import tqdm


class DanbooruDownloader:
    """
    通过 Danbooru JSON API 批量下载图片。
    使用 curl_cffi 的 Chrome TLS 指纹绕过 Cloudflare 保护。
    """

    def __init__(
        self,
        lsTags: list,
        sDownloadRoot: str = "./downloads",
        iPageThreads: int = 3,
        iUrlThreads: int = 3,
    ):
        """

        :param lsTags: 要搜索的标签列表
        :param sDownloadRoot: 下载根目录（图片保存至 images/ 子目录）
        :param iPageThreads: 并发请求页数的线程数
        :param iUrlThreads: 并发下载图片的线程数
        """
        self.sBaseUrl = "https://danbooru.donmai.us"
        self.lsTags = lsTags
        self.sImageDownloadPath = os.path.join(sDownloadRoot, "images")
        os.makedirs(self.sImageDownloadPath, exist_ok=True)

        self.iPageFetchingThreads = iPageThreads
        self.iUrlFetchingThreads = iUrlThreads
        self.oFileLock = threading.Lock()
        self.dProgress = {"total": 0, "completed": 0, "description": "Idle"}
        self._bCancelled = False

        self.oSession = self._fnCreateSession()

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def _fnCreateSession(self):
        """创建 curl_cffi 会话，使用 Chrome TLS 指纹绕过 Cloudflare。"""
        oSession = curl_requests.Session(impersonate="chrome124")
        oSession.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://danbooru.donmai.us/",
        })
        return oSession

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def fnGetProgress(self) -> dict:
        """返回当前下载进度。"""
        return self.dProgress

    def fnCancel(self):
        """请求取消下载。"""
        self._bCancelled = True
        print("Cancellation requested...")

    def fnIsCancelled(self) -> bool:
        """返回是否已请求取消。"""
        return self._bCancelled

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def fnDownload(self):
        """启动下载流程：通过 JSON API 获取图片 URL 后下载。"""
        try:
            print("Starting download process...")
            self.dProgress["description"] = "Fetching image URLs via API..."
            lsAllFileUrls = self._fnFetchAllFileUrls()

            if self._bCancelled:
                print("Download cancelled after fetching URLs.")
                return

            self.dProgress["description"] = "Downloading images..."
            self._fnDownloadImages(lsAllFileUrls)

            if not self._bCancelled:
                print("\n--- Download Summary ---")
                print(f"Downloaded {len(lsAllFileUrls)} files.")
                print("Download process finished successfully.")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")

    # ------------------------------------------------------------------
    # JSON API 分页获取
    # ------------------------------------------------------------------

    def _fnFetchAllFileUrls(self) -> list:
        """通过 Danbooru JSON API 分页获取所有图片直链。"""
        all_file_urls = []
        page = 1
        limit = 200

        while True:
            api_url = (
                f"{self.sBaseUrl}/posts.json"
                f"?tags={'+'.join(self.lsTags)}"
                f"&page={page}&limit={limit}"
            )

            try:
                resp = self.oSession.get(api_url, verify=False, timeout=20)
                resp.raise_for_status()
                posts = resp.json()
            except Exception as e:
                print(f"API request failed (page {page}): {e}")
                break

            if not posts or not isinstance(posts, list):
                break

            for post in posts:
                file_url = post.get("file_url")
                if file_url:
                    all_file_urls.append(file_url)

            print(
                f"  Fetched page {page}: {len(posts)} posts, "
                f"{len(all_file_urls)} total URLs"
            )

            if self._bCancelled:
                break
            if len(posts) < limit:
                break

            page += 1
            time.sleep(1.0)

        print(f"Fetched {len(all_file_urls)} image URLs in total.")
        return all_file_urls

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------

    def _fnDownloadImages(self, lsImageUrls: list):
        """从 URL 列表并发下载所有图片。"""
        os.makedirs(self.sImageDownloadPath, exist_ok=True)

        urls_to_download = []
        for url in lsImageUrls:
            filename = os.path.basename(url)
            filepath = os.path.join(self.sImageDownloadPath, filename)
            if not os.path.exists(filepath):
                urls_to_download.append(url)

        print(
            f"Found {len(lsImageUrls)} total images. "
            f"{len(urls_to_download)} need to be downloaded."
        )

        self.dProgress["total"] = len(urls_to_download)
        self.dProgress["completed"] = 0

        if not urls_to_download:
            return

        with ThreadPool(processes=self.iUrlFetchingThreads) as oPool:
            list(
                tqdm(
                    oPool.imap_unordered(self._fnDownloadSingleFile, urls_to_download),
                    total=len(urls_to_download),
                    desc="Downloading images",
                )
            )

    def _fnDownloadSingleFile(self, sUrl: str):
        """下载单个文件，支持断点续传。超时/429 时自动重试。"""
        sFilename = os.path.basename(sUrl)
        sFilepath = os.path.join(self.sImageDownloadPath, sFilename)
        sTempFilepath = sFilepath + ".part"
        max_retries = 3
        success = False

        for attempt in range(max_retries):
            try:
                dHeaders = {}
                sMode = "wb"
                iStartByte = 0

                if os.path.exists(sTempFilepath):
                    iStartByte = os.path.getsize(sTempFilepath)
                    dHeaders["Range"] = f"bytes={iStartByte}-"
                    sMode = "ab"

                oResponse = self.oSession.get(
                    sUrl, stream=True, verify=False, timeout=30, headers=dHeaders
                )

                # 429 Too Many Requests — 指数退避等待后重试
                if oResponse.status_code == 429:
                    wait = 2 ** (attempt + 2)  # 4, 8, 16 seconds
                    print(f"  429 rate limited, waiting {wait}s: {sFilename}")
                    time.sleep(wait)
                    continue

                oResponse.raise_for_status()

                if oResponse.status_code == 200 and iStartByte > 0:
                    iStartByte = 0
                    sMode = "wb"

                with open(sTempFilepath, sMode) as f:
                    for chunk in oResponse.iter_content(8192):
                        if chunk:
                            f.write(chunk)

                os.rename(sTempFilepath, sFilepath)
                success = True
                break

            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 2)
                    print(f"  Error, retrying in {wait}s: {sFilename} - {e}")
                    time.sleep(wait)
                else:
                    print(f"Failed after {max_retries} retries: {sUrl} - {e}")

        if success:
            with self.oFileLock:
                self.dProgress["completed"] += 1
        # 限速：每次下载后间隔至少 0.3 秒
        time.sleep(0.3)


if __name__ == "__main__":
    # --- Configuration ---
    TAG_LIST = [
        "mery_(yangmalgage)",
        "hyouka",
    ]
    DOWNLOAD_PATH = "./downloads"

    # --- Execution ---
    oDownloader = DanbooruDownloader(
        lsTags=TAG_LIST, sDownloadRoot=DOWNLOAD_PATH,
        iPageThreads=5, iUrlThreads=10,
    )

    oDownloader.fnDownload()
