# civitai-scraper

A CivitAI scraper

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