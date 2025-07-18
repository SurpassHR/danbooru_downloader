import requests
import requests.adapters
import re
import os
import threading
import json
import signal
import atexit
from multiprocessing.pool import ThreadPool
from tqdm import tqdm
import urllib3


class DanbooruDownloader:
    """
    A robust class to download images from Danbooru based on tags.
    It features incremental writing, resumption, intelligent caching,
    and graceful shutdown to prevent data loss.
    """

    def __init__(
        self,
        lsTags: list,
        sDownloadRoot: str = "./downloads",
        iPageThreads: int = 3,
        iUrlThreads: int = 3,
        iBatchSize: int = 50,
    ):
        """
        Initializes the downloader with enhanced configuration.

        :param lsTags: A list of tags to search for.
        :param sDownloadRoot: The root directory for downloads and cache.
        :param iPageThreads: Number of threads for fetching page URLs.
        :param iUrlThreads: Number of threads for fetching image URLs and downloading.
        :param iBatchSize: Number of URLs to batch before writing to cache.
        """
        # --- Basic Configuration ---
        self.sBaseUrl = "https://danbooru.donmai.us"
        self.sApiUrl = f"{self.sBaseUrl}/posts"
        self.lsTags = lsTags
        self.sTagParams = f"tags={'+'.join(self.lsTags)}"
        self.sRequestUrl = f"{self.sApiUrl}?{self.sTagParams}"
        self.iBatchSize = iBatchSize

        # --- Paths (using .jsonl for incremental writing) ---
        self.sCacheDir = os.path.join(sDownloadRoot, "cache")
        self.sPageUrlCacheFile = os.path.join(self.sCacheDir, "cache_page_urls.jsonl")
        self.sImageUrlCacheFile = os.path.join(self.sCacheDir, "cache_image_map.jsonl")  # Renamed for clarity
        self.sImageDownloadPath = os.path.join(sDownloadRoot, "images")
        os.makedirs(self.sCacheDir, exist_ok=True)

        # --- Threading and Session ---
        self.iPageFetchingThreads = iPageThreads
        self.iUrlFetchingThreads = iUrlThreads
        self.oSession = self._fnCreateSession()

        # --- State Management for Resumption and Progress ---
        self.oFileLock = threading.Lock()
        self.dProgress = {"total": 0, "completed": 0, "description": "Idle"}
        self.lsPageUrlBatch = []
        self.lsImageUrlMapBatch = []  # Stores {"post_page_url": ..., "direct_image_url": ...}
        self.iNewPageUrlsCount = 0
        self.iNewImageUrlsCount = 0

        # --- Load existing data for deduplication ---
        self.setExistingPageUrls = self._fnReadJsonlAsSet(self.sPageUrlCacheFile)
        self.dictExistingImageUrlMap = self._fnReadJsonlAsMap(self.sImageUrlCacheFile)
        print(f"Loaded {len(self.setExistingPageUrls)} existing page URLs from cache.")
        print(f"Loaded {len(self.dictExistingImageUrlMap)} existing image URL mappings from cache.")

        # --- Graceful Shutdown ---
        signal.signal(signal.SIGINT, self._fnSignalHandler)
        signal.signal(signal.SIGTERM, self._fnSignalHandler)
        atexit.register(self._fnCleanup)

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _fnCreateSession(self) -> requests.Session:
        """
        Creates a requests session with a robust retry strategy that handles
        rate limiting (429) and server errors (5xx).
        """
        oSession = requests.Session()
        oRetries = requests.adapters.Retry(
            total=5,
            backoff_factor=1,  # Increase backoff for more graceful retries
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        oAdapter = requests.adapters.HTTPAdapter(max_retries=oRetries)
        oSession.mount("https://", oAdapter)
        oSession.mount("http://", oAdapter)
        return oSession

    def _fnSignalHandler(self, signum, frame):
        """Handles termination signals to ensure data is saved."""
        print(f"\nSignal {signum} received. Cleaning up before exit...")
        self._fnCleanup()
        exit(0)

    def _fnCleanup(self):
        """Writes any remaining URLs in batches to the cache files."""
        print("Performing cleanup, writing remaining URLs to cache...")
        if self.lsPageUrlBatch:
            self._fnAppendJsonlFromList(self.lsPageUrlBatch, self.sPageUrlCacheFile)
            self.lsPageUrlBatch.clear()
        if self.lsImageUrlMapBatch:
            self._fnAppendJsonlFromListOfDicts(self.lsImageUrlMapBatch, self.sImageUrlCacheFile)
            self.lsImageUrlMapBatch.clear()
        print("Cleanup finished.")

    def fnGetProgress(self) -> dict:
        """Returns the current download progress."""
        return self.dProgress

    def fnDownload(self):
        """Starts the download process with robust error handling and resumption."""
        try:
            print("Starting download process...")
            self.dProgress["description"] = "Fetching post page URLs..."
            lsAllPostPageUrls = self._fnFetchPostPageUrls()

            self.dProgress["description"] = "Fetching direct image URLs..."
            dictAllImageUrls = self._fnFetchImageUrls(lsAllPostPageUrls)

            self.dProgress["description"] = "Downloading images..."
            # We pass the values (direct image URLs) of the map to the downloader
            self._fnDownloadImages(list(dictAllImageUrls.values()))

            print("\n--- Download Summary ---")
            print(f"Added {self.iNewPageUrlsCount} new page URLs.")
            print(f"Added {self.iNewImageUrlsCount} new image URL mappings.")
            print("Download process finished successfully.")

        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")
        finally:
            # The atexit handler will call _fnCleanup, ensuring data is saved.
            pass

    # --- Private Helper Methods ---

    def _fnCrawl(self, sUrl: str, oPattern: re.Pattern) -> list:
        """Crawls a URL using the shared session."""
        try:
            oResp = self.oSession.get(sUrl, verify=False, timeout=20)
            oResp.raise_for_status()
            sContent = oResp.text
            return re.findall(oPattern, sContent)
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {sUrl}: {str(e)}")
            return []

    def _fnAppendJsonlFromList(self, lsData: list, sFilePath: str):
        """Appends a list of strings to a .jsonl file, one per line."""
        with self.oFileLock:
            try:
                with open(sFilePath, "a", encoding="utf-8") as f:
                    for item in lsData:
                        f.write(str(item) + "\n")
                print(f"Appended {len(lsData)} URLs to {sFilePath}")
            except IOError as e:
                print(f"Error writing to {sFilePath}: {e}")

    def _fnAppendJsonlFromListOfDicts(self, lsDictData: list, sFilePath: str):
        """Appends a list of dictionaries to a .jsonl file, one JSON object per line."""
        with self.oFileLock:
            try:
                with open(sFilePath, "a", encoding="utf-8") as f:
                    for item in lsDictData:
                        f.write(json.dumps(item) + "\n")
                print(f"Appended {len(lsDictData)} URL mappings to {sFilePath}")
            except IOError as e:
                print(f"Error writing to {sFilePath}: {e}")

    def _fnReadJsonlAsSet(self, sFilePath: str) -> set:
        """Reads a .jsonl file line by line into a set for efficient lookup."""
        resultSet = set()
        if not os.path.exists(sFilePath):
            return resultSet
        try:
            with open(sFilePath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        resultSet.add(line)
        except IOError as e:
            print(f"Error reading JSONL file {sFilePath}: {e}")
        return resultSet

    def _fnReadJsonlAsMap(self, sFilePath: str) -> dict:
        """Reads a .jsonl file of mappings into a dictionary."""
        resultMap = {}
        if not os.path.exists(sFilePath):
            return resultMap
        try:
            with open(sFilePath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        resultMap[data["post_page_url"]] = data["direct_image_url"]
        except (IOError, json.JSONDecodeError, KeyError) as e:
            print(f"Error reading or parsing map file {sFilePath}: {e}")
        return resultMap

    def _fnFetchPostPageUrls(self) -> list:
        """Fetches post page URLs incrementally."""
        print("Fetching post page URLs...")
        oPageNumPattern = re.compile('<a class="paginator-page desktop-only" href=".*">(.*?)</a>')
        lsPageList = self._fnCrawl(self.sRequestUrl, oPageNumPattern)
        iPageNum = int(lsPageList[-1]) if lsPageList else 1

        oHrefPattern = re.compile('<a class="post-preview-link" draggable="false" href="(.*?)">')

        with ThreadPool(processes=self.iPageFetchingThreads) as oPool:
            lsAsyncResults = []
            for iPage in range(1, iPageNum + 1):
                sPageUrl = f"{self.sRequestUrl}&page={iPage}"
                lsAsyncResults.append(oPool.apply_async(self._fnCrawl, (sPageUrl, oHrefPattern)))

            for oResult in tqdm(lsAsyncResults, desc="Crawling post pages"):
                for sLink in oResult.get():
                    sFullUrl = f"{self.sBaseUrl}{sLink}"
                    if sFullUrl not in self.setExistingPageUrls:
                        self.setExistingPageUrls.add(sFullUrl)
                        self.lsPageUrlBatch.append(sFullUrl)
                        self.iNewPageUrlsCount += 1
                        if len(self.lsPageUrlBatch) >= self.iBatchSize:
                            self._fnAppendJsonlFromList(self.lsPageUrlBatch, self.sPageUrlCacheFile)
                            self.lsPageUrlBatch.clear()

        return list(self.setExistingPageUrls)

    def _crawl_and_map_worker(self, sPostPageUrl: str, oPattern: re.Pattern) -> dict:
        """Worker to crawl a page and return a mapping from source URL to crawled URL."""
        lsImageUrls = self._fnCrawl(sPostPageUrl, oPattern)
        if lsImageUrls:
            # Assuming one direct image URL per post page
            return {"post_page_url": sPostPageUrl, "direct_image_url": lsImageUrls[0]}
        return {}

    def _fnFetchImageUrls(self, lsPostPageUrls: list) -> dict:
        """Fetches direct image URLs, skipping pages that are already cached."""
        print("Fetching direct image URLs...")
        oImgPattern = re.compile(r'<section .* data-file-url="(.*?)">.*?</section>', flags=re.S)

        # Filter out post pages that we already have a mapping for.
        urls_to_crawl = [url for url in lsPostPageUrls if url not in self.dictExistingImageUrlMap]
        print(f"Found {len(lsPostPageUrls)} total post pages. {len(urls_to_crawl)} are new and will be crawled.")

        with ThreadPool(processes=self.iUrlFetchingThreads) as oPool:
            lsAsyncResults = []
            for sUrl in urls_to_crawl:
                lsAsyncResults.append(oPool.apply_async(self._crawl_and_map_worker, (sUrl, oImgPattern)))

            for oResult in tqdm(lsAsyncResults, desc="Crawling image URLs"):
                dUrlMap = oResult.get()
                if dUrlMap:
                    sPostPageUrl = dUrlMap["post_page_url"]
                    # Final check to prevent race conditions if running multiple instances (unlikely here)
                    if sPostPageUrl not in self.dictExistingImageUrlMap:
                        self.dictExistingImageUrlMap[sPostPageUrl] = dUrlMap["direct_image_url"]
                        self.lsImageUrlMapBatch.append(dUrlMap)
                        self.iNewImageUrlsCount += 1
                        if len(self.lsImageUrlMapBatch) >= self.iBatchSize:
                            self._fnAppendJsonlFromListOfDicts(self.lsImageUrlMapBatch, self.sImageUrlCacheFile)
                            self.lsImageUrlMapBatch.clear()

        return self.dictExistingImageUrlMap

    def _fnDownloadImages(self, lsImageUrls: list):
        """Downloads all images from a list of URLs."""
        os.makedirs(self.sImageDownloadPath, exist_ok=True)

        # Filter out already downloaded files before starting the progress bar
        urls_to_download = []
        for url in lsImageUrls:
            filename = os.path.basename(url)
            filepath = os.path.join(self.sImageDownloadPath, filename)
            if not os.path.exists(filepath):
                urls_to_download.append(url)

        print(f"Found {len(lsImageUrls)} total images. {len(urls_to_download)} need to be downloaded.")

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
        """Downloads a single file with resume capability."""
        sFilename = os.path.basename(sUrl)
        sFilepath = os.path.join(self.sImageDownloadPath, sFilename)
        sTempFilepath = sFilepath + ".part"

        # This check is now done in _fnDownloadImages to set progress correctly
        # if os.path.exists(sFilepath):
        #     with self.oFileLock:
        #         self.dProgress["completed"] += 1
        #     return

        try:
            dHeaders = {}
            sMode = "wb"
            iStartByte = 0

            if os.path.exists(sTempFilepath):
                iStartByte = os.path.getsize(sTempFilepath)
                dHeaders["Range"] = f"bytes={iStartByte}-"
                sMode = "ab"

            with self.oSession.get(sUrl, stream=True, verify=False, timeout=30, headers=dHeaders) as oResponse:
                oResponse.raise_for_status()

                if oResponse.status_code == 200 and iStartByte > 0:
                    iStartByte = 0
                    sMode = "wb"

                with open(sTempFilepath, sMode) as f:
                    for chunk in oResponse.iter_content(8192):
                        if chunk:
                            f.write(chunk)

            os.rename(sTempFilepath, sFilepath)

        except requests.exceptions.RequestException as e:
            print(f"Download request error for {sUrl}: {e}")
        except Exception as e:
            print(f"Unknown download error for {sUrl}: {e}")
        finally:
            with self.oFileLock:
                if os.path.exists(sFilepath):
                    self.dProgress["completed"] += 1


if __name__ == "__main__":
    # --- Configuration ---
    TAG_LIST = [
        "mery_(yangmalgage)",
        "hyouka",
    ]
    DOWNLOAD_PATH = "./downloads"

    # --- Execution ---
    oDownloader = DanbooruDownloader(
        lsTags=TAG_LIST, sDownloadRoot=DOWNLOAD_PATH, iPageThreads=5, iUrlThreads=10, iBatchSize=50
    )

    oDownloader.fnDownload()
