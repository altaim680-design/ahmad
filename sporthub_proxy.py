from flask import Flask, request, Response
import time
import requests

app = Flask(__name__)
UPSTREAM = 'https://nahda-web-accounting.onrender.com'

RETRYABLE_STATUS = {502, 503, 504}
SAFE_RETRY_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def _should_retry(method, target_path):
    method = method.upper()
    if method in SAFE_RETRY_METHODS:
        return True
    # Login POST is safe to retry when Render itself is still waking the upstream.
    return method == 'POST' and target_path.rstrip('/') == '/sporthub/admin/login'


def _request_upstream(method, target, target_path, headers, body):
    retry = _should_retry(method, target_path)
    attempts = 6 if retry else 1
    last_response = None
    last_error = None

    for attempt in range(attempts):
        try:
            r = requests.request(
                method,
                target,
                headers=headers,
                data=body,
                allow_redirects=False,
                timeout=18,
            )
            last_response = r
            if not retry or r.status_code not in RETRYABLE_STATUS:
                return r
        except requests.RequestException as exc:
            last_error = exc
            if not retry:
                break

        # Give Render time to wake the upstream service. Total delay is bounded.
        if attempt < attempts - 1:
            time.sleep(min(2 + attempt * 2, 10))

    if last_response is not None:
        return last_response
    if last_error is not None:
        raise last_error
    raise requests.RequestException('upstream unavailable')


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
    # Force uncompressed upstream responses so content-encoding can never drift
    # between Render, requests, and the browser.
    headers['Accept-Encoding'] = 'identity'
    headers['Host'] = 'nahda-web-accounting.onrender.com'
    headers['X-Forwarded-Proto'] = 'https'
    headers['X-Forwarded-Host'] = request.host

    try:
        r = _request_upstream(
            request.method,
            target,
            target_path,
            headers,
            request.get_data(),
        )
    except requests.RequestException:
        return Response(
            'SPORT HUB عم يشتغل الآن. انتظر لحظات ثم أعد المحاولة.',
            status=503,
            content_type='text/plain; charset=utf-8',
            headers={'Retry-After': '5', 'Cache-Control': 'no-store'},
        )

    # Never expose Render's large generic 502/503/504 gateway page to users.
    # For non-retried write requests, return a small friendly message instead.
    if r.status_code in RETRYABLE_STATUS:
        return Response(
            'SPORT HUB عم يشتغل الآن. انتظر لحظات ثم أعد المحاولة.',
            status=503,
            content_type='text/plain; charset=utf-8',
            headers={'Retry-After': '5', 'Cache-Control': 'no-store'},
        )

    excluded = {
        'content-encoding', 'content-length', 'transfer-encoding', 'connection',
        'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te',
        'trailers', 'upgrade'
    }
    out_headers = [(k, v) for k, v in r.headers.items() if k.lower() not in excluded]
    out_headers.append(('Cache-Control', 'no-store' if target_path.startswith('/sporthub/admin') else r.headers.get('Cache-Control', 'no-cache')))
    return Response(r.content, status=r.status_code, headers=out_headers)


@app.get('/healthz')
def healthz():
    return {'ok': True, 'service': 'sporthub-syria'}
