

import cloudscraper
import json
import click
from hashlib import md5, sha256
import os
import re
import copy
import sys
import asyncio


class Logger:
    def __init__(self):
        self.stdout = sys.stdout
        self.log = open("log.log", "a+", encoding="utf-8")
        self._secret_re = re.compile(r"&?token\=([^&]+)&?")

    def write(self, msg):
        re_f = self._secret_re.findall(msg)
        if len(re_f) > 0:
            try:
                msg = msg.replace(re_f[0], "HIDDEN_SECRET")
            except:
                pass
        self.stdout.write(msg)
        self.log.write(msg)

    def flush(self):
        self.stdout.flush()
        self.log.flush()


sys.stdout = Logger()


class CivitAI:
    def __init__(self):
        self._api_base = "https://civitai.com"
        self._scraper = cloudscraper.create_scraper(browser='chrome')
        self.limit = 3

    def get_models(self, url: str) -> dict:
        print(url)
        resp = self._scraper.get(url, timeout=30)

        if resp.status_code != 200:
            raise ValueError(resp.status_code)
        return resp.json()


class CivitAIModel:
    def __init__(self, dl_dir: str, data: dict):
        self._data = copy.deepcopy(data)

        self.model_id = data["id"]
        self.model_path = os.path.join(dl_dir, "{}".format(self.model_id))

        self.sub_models = []
        # model directory format:
        # dir/{model_id}/{version_id}/
        for model in self._data["modelVersions"]:
            self.sub_models.append(CivitAIModelVersion(
                self.model_id, self.model_path, model))

    async def verify(self):
        for model in self.sub_models:
            await model.verify()

    async def new(self):
        # Create model path
        os.makedirs(self.model_path, exist_ok=True)

        # Save Meta Data
        meta_file = os.path.join(self.model_path, "meta.json")
        if not os.path.exists(meta_file):
            with open(meta_file, "w+", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)

        for model in self.sub_models:
            await model.new()

    async def run(self):
        for model in self.sub_models:
            await model.run()


