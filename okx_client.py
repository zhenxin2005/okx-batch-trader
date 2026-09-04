"""
OKX API 客户端封装
通过 OKX 客户端的 SOCKS5 代理连接，无需 VPN
"""
import os
import time
import ssl
import hmac
import hashlib
import base64
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Callable

import httpx
from decimal import Decimal

logger = logging.getLogger(__name__)


def parse_holdings(balance_result: dict) -> dict[str, float]:
    """从余额接口返回中提取 {币种: 可用数量}，只含数量大于 0 的币"""
    details = balance_result.get("data", [{}])[0].get("details", [])
    holdings = {}
    for d in details:
        avail = float(d.get("availBal", 0) or 0)
        if avail > 0:
            holdings[d["ccy"]] = avail
    return holdings


class OKXTrader:
    """OKX REST API 客户端"""

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        passphrase: str = "",
        use_demo: bool = None,
    ):
        self.api_key = api_key or os.environ.get("OKX_API_KEY", "")
        self.secret_key = secret_key or os.environ.get("OKX_SECRET_KEY", "")
        self.passphrase = passphrase or os.environ.get("OKX_PASSPHRASE", "")
        # 优先级：显式传参 > .env 配置 > 默认模拟盘
        if use_demo is None:
            env_val = os.environ.get("OKX_USE_DEMO")
            self.use_demo = (env_val.strip().lower() in ("true", "1", "yes")
                             if env_val is not None else True)
        else:
            self.use_demo = use_demo
        self.flag = "1" if self.use_demo else "0"
        self.domain = os.environ.get("OKX_DOMAIN", "https://www.okx.com")
        self._instruments = None  # 交易对精度信息缓存

        proxy = os.environ.get("OKX_PROXY", "socks5://127.0.0.1:17001")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) OKX/3.5.0 Chrome/110.0.5481.204 Safari/537.36",
            "Accept": "application/json",
        }

        transport = httpx.HTTPTransport(proxy=proxy, verify=ssl_context)
        self.client = httpx.Client(
            base_url=self.domain,
            transport=transport,
            timeout=10,
            headers=headers,
        )

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method + path + body
        mac = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _get_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
               f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"

    def _request(self, method: str, path: str, params: dict = None) -> dict:
        # OKX 签名规则不同：GET 参数拼在 query，签名含完整网址；
        # POST 参数放请求体（必须无空格的紧凑 JSON），签名只含不带 query 的路径
        if method == "POST":
            body = json.dumps(params, separators=(",", ":")) if params else ""
            sign_path = path
        else:
            body = ""
            sign_path = f"{path}?{'&'.join([f'{k}={v}' for k, v in params.items()])}" if params else path

        timestamp = self._get_timestamp()
        sign = self._sign(timestamp, method, sign_path, body)

        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

        if self.use_demo:
            headers["x-simulated-trading"] = "1"

        try:
            if method == "GET":
                response = self.client.get(sign_path, headers=headers)
            else:
                response = self.client.post(sign_path, headers=headers, data=body)
            return response.json()
        except Exception as e:
            logger.error(f"API 请求失败: {e}")
            return {"code": "-1", "msg": str(e)}

    def get_all_tickers(self) -> list[dict]:
        result = self._request("GET", "/api/v5/market/tickers", {"instType": "SPOT"})
        if result.get("code") == "0":
            tickers = result.get("data", [])
            return [t for t in tickers if t.get("instId", "").endswith("-USDT")]
        return []

    def check_api(self) -> dict:
        """返回余额接口的原始结果，用于界面显示密钥是否有效及具体错误"""
        return self._request("GET", "/api/v5/account/balance")

    def get_spot_holdings(self) -> dict[str, float]:
        """返回 {币种: 可用数量}，只含数量大于 0 的币"""
        result = self.check_api()
        if result.get("code") != "0":
            return {}
        return parse_holdings(result)

    def _get_instruments(self) -> dict[str, dict]:
        """返回 {instId: {lotSz, minSz}}，进程内只拉取一次"""
        if self._instruments is None:
            result = self._request("GET", "/api/v5/public/instruments", {"instType": "SPOT"})
            if result.get("code") == "0":
                self._instruments = {
                    d["instId"]: {"lotSz": d.get("lotSz", ""), "minSz": d.get("minSz", "")}
                    for d in result.get("data", [])
                }
            else:
                self._instruments = {}
        return self._instruments

    @staticmethod
    def _floor_to_step(amount: float, step: str) -> str:
        """数量向下取整到合法步长（如 lotSz=0.001），返回字符串避免浮点误差"""
        step_d = Decimal(step or "0")
        if step_d <= 0:
            return f"{amount:g}"
        val = (Decimal(str(amount)) // step_d) * step_d
        return f"{val:f}"

    def get_account_balance(self, ccy: str = "USDT") -> Optional[float]:
        result = self._request("GET", "/api/v5/account/balance", {"ccy": ccy})
        if result.get("code") == "0":
            details = result.get("data", [{}])[0].get("details", [])
            for detail in details:
                if detail.get("ccy") == ccy:
                    return float(detail.get("availBal", 0))
            return float(result.get("data", [{}])[0].get("totalEq", "0"))
        return None

    def place_market_buy_order(self, inst_id: str, sz: float) -> dict:
        """市价买入，sz 为花费的 USDT 金额（tgtCcy=quote_ccy）"""
        return self._request("POST", "/api/v5/trade/order", {
            "instId": inst_id, "tdMode": "cash",
            "side": "buy", "ordType": "market", "sz": str(sz),
            "tgtCcy": "quote_ccy",
        })

    def place_market_sell_order(self, inst_id: str, sz, tgt_ccy: str = None) -> dict:
        """市价卖出。tgt_ccy='quote_ccy' 时 sz 为 USDT 金额，否则 sz 为币的数量"""
        params = {
            "instId": inst_id, "tdMode": "cash",
            "side": "sell", "ordType": "market", "sz": str(sz),
        }
        if tgt_ccy:
            params["tgtCcy"] = tgt_ccy
        return self._request("POST", "/api/v5/trade/order", params)

    def sell_all_holdings(self, inst_id: str, holdings: dict) -> dict:
        """市价卖出某交易对的全部持仓（数量按 lotSz 向下取整防拒单）"""
        base_ccy = inst_id.split("-")[0]
        avail = holdings.get(base_ccy, 0)
        if avail <= 0:
            return {"code": "-1", "msg": f"无 {base_ccy} 持仓"}
        lot_sz = self._get_instruments().get(inst_id, {}).get("lotSz", "")
        sz = self._floor_to_step(avail, lot_sz)
        return self.place_market_sell_order(inst_id, sz)

    def batch_buy(self, orders: list[dict]) -> list[dict]:
        """逐单市价买入，orders: [{instId, sz(USDT金额)}]，返回逐币结果"""
        results = []
        for order in orders:
            result = self.place_market_buy_order(order["instId"], order["sz"])
            results.append(self._pack_result(order["instId"], order["sz"], result))
            time.sleep(0.1)
        return results

    def batch_sell(self, orders: list[dict], holdings: dict) -> list[dict]:
        """逐单市价卖出。orders: [{instId, sz}]，mode='amount' 按 USDT 金额，mode='all' 全部卖出"""
        results = []
        for order in orders:
            if order.get("mode") == "all":
                result = self.sell_all_holdings(order["instId"], holdings)
            else:
                result = self.place_market_sell_order(order["instId"], order["sz"], tgt_ccy="quote_ccy")
            results.append(self._pack_result(order["instId"], order.get("sz", "全部"), result))
            time.sleep(0.1)
        return results

    @staticmethod
    def _pack_result(inst_id: str, sz, result: dict) -> dict:
        return {
            "instId": inst_id,
            "sz": sz,
            "code": result.get("code", "-1"),
            "msg": result.get("msg", ""),
            "ordId": result.get("data", [{}])[0].get("ordId", "") if result.get("data") else "",
        }
