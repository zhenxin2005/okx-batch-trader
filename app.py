"""
OKX 批量交易工具
实时行情 + 多条件筛选（价格/涨幅/持仓）+ 勾选币种批量买入/卖出
API 密钥可直接在网页侧边栏配置，保存后写入本地 .env
行情通过 OKX 客户端的 SOCKS5 代理走 REST API
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv, set_key, dotenv_values

from okx_client import OKXTrader, parse_holdings

load_dotenv()

st.set_page_config(
    page_title="OKX 批量交易",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .live-dot {
        display: inline-block; width: 8px; height: 8px;
        background: #00D4AA; border-radius: 50%;
        margin-right: 6px; animation: blink 1s infinite;
    }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
</style>
""",
    unsafe_allow_html=True,
)

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# --------------------------------------------------------------------------- #
# API 配置：优先级 网页保存的值 > .env；保存时写回 .env
# --------------------------------------------------------------------------- #
if "api_config" not in st.session_state:
    # 直接读 .env 文件（而非进程内存中的环境变量），
    # 避免程序启动后才修改的密钥在刷新页面后读回旧值
    env_file = dotenv_values(ENV_PATH)
    st.session_state.api_config = {
        "api_key": env_file.get("OKX_API_KEY", ""),
        "secret_key": env_file.get("OKX_SECRET_KEY", ""),
        "passphrase": env_file.get("OKX_PASSPHRASE", ""),
        "use_demo": env_file.get("OKX_USE_DEMO", "True").strip().lower() in ("true", "1", "yes"),
    }
cfg = st.session_state.api_config

if not cfg["api_key"]:
    st.warning("⚠️ 尚未配置 API 密钥，请在左侧「⚙️ API 配置」中填写（行情可看，无法交易）")


@st.cache_resource
def get_trader(api_key, secret_key, passphrase, use_demo):
    return OKXTrader(api_key, secret_key, passphrase, use_demo)


trader = get_trader(cfg["api_key"], cfg["secret_key"], cfg["passphrase"], cfg["use_demo"])


@st.cache_data(ttl=5)
def fetch_tickers() -> list[dict]:
    return trader.get_all_tickers()


@st.cache_data(ttl=5)
def fetch_balance():
    """返回 (持仓dict或None, 错误信息, 账户总权益)。持仓为 None 表示密钥无效"""
    raw = trader.check_api()
    if raw.get("code") != "0":
        return None, f"{raw.get('code')}: {raw.get('msg')}", 0.0
    data = raw.get("data", [{}])[0]
    return parse_holdings(raw), "", float(data.get("totalEq", 0) or 0)


# --------------------------------------------------------------------------- #
# Session state: 勾选状态按币种 ID 保存（刷新/筛选后依然跟随币种）
# --------------------------------------------------------------------------- #
if "selected" not in st.session_state:
    st.session_state.selected = {}
if "buy_results" not in st.session_state:
    st.session_state.buy_results = None
if "sell_results" not in st.session_state:
    st.session_state.sell_results = None

# 新版 Streamlit 禁止在控件实例化后直接改写它的 session_state，
# 因此按钮要重置勾选框/输入框时只登记标记，待下一轮在控件渲染前统一清空
_pending_reset = st.session_state.pop("_pending_widget_reset", None)
if _pending_reset:
    for _key, _value in _pending_reset.items():
        st.session_state[_key] = _value


def get_selected() -> list[str]:
    return [i for i, v in st.session_state.selected.items() if v]


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
holdings_all, api_err, total_eq = fetch_balance()
usdt_bal = holdings_all.get("USDT", 0.0) if holdings_all else 0.0
mode_badge = (
    '<span style="color:#F0B90B; font-weight:bold;">🧪 模拟盘</span>' if cfg["use_demo"]
    else '<span style="color:#FF4B4B; font-weight:bold;">🔴 实盘</span>'
)
if api_err:
    status_html = (
        '<span style="color:#FF4B4B; font-weight:bold;">❌ API 密钥无效</span>'
        '<span style="color:#8B949E;">（请在左侧「⚙️ API 配置」中检查）</span>'
    )
else:
    status_html = (
        f'💰 可用 USDT: <b style="color:#E6EDF3;">{usdt_bal:,.2f}</b>'
        f'<span style="color:#8B949E;"> | 账户权益 {total_eq:,.2f}</span>'
    )

