import urllib.request
import json
import re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

urls = [
    "https://eldenring.wiki.fextralife.com/Elden_Ring_Tarnished_Edition",
    "https://en.bandainamcoent.eu/elden-ring/elden-ring-tarnished-edition"
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        # clean HTML tags
        text = re.sub('<[^<]+?>', ' ', html)
        text = ' '.join(text.split())
        print(f"=== {url} ===")
        print(text[:2000])
    except Exception as e:
        print(f"Error {url}: {e}")
