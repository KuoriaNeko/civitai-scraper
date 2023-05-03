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

If you want to scrape images using main_img.py, the directory structure should be as follows:

```
download
├───img_id_1.json # Metadata of img_id
├───img_id_1.png (or webp, jpg) # Image
├───img_id_2.json
└───img_id_2.png
...
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

# Examples

Check [Examples](https://github.com/KuoriaNeko/civitai-scarper/examples)


Here's an example for downloading images:

```
python3 main_img.py --download --dir "download" --param "limit=200" --param "period=AllTime"
```
Please refer to [Image API reference](https://github.com/civitai/civitai/wiki/REST-API-Reference#get-apiv1images) to request specific images.