st.markdown(
    '<h1 style="margin-bottom:0.2rem;">'
    '<span class="live-dot"></span>📊 OKX 批量交易</h1>'
    f'<div style="margin-bottom:1rem; color:#8B949E;">'
    f'{mode_badge} &nbsp;|&nbsp; {status_html}</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Sidebar: API 配置 + 筛选
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("## ⚙️ API 配置")
    with st.expander("密钥设置", expanded=bool(api_err or not cfg["api_key"])):
        if api_err:
            st.error(f"❌ 密钥无效：{api_err}")
            st.caption("常见原因：Passphrase 记错；或密钥是在「实时交易」环境创建的——"
                       "模拟盘需要到 OKX → API 管理 → 模拟交易 标签页单独创建。")
        elif not cfg["api_key"]:
            st.info("请填入 API Key / Secret Key / Passphrase")
        else:
            st.success(f"✅ 连接成功 | 账户权益 {total_eq:,.2f} USDT")

        st.caption("输入框留空 = 保持现有值不变。密钥只保存在本机 .env 文件里。")
        in_key = st.text_input("API Key", type="password", key="cfg_api_key",
                               placeholder="留空则不修改" if cfg["api_key"] else "请输入")
        in_secret = st.text_input("Secret Key", type="password", key="cfg_secret_key",
                                  placeholder="留空则不修改" if cfg["secret_key"] else "请输入")
        in_pass = st.text_input("Passphrase", type="password", key="cfg_passphrase",
                                placeholder="留空则不修改" if cfg["passphrase"] else "请输入")

        new_demo = st.toggle("模拟盘模式", value=cfg["use_demo"], key="cfg_use_demo",
                             help="切换后立即生效并保存。第一次使用请务必保持模拟盘！")
        if new_demo != cfg["use_demo"]:
            cfg["use_demo"] = new_demo
            set_key(ENV_PATH, "OKX_USE_DEMO", "True" if new_demo else "False")
            st.cache_data.clear()
            st.rerun()

        if st.button("💾 保存配置", width="stretch"):
            changed = False
            for val, name, env_name in [
                (in_key, "api_key", "OKX_API_KEY"),
                (in_secret, "secret_key", "OKX_SECRET_KEY"),
                (in_pass, "passphrase", "OKX_PASSPHRASE"),
            ]:
                if val.strip():
                    cfg[name] = val.strip()
                    set_key(ENV_PATH, env_name, val.strip())
                    changed = True
            if changed:
                st.session_state._pending_widget_reset = {
                    "cfg_api_key": "", "cfg_secret_key": "", "cfg_passphrase": ""
                }
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("没有填写任何新值")

    st.markdown("---")
    st.markdown("## 🔍 筛选")

    c1, c2 = st.columns(2)
    with c1:
        st.number_input("最低价", min_value=0.0, value=None,
                        placeholder="不限", key="min_price")
    with c2:
        st.number_input("最高价", min_value=0.0, value=None,
                        placeholder="不限", key="max_price")

    c3, c4 = st.columns(2)
    with c3:
        st.number_input("最小涨跌%", min_value=-100.0, value=None,
                        placeholder="不限", key="min_chg")
    with c4:
        st.number_input("最大涨跌%", min_value=-100.0, value=None,
                        placeholder="不限", key="max_chg")

    st.number_input("最小交易量 (USDT)", value=100_000.0,
                    step=50_000.0, format="%.0f", key="min_vol")
    st.text_input("搜索交易对", "", key="search")
    st.toggle("只看已持仓", value=False, key="only_held")

    st.markdown("---")
    st.markdown("## ⚙️ 刷新设置")
    st.selectbox("自动刷新间隔", options=[3, 5, 10, 30], index=1,
                 format_func=lambda x: f"{x} 秒", key="refresh_interval")
    st.toggle("启用自动刷新", value=True, key="auto_refresh")

    st.markdown("---")
    if st.button("🔄 立即刷新", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# --------------------------------------------------------------------------- #
# 行情表格（fragment 自动刷新，不打扰下方买卖按钮）
# --------------------------------------------------------------------------- #
def market_fragment():
    tickers = fetch_tickers()
    if not tickers:
        st.error("获取行情失败，请检查代理连接（确保 OKX 客户端已打开）")
        return

    holdings = fetch_balance()[0] or {}

    df = pd.DataFrame(tickers)
    for col in ["last", "open24h", "volCcy24h"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["change_pct"] = ((df["last"] - df["open24h"]) / df["open24h"] * 100).round(2)
    df["base"] = df["instId"].str.split("-").str[0]
    df["持仓数量"] = df["base"].map(lambda c: holdings.get(c, 0.0))
    df["持仓价值"] = (df["持仓数量"] * df["last"]).round(2)

    # 应用筛选
    f = df
    if st.session_state.min_price is not None:
        f = f[f["last"] >= st.session_state.min_price]
    if st.session_state.max_price is not None:
        f = f[f["last"] <= st.session_state.max_price]
    if st.session_state.min_chg is not None:
        f = f[f["change_pct"] >= st.session_state.min_chg]
    if st.session_state.max_chg is not None:
        f = f[f["change_pct"] <= st.session_state.max_chg]
    f = f[f["volCcy24h"] >= st.session_state.min_vol]
    if st.session_state.only_held:
        f = f[f["持仓数量"] > 0]
    if st.session_state.search:
        f = f[f["instId"].str.contains(st.session_state.search, case=False, na=False)]

    # 按交易对名稳定排序（保证勾选状态与行的对应关系不被刷新打乱）
    f = f.sort_values("instId").reset_index(drop=True)
    f["勾选"] = f["instId"].map(lambda i: st.session_state.selected.get(i, False))

    # 概览
    gainers = (f["change_pct"] > 0).sum()
    losers = (f["change_pct"] < 0).sum()
    n_sel = len(get_selected())
    sel_info = f'<span style="color:#00D4AA;">☑ 已选 <b>{n_sel}</b> 个</span>' if n_sel else ""
    st.markdown(
        f'<div style="display:flex; gap:2rem; margin-bottom:0.5rem; align-items:center;">'
        f'<span>📊 共 <b>{len(f)}</b> 个交易对</span>'
        f'<span style="color:#00D4AA;">▲ {gainers} 上涨</span>'
        f'<span style="color:#FF4B4B;">▼ {losers} 下跌</span>'
        f'{sel_info}'
        f'<span style="margin-left:auto; font-size:0.85rem; opacity:0.7;">'
        f'⏱ {datetime.now().strftime("%H:%M:%S")}</span></div>',
        unsafe_allow_html=True,
    )

    # key 随行集合变化：筛选条件改变导致行增删时换一个新表格控件，
    # 旧的按行号记录的编辑状态自动作废，避免勾选错挂到别的币上
    editor_key = "market_editor_" + str(hash(tuple(f["instId"])))

    edited = st.data_editor(
        f[["勾选", "instId", "last", "change_pct", "volCcy24h", "持仓数量", "持仓价值"]],
        key=editor_key,
        hide_index=True,
        width="stretch",
        column_config={
            "勾选": st.column_config.CheckboxColumn("勾选", default=False, width="small"),
            "instId": st.column_config.TextColumn("交易对"),
            "last": st.column_config.NumberColumn("最新价", format="%.6g"),
            "change_pct": st.column_config.NumberColumn("24h涨跌%", format="%.2f"),
            "volCcy24h": st.column_config.NumberColumn("24h交易量", format="%.0f"),
            "持仓数量": st.column_config.NumberColumn("持仓数量", format="%.8g"),
            "持仓价值": st.column_config.NumberColumn("持仓价值", format="%.2f"),
        },
        disabled=["instId", "last", "change_pct", "volCcy24h", "持仓数量", "持仓价值"],
    )

    # 渲染后把用户勾选的变动按币种写回 selected（跨刷新保存在这里）
    changed = edited["勾选"] != f["勾选"]
    for idx in f.index[changed]:
        st.session_state.selected[f.at[idx, "instId"]] = bool(edited.at[idx, "勾选"])


auto = st.session_state.get("auto_refresh", True)
interval = st.session_state.get("refresh_interval", 5)

if auto:
    @st.fragment(run_every=interval)
    def auto_market_fragment():
        market_fragment()

    auto_market_fragment()
else:
    market_fragment()

# --------------------------------------------------------------------------- #
# 结果展示
# --------------------------------------------------------------------------- #
def show_results(results: list[dict] | None, title: str):
    if not results:
        return
    ok = sum(1 for r in results if r["code"] == "0")
    fail = len(results) - ok
    if fail == 0:
        st.success(f"{title}完成：{ok} 笔全部成功 ✅")
    else:
        st.warning(f"{title}：成功 {ok} 笔，失败 {fail} 笔（详情见下表）")
    st.dataframe(
        pd.DataFrame(results)[["instId", "sz", "code", "msg", "ordId"]].rename(
            columns={"instId": "交易对", "sz": "数量/金额", "code": "状态码",
                     "msg": "信息", "ordId": "订单号"}
        ),
        hide_index=True,
        width="stretch",
    )


can_trade = bool(cfg["api_key"]) and not api_err

# --------------------------------------------------------------------------- #
# 批量买入
# --------------------------------------------------------------------------- #
st.markdown("## 🛒 批量买入")
selected = get_selected()
b1, b2 = st.columns(2)
with b1:
    buy_amount = st.number_input("每币买入金额 (USDT)", min_value=1.0,
                                 value=100.0, step=10.0, key="buy_amount")
with b2:
    total_cost = buy_amount * len(selected)
    st.markdown(
        f'<div style="padding:0.4rem 0;">已选 <b>{len(selected)}</b> 个币种，'
        f'预计总花费 <b style="color:#00D4AA;">{total_cost:,.2f} USDT</b>，'
        f'可用余额 {usdt_bal:,.2f} USDT</div>',
        unsafe_allow_html=True,
    )

insufficient = selected and total_cost > usdt_bal
if insufficient:
    st.error(f"❌ 余额不足：需要 {total_cost:,.2f} USDT，可用 {usdt_bal:,.2f} USDT")
if selected:
    st.caption("已选：" + "、".join(selected))
if not can_trade:
    st.info("请先在左侧「⚙️ API 配置」中配置有效密钥，才能交易")

confirm_buy = st.checkbox("我确认要执行以上买入操作", key="confirm_buy")
if st.button("🚀 一键买入", type="primary",
             disabled=not (can_trade and selected and confirm_buy and not insufficient)):
    orders = [{"instId": i, "sz": buy_amount} for i in selected]
    with st.spinner("正在下单..."):
        st.session_state.buy_results = trader.batch_buy(orders)
    st.session_state.selected = {}
    st.session_state._pending_widget_reset = {"confirm_buy": False}
    st.rerun()

show_results(st.session_state.buy_results, "买入")

# --------------------------------------------------------------------------- #
# 批量卖出
# --------------------------------------------------------------------------- #
st.markdown("## 💰 批量卖出")
sell_mode = st.radio("卖出方式", ["全部卖出", "按金额卖出"],
                     horizontal=True, key="sell_mode")

s1, s2 = st.columns(2)
with s1:
    if sell_mode == "按金额卖出":
        st.number_input("每币卖出金额 (USDT)", min_value=1.0,
                        value=100.0, step=10.0, key="sell_amount")
    else:
        st.markdown('<div style="padding:0.4rem 0;">卖出已选币种的全部持仓</div>',
                    unsafe_allow_html=True)
with s2:
    holdings_now = holdings_all or {}
    no_hold = [i for i in selected if holdings_now.get(i.split("-")[0], 0.0) <= 0]
    st.markdown(
        f'<div style="padding:0.4rem 0;">已选 <b>{len(selected)}</b> 个币种'
        + (f'，其中 <b style="color:#FF4B4B;">{len(no_hold)} 个无持仓</b>' if no_hold else "")
        + "</div>",
        unsafe_allow_html=True,
    )

confirm_sell = st.checkbox("我确认要执行以上卖出操作", key="confirm_sell")
if st.button("💸 一键卖出", type="primary",
             disabled=not (can_trade and selected and confirm_sell)):
    raw = trader.check_api()
    if raw.get("code") != "0":
        st.error(f"获取持仓失败：{raw.get('code')} {raw.get('msg')}")
    else:
        if sell_mode == "按金额卖出":
            orders = [{"instId": i, "sz": st.session_state.sell_amount, "mode": "amount"}
                      for i in selected]
        else:
            orders = [{"instId": i, "mode": "all"} for i in selected]
        with st.spinner("正在下单..."):
            st.session_state.sell_results = trader.batch_sell(orders, parse_holdings(raw))
        st.session_state.selected = {}
        st.session_state._pending_widget_reset = {"confirm_sell": False}
        st.rerun()

show_results(st.session_state.sell_results, "卖出")

st.markdown("---")
st.caption("⚠️ 交易有风险，本工具不构成任何投资建议。批量下单为逐单执行，中途失败不影响已成交订单。")
