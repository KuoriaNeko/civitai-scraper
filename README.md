# civitai-scraper

A CivitAI scraper

## Directory Structure

```
download
└───1 # Model ID
    ├───meta.json # Model Meta Data
    └───11 # Model Version ID
        ├───a.safetensors # Model file
        └───eg.jpg # Preview image
```

## How the downloaded files are named

Files are named in the following format:

|Usage|Rule|
|--|--|
|Pretrained model file|SHA256 from meta data OR `MD5(model_id + version_id + name)` + original extension|
|Model preview images|`MD5(the 'hash' value from meta data)` + extension from `Content-Type` in HTTP response header|

Examples (for convenience, some long text will be omitted):

|Type|Model ID|Version ID|Name|Model SHA256|Image Hash|Content-Type|Final filename|
|--|--|--|--|--|--|--|--|
|Model|11771|13905|aliciaMMD_delta.safetensors|976...E4C2|-|-|976e...e4c2.safetensors|
|Model|11771|13905|aliciaMMD_delta.safetensors|-|-|-|cf90c9ada33afd8b31f6ae445a13e068.safetensors|
|Image|11771|13905|-|-|`UELN#?xuW=%2},oeY7V[9FWB%Nbcgkof$xf6`|image/jpeg|abe04fa7678f942a24df2fe41d88b1bc.jpg|

# Requirements

- Python 3.10+
- [cloudscraper](https://github.com/VeNoMouS/cloudscraper)
- [click](https://github.com/pallets/click/)

# Usage

Download public models from civitai
```bash
python3 civitai.py --download \
--dir "download" \
--params "sort=Newest" \
--params "limit=5" \
--params "type=Hypernetwork"
```

Download public and hidden models
```bash
python3 civitai.py --download \
--dir "download" \
--params "sort=Newest" \
--params "limit=5" \
--params "type=Hypernetwork" \
--params "token=YOUR_API_TOKEN" \
--params "hidden=True"
```

Verify downloaded files
```bash
python3 civitai.py \
--dir "download" \
--verify
```