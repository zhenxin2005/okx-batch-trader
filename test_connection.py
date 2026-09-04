import os
import ssl
import httpx
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get('OKX_API_KEY', '')
secret = os.environ.get('OKX_SECRET_KEY', '')
passphrase = os.environ.get('OKX_PASSPHRASE', '')

# 自定义 SSL 上下文，跳过主机名验证
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

from okx.okxclient import OkxClient

# 用 IP + 跳过 SSL 验证
print('=== 测试: IP + 跳过 SSL 验证 ===')
try:
    client = OkxClient(
        api_key=api_key,
        api_secret_key=secret,
        passphrase=passphrase,
        flag='1',
        base_api='https://47.79.65.12',
    )
    client.client = httpx.Client(verify=ssl_context, base_url='https://47.79.65.12', http2=True)
    result = client._request('GET', '/api/v5/market/tickers', params={'instType': 'SPOT'})
    print(f'结果: {result}')
except Exception as e:
    print(f'错误: {type(e).__name__}: {e}')
