from flask import Flask, request, Response
import requests

app = Flask(__name__)
UPSTREAM = 'https://nahda-web-accounting.onrender.com'

@app.route('/', defaults={'path': ''}, methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD'])
@app.route('/<path:path>', methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD'])
def proxy(path):
    if path == '':
        target_path = '/sporthub'
    elif path.startswith('sporthub/') or path == 'sporthub':
        target_path = '/' + path
    elif path.startswith('login') or path.startswith('static/'):
        target_path = '/' + path
    else:
        target_path = '/sporthub/' + path

    target = UPSTREAM + target_path
    if request.query_string:
        target += '?' + request.query_string.decode('utf-8', errors='ignore')

    headers = {
        k: v for k, v in request.headers
        if k.lower() not in ('host', 'content-length', 'connection', 'accept-encoding')
    }
    # Important: force an uncompressed upstream response. Render/browser may negotiate
    # Brotli, and forwarding those bytes without the original encoding header renders
    # the page as binary garbage in the browser.
    headers['Accept-Encoding'] = 'identity'
    headers['Host'] = 'nahda-web-accounting.onrender.com'
    headers['X-Forwarded-Proto'] = 'https'

    try:
        r = requests.request(
            request.method,
            target,
            headers=headers,
            data=request.get_data(),
            allow_redirects=False,
            timeout=60,
        )
    except requests.RequestException:
        return Response(
            'الخدمة قيد التشغيل، أعد المحاولة بعد قليل.',
            status=503,
            content_type='text/plain; charset=utf-8',
        )

    excluded = {
        'content-encoding', 'content-length', 'transfer-encoding', 'connection',
        'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te',
        'trailers', 'upgrade'
    }
    out_headers = [(k, v) for k, v in r.headers.items() if k.lower() not in excluded]
    return Response(r.content, status=r.status_code, headers=out_headers)

@app.get('/healthz')
def healthz():
    return {'ok': True, 'service': 'sporthub-syria'}
