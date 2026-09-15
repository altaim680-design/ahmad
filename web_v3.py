# -*- coding: utf-8 -*-
from pathlib import Path
import base64, hashlib, zlib

_parts_dir = Path(__file__).with_name('v3parts')
_payload = ''.join((_parts_dir / f'p{i}.txt').read_text(encoding='utf-8').strip() for i in range(6))
_source = zlib.decompress(base64.b64decode(_payload))
_expected = '58b5843deeee87829a91cf3b9e8f1e74fbf23708e6a63580f82b39651e3d2f08'
_actual = hashlib.sha256(_source).hexdigest()
if _actual != _expected:
    raise RuntimeError(f'V3 payload integrity check failed: {_actual}')
exec(compile(_source.decode('utf-8'), 'web_v3_impl.py', 'exec'), globals(), globals())
