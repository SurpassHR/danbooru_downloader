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
        fnProgress=None,
        dRenameConfig: dict = None,
    ):
        """

        :param lsTags: 要搜索的标签列表
        :param sDownloadRoot: 下载根目录（图片保存至 images/ 子目录）
        :param iPageThreads: 并发请求页数的线程数
        :param iUrlThreads: 并发下载图片的线程数
        :param fnProgress: 进度回调函数，签名 (total, completed, description)
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
        self._fnProgress = fnProgress
        self.dRenameConfig = dRenameConfig or {}

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
    # 标签解析工具
    # ------------------------------------------------------------------

    @staticmethod
    def _fnExtractTag(tag_string: str, namespace: str) -> str:
        """从 Danbooru tag_string 中提取指定命名空间的第一个标签值。"""
        if not tag_string or not namespace:
            return ""
        ns_prefix = f"{namespace}:"
        for tag in tag_string.split():
            if tag.startswith(ns_prefix):
                return tag[len(ns_prefix):]
        return ""

    @staticmethod
    def _fnGetShortTags(tag_string: str, count: int) -> str:
        """取前 N 个普通标签（无命名空间），下划线连接。"""
        if not tag_string or count <= 0:
            return ""
        general = [tag for tag in tag_string.split() if ":" not in tag]
        return "_".join(general[:count])

    # ------------------------------------------------------------------
    # 标签解析工具
    # ------------------------------------------------------------------

    @staticmethod
    def _fnExtractTag(tag_string: str, namespace: str) -> str:
        """从 Danbooru tag_string 中提取指定命名空间的第一个标签值。"""
        if not tag_string or not namespace:
            return ""
        ns_prefix = f"{namespace}:"
        for tag in tag_string.split():
            if tag.startswith(ns_prefix):
                return tag[len(ns_prefix):]
        return ""

    @staticmethod
    def _fnGetShortTags(tag_string: str, count: int) -> str:
        """取前 N 个普通标签（无命名空间），下划线连接。"""
        if not tag_string or count <= 0:
            return ""
        general = [tag for tag in tag_string.split() if ":" not in tag]
        return "_".join(general[:count])

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def fnGetProgress(self) -> dict:
        """返回当前下载进度的快照（线程安全）。"""
        with self.oFileLock:
            return dict(self.dProgress)

    def fnCancel(self):
        """请求取消下载。"""
        self._bCancelled = True
        print("Cancellation requested...")

    def fnIsCancelled(self) -> bool:
        """返回是否已请求取消。"""
        return self._bCancelled

    # ------------------------------------------------------------------
    # 重命名
    # ------------------------------------------------------------------

    def _fnComputeNewFilename(self, post: dict, index: int, total: int, original_ext: str) -> str | None:
        """根据重命名配置生成新文件名。返回 None 表示应保留原始文件名。"""
        rc = self.dRenameConfig
        if not rc.get("enabled"):
            return None

        mode = rc.get("mode", "pattern")

        if mode == "sequence":
            digits = len(str(total))
            prefix = rc.get("prefix", "")
            return f"{prefix}{index:0{digits}d}{original_ext}"

        # Pattern mode
        pattern = rc.get("pattern", "{post_id}")
        has_ext_in_pattern = "{ext}" in pattern
        if has_ext_in_pattern:
            pattern = pattern.replace("{ext}", original_ext)

        replacements = {
            "{post_id}": str(post.get("id", "")),
            "{artist}": self._fnExtractTag(post.get("tag_string", ""), "artist"),
            "{character}": self._fnExtractTag(post.get("tag_string", ""), "character"),
            "{copyright}": self._fnExtractTag(post.get("tag_string", ""), "copyright"),
            "{rating}": post.get("rating", ""),
            "{md5}": post.get("md5", ""),
            "{date}": (post.get("created_at", "")[:10] if post.get("created_at") else ""),
            "{tags_short}": self._fnGetShortTags(post.get("tag_string", ""), rc.get("tags_short_count", 3)),
            "{search_tags}": "_".join(self.lsTags),
        }

        basename = pattern
        for placeholder, value in replacements.items():
            if value:
                basename = basename.replace(placeholder, value)

        import re
        remaining = re.findall(r"\{\w+\}", basename)
        if remaining:
            return None

        if not has_ext_in_pattern:
            basename += original_ext

        return basename

    # ------------------------------------------------------------------
    # 主流程# ------------------------------------------------------------------

    def _fnComputeNewFilename(self, post: dict, index: int, total: int, original_ext: str) -> str | None:
        """根据重命名配置生成新文件名。返回 None 表示应保留原始文件名。"""
        rc = self.dRenameConfig
        if not rc.get("enabled"):
            return None

        mode = rc.get("mode", "pattern")

        if mode == "sequence":
            digits = len(str(total))
            prefix = rc.get("prefix", "")
            return f"{prefix}{index:0{digits}d}{original_ext}"

        # Pattern mode
        pattern = rc.get("pattern", "{post_id}")
        has_ext_in_pattern = "{ext}" in pattern
        if has_ext_in_pattern:
            pattern = pattern.replace("{ext}", original_ext)

        replacements = {
            "{post_id}": str(post.get("id", "")),
            "{artist}": self._fnExtractTag(post.get("tag_string", ""), "artist"),
            "{character}": self._fnExtractTag(post.get("tag_string", ""), "character"),
            "{copyright}": self._fnExtractTag(post.get("tag_string", ""), "copyright"),
            "{rating}": post.get("rating", ""),
            "{md5}": post.get("md5", ""),
            "{date}": (post.get("created_at", "")[:10] if post.get("created_at") else ""),
            "{tags_short}": self._fnGetShortTags(post.get("tag_string", ""), rc.get("tags_short_count", 3)),
            "{search_tags}": "_".join(self.lsTags),
        }

        basename = pattern
        for placeholder, value in replacements.items():
            if value:
                basename = basename.replace(placeholder, value)

        import re
        remaining = re.findall(r"\{\w+\}", basename)
        if remaining:
            return None

        if not has_ext_in_pattern:
            basename += original_ext

        return basename

    # ------------------------------------------------------------------
    # 主流程# ------------------------------------------------------------------

    def fnDownload(self):
        """启动下载流程：通过 JSON API 获取图片 URL 后下载。"""
        try:
            print("Starting download process...")
            self.dProgress["description"] = "Fetching image URLs via API..."
            lsAllPosts = self._fnFetchAllPosts()

            if self._bCancelled:
                print("Download cancelled after fetching URLs.")
                return

            self.dProgress["description"] = "Downloading images..."
            self._fnDownloadImages(lsAllPosts)

            if not self._bCancelled:
                print("\n--- Download Summary ---")
                print(f"Downloaded {len(lsAllPosts)} files.")
                print("Download process finished successfully.")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")

    # ------------------------------------------------------------------
    # JSON API 分页获取
    # ------------------------------------------------------------------

    def _fnFetchAllPosts(self) -> list:
        """通过 JSON API 获取所有帖子，返回 [(file_url, post_data), ...] 按 post_id 升序。"""
        all_posts = []
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
                    all_posts.append((file_url, post))

            print(
                f"  Fetched page {page}: {len(posts)} posts, "
                f"{len(all_posts)} total URLs"
            )

            if self._bCancelled:
                break
            if len(posts) < limit:
                break

            page += 1
            time.sleep(1.0)

        all_posts.sort(key=lambda x: x[1].get("id", 0))
        print(f"Fetched {len(all_posts)} image URLs in total.")
        return all_posts

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------

    def _fnDownloadImages(self, lsPosts: list):
        """从 post 列表下载图片，支持重命名。lsPosts = [(file_url, post_data), ...]"""
        os.makedirs(self.sImageDownloadPath, exist_ok=True)

        total_fetched = len(lsPosts)
        posts_to_download = []
        for index, (file_url, post) in enumerate(lsPosts):
            filename = os.path.basename(file_url)
            filepath = os.path.join(self.sImageDownloadPath, filename)
            if not os.path.exists(filepath):
                posts_to_download.append((index, total_fetched, file_url, post))

        print(
            f"Found {total_fetched} total images. "
            f"{len(posts_to_download)} need to be downloaded."
        )

        self.dProgress["total"] = len(posts_to_download)
        self.dProgress["completed"] = 0

        if not posts_to_download:
            return

        with ThreadPool(processes=self.iUrlFetchingThreads) as oPool:
            it = oPool.imap_unordered(self._fnDownloadSingleFile, posts_to_download)
            for _ in tqdm(
                it,
                total=len(urls_to_download),
                desc="Downloading images",
            ):
                if self._bCancelled:
                    oPool.terminate()
                    break

    def _fnDownloadSingleFile(self, args):
        """下载单个文件。args = (index, total_count, file_url, post)"""
        index, total_count, sUrl, post = args
        if self._bCancelled:
            return
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

                # 429 Too Many Requests -- 指数退避等待后重试
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
            # 重命名（序号模式下 index+1 转为 1-based）
            original_ext = os.path.splitext(sFilename)[1]
            new_name = self._fnComputeNewFilename(post, index + 1, total_count, original_ext)
            if new_name:
                new_path = os.path.join(self.sImageDownloadPath, new_name)
                if new_path != sFilepath:
                    if os.path.exists(new_path):
                        base, ext = os.path.splitext(new_name)
                        counter = 1
                        while os.path.exists(
                            os.path.join(self.sImageDownloadPath, f"{base}_{counter}{ext}")
                        ):
                            counter += 1
                        new_path = os.path.join(self.sImageDownloadPath, f"{base}_{counter}{ext}")
                    try:
                        os.rename(sFilepath, new_path)
                        print(f"  Renamed: {sFilename} -> {os.path.basename(new_path)}")
                    except OSError as e:
                        print(f"  Rename failed: {sFilename} - {e}")

            with self.oFileLock:
                self.dProgress["completed"] += 1
                if self._fnProgress:
                    self._fnProgress(
                        self.dProgress["total"],
                        self.dProgress["completed"],
                        self.dProgress["description"],
                    )
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
