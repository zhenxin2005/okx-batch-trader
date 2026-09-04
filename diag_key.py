"""临时诊断：当前密钥在模拟盘/实盘环境分别测试（只查余额，只读不下单）"""
import os
from dotenv import load_dotenv

load_dotenv()
from okx_client import OKXTrader

k = os.environ.get("OKX_API_KEY", "")
print(f"当前配置的 API Key: {k[:4]}****{k[-4:]} (共{len(k)}位)")

for demo in (True, False):
    t = OKXTrader(use_demo=demo)
    r = t.check_api()
    code, msg = r.get("code"), r.get("msg", "")
    label = "模拟盘环境" if demo else "实盘环境"
    if code == "0":
        eq = r.get("data", [{}])[0].get("totalEq", "0")
        print(f"{label}: ✅ 成功！账户权益 {eq} USDT")
    else:
        print(f"{label}: ❌ [{code}] {msg[:60]}")
