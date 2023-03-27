# -*- coding: utf-8 -*-

import json
import click
import re
import os
import sys
import asyncio

from civitai import CivitAI, CivitAIModel


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


async def run_download(dl_dir: str, verify: bool, **kwargs):
    cai = CivitAI(dl_dir=dl_dir)
    params = kwargs["param"]
    from_metadata = kwargs["from_metadata"]

    next_page = "https://civitai.com/api/v1/models"
    if len(params) > 0:
        next_page += "?"
        for param in params:
            next_page += "&{}".format(param)

    while 1:
        model_list = {}
        if from_metadata:
            model_list = cai.get_models_from_metadata()
        else:
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

        nsfw_only = kwargs["nsfw_only"]
        for item in model_list["items"]:
            if nsfw_only and not item["nsfw"]:
                continue

            cai_model = CivitAIModel(
                dl_dir,
                item,
                kwargs["metadata_only"],
                kwargs["latest_only"]
            )
            await cai_model.new()
            await cai_model.run(verify)

        if from_metadata:
            return


async def run_verify(dl_dir: str, **kwargs):
    for model_dir in os.listdir(dl_dir):
        meta_file = os.path.join(dl_dir, model_dir, "meta.json")
        cai_model = None
        with open(meta_file, "r+", encoding="utf-8") as f:
            cai_model = CivitAIModel(
                dl_dir,
                json.load(f),
                kwargs["metadata_only"],
                kwargs["latest_only"]
            )

        if cai_model is not None:
            await cai_model.verify()


@click.command()
@click.option("--dir", default="downloaded", help="Download to this directory")
@click.option("--param", default=[], help="URL query params", multiple=True)
@click.option("--download", is_flag=True, help="Start file download")
@click.option("--metadata-only", is_flag=True, help="download metadata only")
@click.option("--nsfw-only", is_flag=True, help="download NSFW content only, also applies to --metadata-only")
@click.option("--latest-only", is_flag=True, help="download latest model only, or remove non-latest files on verification, not applies to --metadata-only")
@click.option("--from-metadata", is_flag=True, help="read metadata downloaded previously when downloading models")
@click.option("--verify", is_flag=True, help="Run verification for downloaded files")
def main(dir: str, download: bool, verify: bool, **kwargs):
    try:
        if download:
            asyncio.run(run_download(dir, verify, **kwargs))
        elif verify:
            asyncio.run(run_verify(dir, **kwargs))
    except KeyboardInterrupt:
        print("SIGINT received")
        pass


if __name__ == "__main__":
    main()