class CivitAIModelVersion:
    def __init__(self, model_id: int, dl_dir: str, data: dict):
        self._data = copy.deepcopy(data)
        self._scraper = cloudscraper.create_scraper(browser='chrome')
        self._ct_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp"
        }

        self.model_id = model_id
        self.version_id = data["id"]

        # dir/{model_id}/{version_id}/
        self.sub_model_path = os.path.join(
            dl_dir, "{}".format(self.version_id))

        self.model_files = []
        for model_file in self._data["files"]:
            # file name: model_file["hashes"]["SHA256"] + ext
            # or md5(model_id + version_id + name) + ext
            h = model_file["hashes"].get(
                "SHA256",
                md5("{}{}{}".format(
                    self.model_id,
                    self.version_id,
                    model_file["name"]
                ).encode("utf-8")).hexdigest()
            ).lower()
            fn = os.path.join(self.sub_model_path, h)
            self.model_files.append({
                "url": model_file["downloadUrl"],
                "sha256": model_file["hashes"].get("SHA256", None),
                "file": "{}.{}".format(fn, model_file["name"].split(".")[-1])
            })

        self.images = []
        # image name: md5(image["hash"])
        for image in self._data["images"]:
            md5_hash = md5(image["hash"].encode("utf-8")).hexdigest()
            fn = os.path.join(
                self.sub_model_path,
                md5_hash
            )
            self.images.append({
                "url": image["url"],
                "md5_hash": md5_hash,
                "file": fn
            })

    async def verify(self):
        # Verify Model Files
        for model_file in self.model_files:
            print("[{}-{}] Verifying model file {}".format(
                self.model_id,
                self.version_id,
                model_file["file"]
            ))

            # check model file exists
            if not await check_file_exists(self.sub_model_path, model_file["file"]):
                print("[{}-{}][Failed] model file {} does not exists".format(
                    self.model_id,
                    self.version_id,
                    model_file["file"]
                ))
                continue

            # check model file hash if possible
            model_file_sha256 = model_file["sha256"]
            if model_file_sha256 is not None:
                h256 = sha256()
                with open(model_file["file"], "rb") as f:
                    while 1:
                        data = f.read(8192)
                        if not data:
                            break
                        h256.update(data)
                if h256.hexdigest() != model_file_sha256.lower():
                    print("[{}-{}][Failed] hash of model file {} is not match".format(
                        self.model_id,
                        self.version_id,
                        model_file["file"]
                    ))
            else:
                print("[{}-{}] Skipped hash verification for model file {}".format(
                    self.model_id,
                    self.version_id,
                    model_file["file"]
                ))

        # Verify Images
        images_total = len(self.images)
        for i in range(images_total):
            image = self.images[i]
            print("[{}-{}] Verifying image {} [{}/{}]".format(
                self.model_id,
                self.version_id,
                image["file"],
                i+1,
                images_total
            ))
            if not await check_file_exists(self.sub_model_path, image["file"], split_ext=True):
                print("[{}-{}][Failed] {} does not exists".format(
                    self.model_id,
                    self.version_id,
                    image["file"]
                ))

    async def new(self):
        os.makedirs(self.sub_model_path, exist_ok=True)

    async def run(self):
        for model_file in self.model_files:
            # download model file
            if not await check_file_exists(self.sub_model_path, model_file["file"]):
                print("[{}-{}] Downloading model to {}".format(
                    self.model_id,
                    self.version_id,
                    model_file["file"]
                ))
                await self.download(model_file["url"], model_file["file"])

        # download images
        images_total = len(self.images)
        for i in range(images_total):
            image = self.images[i]
            if await check_file_exists(self.sub_model_path, image["file"], split_ext=True):
                continue

            print("[{}-{}] Downloading image to {} [{}/{}]".format(
                self.model_id,
                self.version_id,
                image["file"],
                i+1,
                images_total
            ))
            await self.download(image["url"], image["file"], auto_ext=True)

    async def _download(self, url: str, fn: str, auto_ext: bool = False):
        with self._scraper.get(url, stream=True) as r:
            # Set encoding to utf-8 to avoid character issues
            r.encoding = "utf-8"

            if auto_ext:
                ext_name = self._ct_map.get(
                    r.headers.get("Content-Type", "default"),
                    ""
                )
                if len(ext_name) > 0:
                    fn = "{}.{}".format(fn, ext_name)

            if r.status_code != 200:
                raise ValueError(r.status_code)

            with open(fn, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    # If you have chunk encoded response uncomment if
                    # and set chunk_size parameter to None.
                    # if chunk:
                    f.write(chunk)

    async def download(self, url: str, fn: str, auto_ext: bool = False):
        retries = 0
        while 1:
            try:
                await self._download(url, fn, auto_ext)
                print("Downloaded {}".format(url))
                return
            except Exception as e:
                print(str(e))
                if retries >= 3:
                    print("Failed to download {}, maximum retires exceeded".format(url))
                    return
                print("Failed to download {}, waiting for 60s".format(url))
                await asyncio.sleep(60)


async def check_file_exists(dir: str, fn: str, split_ext: bool = False) -> bool:
    fn = fn.split(os.path.sep)[-1]
    for _, _, efns in os.walk(dir):
        for efn in efns:
            if split_ext:
                if efn.split(".")[0] == fn:
                    return True
            else:
                if efn == fn:
                    return True
    return False


async def run_download(dl_dir: str, params: list):
    cai = CivitAI()

    next_page = "https://civitai.com/api/v1/models"
    if len(params) > 0:
        next_page += "?"
        for param in params:
            next_page += "&{}".format(param)

    while 1:
        model_list = {}
        retries = 0
        while 1:
            try:
                model_list = cai.get_models(next_page)
                break
            except Exception as e:
                print(str(e))
                retries += 1
                if retries >= 3:
                    print("Failed to get meta, maximum retires exceeded")
                    return
                print("Failed to get meta, waiting for 60s")
                await asyncio.sleep(60)

        total_items = model_list["metadata"]["totalItems"]
        total_pages = model_list["metadata"]["totalPages"]
        current_page = model_list["metadata"]["currentPage"]
        next_page = model_list["metadata"].get("nextPage", None)

        if next_page is None:
            return

        print("Total Items: {}, Page: [{}/{}]".format(
            total_items,
            current_page,
            total_pages
        ))

        for item in model_list["items"]:
            cai_model = CivitAIModel(dl_dir, item)
            await cai_model.new()
            await cai_model.run()


async def run_verify(dl_dir: str):
    for model_dir in os.listdir(dl_dir):
        meta_file = os.path.join(dl_dir, model_dir, "meta.json")
        cai_model = None
        with open(meta_file, "r+", encoding="utf-8") as f:
            cai_model = CivitAIModel(dl_dir, json.load(f))
        await cai_model.verify()


@click.command()
@click.option("--dir", default="downloaded", help="Download to this directory")
@click.option("--download", is_flag=True, help="Start file download")
@click.option("--verify", is_flag=True, help="Run verification for downloaded files")
@click.option("--param", default=[], help="URL query params", multiple=True)
def main(dir: str, download: bool, verify: bool, param: list):
    try:
        if download:
            asyncio.run(run_download(dir, param))
        elif verify:
            asyncio.run(run_verify(dir))
    except KeyboardInterrupt:
        print("SIGINT received")
        pass


if __name__ == "__main__":
    main()
