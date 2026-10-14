"""Fetch the plugin's per-model program JSON the way the T0xDB plugin does.

Signs a CloudFront canned-policy URL with the key pair embedded in the plugin
bundle (read from the bundle at runtime, never stored here).
"""
import base64, json, re, sys, time
from pathlib import Path
import urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BUNDLE = Path(sys.argv[1]).read_text()
OUT = Path(sys.argv[2])
NAMES = sys.argv[3:]
KEY_ID = re.search(r'keypairId:\s*"([A-Z0-9]+)"', BUNDLE).group(1)
PEM = re.search(r'privateKeyString:\s*"(-----BEGIN RSA PRIVATE KEY-----.+?-----END RSA PRIVATE KEY-----)"', BUNDLE).group(1)
KEY = serialization.load_pem_private_key(PEM.encode().decode("unicode_escape").encode(), None)
BASE = "https://duavz4uy9zims.cloudfront.net"

def b64(b: bytes) -> str:
    return base64.b64encode(b).decode().translate(str.maketrans("+=/", "-_~"))

def signed(url: str) -> str:
    exp = int(time.time()) + 3600
    policy = json.dumps({"Statement": [{"Resource": url, "Condition": {"DateLessThan": {"AWS:EpochTime": exp}}}]}, separators=(",", ":"))
    sig = KEY.sign(policy.encode(), padding.PKCS1v15(), hashes.SHA1())
    return f"{url}?Expires={exp}&Signature={b64(sig)}&Key-Pair-Id={KEY_ID}"

for name in NAMES:
    url = f"{BASE}/meiju/{name}.json"
    try:
        with urllib.request.urlopen(signed(url), timeout=20) as r:
            data = r.read()
        dest = OUT / (name.replace("/", "_") + ".json")
        dest.write_bytes(data)
        print("ok  ", name, len(data), "->", dest)
    except Exception as e:
        print("fail", name, e)
