# -*- utf-8 -*-

import copy
import os
import shutil
import cloudscraper
import json
import asyncio
import logging
import re
from hashlib import md5, sha256
from datetime import datetime
from .utils import check_file_exists


class CivitAI:
    def __init__(self, dl_dir: str):
        self._scraper = cloudscraper.create_scraper(browser='chrome')
        self._dl_dir = dl_dir
        self._base_data = {
            "metadata": {
                "totalItems": 0,
                "totalPages": 1,
                "currentPage": 1,
                "nextPage": ""
            },
            "items": []
        }

    async def civitai_get(self, url: str) -> dict:
        retries = 0
        while 1:
            try:
                logging.info(url)
                resp = self._scraper.get(url, timeout=30)
                if resp.status_code != 200:
                    raise InvalidStatusCode(resp.status_code)
                return resp.json()
            except InvalidStatusCode as e:
                logging.error(e)
                if e.status_code == 404:
                    return
                retries += 1
            except Exception as e:
                logging.error(e)
                retries += 1

            if retries >= 3:
                logging.error(
                    "failed to get metadata, maximum retires exceeded")
                return
            logging.error("failed to get meta, waiting for 60s")
            await asyncio.sleep(60)

    async def get_models_from_metadata(self) -> dict:
        data = copy.deepcopy(self._base_data)
        for dir in os.listdir(self._dl_dir):
            metafile = os.path.join(self._dl_dir, dir, "meta.json")
            with open(metafile, "r", encoding="utf-8") as f:
                data["items"].append(json.load(f))
                data["metadata"]["totalItems"] += 1
        return data

    async def get_model_ids_from_file(self, filename: str) -> dict:
        data = copy.deepcopy(self._base_data)
        with open(filename, "r") as f:
            list_url = f.readlines()
        for url in list_url:
            url = url.strip()

            # URL is model ID
            if url.isnumeric():
                data["items"].append(url)
                continue

            check = url.split("/")
            if len(check) < 2:
                logging.error("invalid url {}".format(url))
                continue
            if check[-2].isnumeric():
                data["items"].append(check[-2])
            elif check[-1].isnumeric():
                data["items"].append(check[-1])
            else:
                logging.error("model id not found in url {}".format(url))
                continue
        return data


class CivitAIModel:
    def __init__(
        self,
        dl_dir: str,
        data: dict,
        ignore_status_code: list,
        metadata_only: bool,
        latest_only: bool,
        from_metadata: bool = False,
        original_image: bool = False
    ):
        self._data = copy.deepcopy(data)
        self._metadata_only = metadata_only
        self._latest_only = latest_only
        self._from_metadata = from_metadata
        self._original_image = original_image

        self.model_id = data["id"]
        self.model_path = os.path.join(dl_dir, "{}".format(self.model_id))

        self._data["modelVersions"].sort(
            key=lambda modelv: datetime.strptime(
                modelv["createdAt"], "%Y-%m-%dT%H:%M:%S.%fZ"),
            reverse=True
        )

        self.nonlatest_sub_models = []
        self.sub_models = []
        # model directory format:
        # dir/{model_id}/{version_id}/
        for model in self._data["modelVersions"]:
            if self._latest_only and len(self.sub_models) > 0:
                m = CivitAIModelVersion(
                    self.model_id, self.model_path, model, ignore_status_code, self._original_image)
                if os.path.exists(m.sub_model_path):
                    self.nonlatest_sub_models.append(m)
            else:
                self.sub_models.append(CivitAIModelVersion(
                    self.model_id, self.model_path, model, ignore_status_code, self._original_image))

    async def remove_non_latest_model(self):
        for model in self.nonlatest_sub_models:
            await model.remove()

    async def verify(self):
        for model in self.sub_models:
            await model.verify()
        await self.remove_non_latest_model()

    async def new(self):
        '''
        Creates model path and model version path, download model metadata,
        BUT NOT download model files, for download model files, see run() method.
        '''

        if not self._from_metadata:
            # Create model path
            os.makedirs(self.model_path, exist_ok=True)

            # Save Meta Data
            meta_file = os.path.join(self.model_path, "meta.json")
            if not os.path.exists(meta_file):
                with open(meta_file, "w+", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=4)

        if self._metadata_only:
            return

        for model in self.sub_models:
            await model.new()

    async def run(self, verify: bool = False):
        # do not download model files if metadata_only specificed
        if self._metadata_only:
            return

        for model in self.sub_models:
            await model.run()
            if verify:
                await model.verify()


