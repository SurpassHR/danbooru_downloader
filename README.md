<div align="center">
  <h1><a href="https://danbooru.donmai.us"><img src="assets/icon.png" alt="Danbooru Logo" width="24" height="24"></a><a href="https://danbooru.donmai.us">  Danbooru</a> Downloader</h1>
</div>

- Download raw images from https://danbooru.donmai.us.

- Download filter supports `OR` and `NOT` operator, refer to https://danbooru.donmai.us/wiki_pages/help:blacklists.

- Suggested python version >= 3.12.

- Support resuming downloads from break point.

- Display download progress using tqdm.

## Usage

- Run `init_dev_env.sh`.

- Change `downloader.py` Line.13 `TAG_LIST` to your target tags.

- Run `downloader.py`.

- Find your results in `downloads` folder.

> Every time you start a new download job, it's suggested deleting `./cache_page_urls.json`, `./cache_image_urls.json`, `./downloads` manually.