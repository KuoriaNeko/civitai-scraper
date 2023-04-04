# Examples

## Commandline Examples

Download public models from civitai
```bash
python3 civitai.py --download \
--dir "download" \
--param "sort=Newest" \
--param "limit=5" \
--param "type=Hypernetwork"
```

Download and verify public models from civitai
```bash
python3 civitai.py --download \
--verify \
--dir "download" \
--param "sort=Newest" \
--param "limit=5" \
--param "type=Hypernetwork"
```

Download public and hidden models
```bash
python3 civitai.py --download \
--dir "download" \
--param "sort=Newest" \
--param "limit=5" \
--param "type=Hypernetwork" \
--param "token=YOUR_API_TOKEN" \
--param "hidden=True"
```

Verify downloaded files
```bash
python3 civitai.py \
--dir "download" \
--verify
```

## URL File Examples

Download models from a URL file
```bash
python3 civitai.py --download \
--dir "download" \
--from-url-file "YOUR_URL_FILE"
```

URL file content accepts these formats(per line):

|Description|Example|
|--|--|
|Model Webpage URL|`https://civitai.com/models/26139/blue-lycoris-uniform`|
|Model Webpage URL|`https://civitai.com/models/26139`|
|Model ID|26139|

You can find a example URL file [here](url_file/url_list.txt)