class CivitAIModelVersion:
    def __init__(
        self,
        model_id: int,
        dl_dir: str,
        data: dict,
        ignore_status_code: list,
        original_image: bool
    ):
        self._data = copy.deepcopy(data)
        self._scraper = cloudscraper.create_scraper(browser='chrome')
        self._ignore_status_code = ignore_status_code
        self._original_image = original_image
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
                "file": fn,
                "width": image["width"]
            })

    def log_info(self, message):
        logging.info("[{}-{}] {}".format(
            self.model_id,
            self.version_id,
            message))

    def log_warn(self, message):
        logging.warning("[{}-{}] {}".format(
            self.model_id,
            self.version_id,
            message))

    def log_error(self, message):
        logging.error("[{}-{}] {}".format(
            self.model_id,
            self.version_id,
            message))

    async def remove(self):
        if os.path.exists(self.sub_model_path):
            self.log_info("removing {}".format(self.sub_model_path))
            shutil.rmtree(self.sub_model_path)

    async def verify(self):
        # Verify Model Files
        for model_file in self.model_files:
            self.log_info("Verifying model file {}".format(model_file["file"]))

            # check model file exists
            if not await check_file_exists(self.sub_model_path, model_file["file"]):
                self.log_error(
                    "model file {} does not exists".format(model_file["file"]))
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
                    self.log_error(
                        "hash of model file {} is not match".format(model_file["file"]))
            else:
                self.log_info(
                    "skipped hash verification for model file {}".format(model_file["file"]))

        # Verify Images
        images_total = len(self.images)
        for i in range(images_total):
            image = self.images[i]
            self.log_info("Verifying image {} [{}/{}]".format(
                image["file"],
                i+1,
                images_total
            ))
            if not await check_file_exists(self.sub_model_path, image["file"], split_ext=True):
                self.log_error(
                    "image file {} does not exists".format(image["file"]))

    async def new(self):
        '''
        Creates model version path
        '''

        os.makedirs(self.sub_model_path, exist_ok=True)

    async def run(self):
        for model_file in self.model_files:
            # download model file
            if not await check_file_exists(self.sub_model_path, model_file["file"]):
                self.log_info(
                    "downloading model to {}".format(model_file["file"]))
                await self.download(model_file["url"], model_file["file"])

        # download images
        images_total = len(self.images)
        for i in range(images_total):
            image = self.images[i]
            if await check_file_exists(self.sub_model_path, image["file"], split_ext=True):
                continue

            image_url = self.get_original_image_url(
                image["url"], image["width"]) if self._original_image else image["url"]
            self.log_info("downloading image to {} [{}/{}]".format(
                image["file"],
                i+1,
                images_total
            ))
            await self.download(image_url, image["file"], auto_ext=True)

    def get_original_image_url(self, image_url: str, width: int):
        return re.sub(r'/width=\d+/', '/width={}'.format(width) + '/', image_url)

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
                raise InvalidStatusCode(r.status_code)

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
                self.log_info("downloaded {}".format(url))
                return
            except InvalidStatusCode as e:
                self.log_error(e)
                if e.status_code in self._ignore_status_code:
                    return
                else:
                    retries += 1
                    if retries >= 3:
                        self.log_error(
                            "failed to download {}, maximum retires exceeded".format(url))
                        return
                    self.log_error(
                        "Failed to download {}, waiting for 60s".format(url))
                    await asyncio.sleep(60)


class CivitAIImage:
    def __init__(
        self,
        dl_dir: str,
        data: dict,
        metadata_only: bool,
        original_image: bool
    ):
        self.dl_dir = dl_dir
        self._data = copy.deepcopy(data)
        self._scraper = cloudscraper.create_scraper(browser='chrome')
        self._original_image = original_image
        self._metadata_only = metadata_only
        self._ct_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp"
        }

        self.img_id = os.path.join(dl_dir, str(self._data['id']))
        self.img_url = self._data['url']
        self.img_width = self._data['width']

    def log_info(self, message):
        logging.info("[{}] {}".format(
            self.img_id,
            message))

    def log_warn(self, message):
        logging.warning("[{}] {}".format(
            self.img_id,
            message))

    def log_error(self, message):
        logging.error("[{}] {}".format(
            self.img_id,
            message))

    async def verify(self):
        if not await check_file_exists(self.dl_dir, self.img_id, split_ext=True):
            self.log_error(
                "image file {} does not exists".format(self.img_id))

    async def new(self):
        '''
        Creates model version path
        '''

        os.makedirs(self.dl_dir, exist_ok=True)

    async def run(self):

        if await check_file_exists(self.dl_dir, self.img_id, split_ext=True):
            return

        with open("{}.{}".format(self.img_id, 'json'), "w") as json_file:
            json.dump(self._data, json_file)
        if self._metadata_only:
            return
        image_url = self.get_original_image_url(
            self.img_url, self.img_width) if self._original_image else self.img_url
        self.log_info("downloading image to {}".format(self.img_id))
        await self.download(image_url, self.img_id, auto_ext=True)


    def get_original_image_url(self, image_url: str, width: int):
        return re.sub(r'/width=\d+/', '/width={}'.format(width) + '/', image_url)

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
                raise InvalidStatusCode(r.status_code)

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
                self.log_info("downloaded {}".format(url))
                return
            except InvalidStatusCode as e:
                self.log_error(e)
                if e.status_code in self._ignore_status_code:
                    return
                else:
                    retries += 1
                    if retries >= 3:
                        self.log_error(
                            "failed to download {}, maximum retires exceeded".format(url))
                        return
                    self.log_error(
                        "Failed to download {}, waiting for 60s".format(url))
                    await asyncio.sleep(60)


class InvalidStatusCode(Exception):
    def __init__(self, status_code: int):
        super().__init__("invalid status code {}".format(status_code))
        self.status_code = status_code
