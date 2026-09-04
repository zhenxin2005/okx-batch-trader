import os, ssl, hmac, hashlib, base64, json
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get('OKX_API_KEY', '')
secret_key = os.environ.get('OKX_SECRET_KEY', '')

variations = [
    ('Zhenxin2019＠', 'full-width @'),
    ('Zhenxin2019', 'no special char'),
    ('Zhenxin2019a', 'lowercase a instead of @'),
    ('Zhenxin2019A', 'uppercase A instead of @'),
    ('Zhenxin20192', '2 instead of @'),
    ('Zhenxin2019#', '# instead of @'),
    ('Zhenxin2019!', '! instead of @'),
    ('Zhenxin2019*', '* instead of @'),
    ('Zhenxin2019&', '& instead of @'),
    ('Zhenxin2019_', '_ instead of @'),
    ('Zhenxin2019.', '. instead of @'),
    ('Zhenxin2019,', ', instead of @'),
    ('Zhenxin2019-', '- instead of @'),
    ('Zhenxin2019+', '+ instead of @'),
    ('Zhenxin2019=', '= instead of @'),
    ('Zhenxin2019~', '~ instead of @'),
    ('Zhenxin2019^', '^ instead of @'),
    ('Zhenxin2019@', 'original'),
    ('Zhenxin2019@!', 'added !'),
    ('Zhenxin2019@#', 'added #'),
    ('Zhenxin2019@123', 'added 123'),
    ('Zhenxin2019@abc', 'added abc'),
    ('Zhenxin2019@OKX', 'added OKX'),
    ('Zhenxin2019@okx', 'added okx'),
    ('Zhenxin2019@!', '@ and !'),
    ('Zhenxin2019@#', '@ and #'),
    ('Zhenxin2019@$', '@ and $'),
    ('Zhenxin2019@%', '@ and %'),
    ('Zhenxin2019@^', '@ and ^'),
    ('Zhenxin2019@&', '@ and &'),
    ('Zhenxin2019@*', '@ and *'),
    ('Zhenxin2019@(', '@ and ('),
    ('Zhenxin2019@)', '@ and )'),
    ('Zhenxin2019@_', '@ and _'),
    ('Zhenxin2019@+', '@ and +'),
    ('Zhenxin2019@=', '@ and ='),
    ('Zhenxin2019@1', '@ and 1'),
    ('Zhenxin2019@9', '@ and 9'),
    ('Zhenxin2019@0', '@ and 0'),
]

for pp, desc in variations:
    try:
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f'{datetime.now(timezone.utc).microsecond // 1000:03d}Z'
        method = 'GET'
        path = '/api/v5/account/balance?ccy=USDT'
        body = ''
        message = timestamp + method + path + body
        mac = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256)
        sign = base64.b64encode(mac.digest()).decode()

        headers = {
            'OK-ACCESS-KEY': api_key,
            'OK-ACCESS-SIGN': sign,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': pp,
            'Content-Type': 'application/json',
            'x-simulated-trading': '1',
        }

        proxy = 'socks5://127.0.0.1:17001'
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        transport = httpx.HTTPTransport(proxy=proxy, verify=ssl_context)
        client = httpx.Client(base_url='https://www.okx.com', transport=transport, timeout=10,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) OKX/3.5.0 Chrome/110.0.5481.204 Safari/537.36',
                'Accept': 'application/json',
            })

        response = client.get(path, headers=headers)
        result = response.json()
        code = result.get('code', 'unknown')
        if code == '0':
            print(f'{desc}: SUCCESS!')
            print(f'  Data: {result.get("data", [])[:1]}')
            break
        else:
            msg = result.get('msg', '')
            if 'PASSPHRASE' not in msg:
                print(f'{desc}: DIFFERENT ERROR: code={code} msg={msg}')
            else:
                pass  # Skip printing all 50105 errors
    except Exception as e:
        print(f'{desc}: error={str(e)[:80]}')

print('Done testing variations')