# -*- coding: utf-8 -*-

import json
import random

import click
import re
import os
import sys
import asyncio
import logging
import datetime

from civitai import CivitAI, CivitAIModel

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %z",
    handlers=[
        logging.FileHandler("log.log", mode="a+"),
        logging.StreamHandler(sys.stdout)
    ]
)


async def run_download(dl_dir: str, verify: bool, **kwargs):
    cai = CivitAI(dl_dir=dl_dir)
    params = kwargs["param"]
    from_metadata = kwargs["from_metadata"]
    from_url_file = kwargs["from_url_file"]

    next_page = "https://civitai.com/api/v1/models"
    if len(params) > 0:
        next_page += "?"
        for param in params:
            next_page += "&{}".format(param)

    while len(next_page) > 0:
        model_list = {}
        if from_metadata:
            model_list = await cai.get_models_from_metadata()
            next_page = ""
        elif len(from_url_file) > 0:
            model_list = await cai.get_model_ids_from_file(from_url_file)
            next_page = ""
        else:
            model_list = await cai.civitai_get(next_page)

        total_items = model_list["metadata"]["totalItems"]
        total_pages = model_list["metadata"]["totalPages"]
        current_page = model_list["metadata"]["currentPage"]
        next_page = model_list["metadata"].get("nextPage", "")

        logging.info("Total Items: {}, Page: [{}/{}]".format(
            total_items,
            current_page,
            total_pages
        ))

        nsfw_only = kwargs["nsfw_only"]
        for item in model_list["items"]:
            # from url file
            if len(from_url_file) > 0:
                item = await cai.civitai_get(
                    "https://civitai.com/api/v1/models/{}".format(item)
                )
                if not item:
                    continue

            if nsfw_only and not item["nsfw"]:
                continue

            cai_model = CivitAIModel(
                dl_dir,
                item,
                kwargs["ignore_status_code"],
                kwargs["metadata_only"],
                kwargs["latest_only"],
                from_metadata=from_metadata,
                original_image=kwargs["original_image"]
            )
            await cai_model.new()
            await cai_model.run(verify)


async def run_verify(dl_dir: str, **kwargs):
    for model_dir in os.listdir(dl_dir):
        meta_file = os.path.join(dl_dir, model_dir, "meta.json")
        cai_model = None
        with open(meta_file, "r+", encoding="utf-8") as f:
            cai_model = CivitAIModel(
                dl_dir,
                json.load(f),
                kwargs["ignore_status_code"],
                kwargs["metadata_only"],
                kwargs["latest_only"]
            )

        if cai_model is not None:
            await cai_model.verify()


@click.command()
@click.option("--dir", default="downloaded", help="Download to this directory")
@click.option("--param", default=[], help="URL query params", multiple=True)
@click.option("--ignore-status-code", default=[401, 403, 404], help="the specified http status codes skips retry, only for download models", multiple=True)
@click.option("--download", is_flag=True, help="Start file download")
@click.option("--metadata-only", is_flag=True, help="download metadata only")
@click.option("--nsfw-only", is_flag=True, help="download NSFW content only, also applies to --metadata-only")
@click.option("--latest-only", is_flag=True, help="download latest model only, or remove non-latest files on verification, not applies to --metadata-only")
@click.option("--from-metadata", is_flag=True, help="read metadata downloaded previously when downloading models")
@click.option("--from-url-file", default="", help="download models from url file")
@click.option("--original-image", is_flag=True, help="download original images")
@click.option("--verify", is_flag=True, help="Run verification for downloaded files")
def main(dir: str, download: bool, verify: bool, **kwargs):
    try:
        if download:
            asyncio.run(run_download(dir, verify, **kwargs))
        elif verify:
            asyncio.run(run_verify(dir, **kwargs))
        else:
            click.echo(
                click.get_current_context().get_help())
            exit(1)
    except KeyboardInterrupt:
        logging.warning("SIGINT received")


if __name__ == "__main__":
    main()
