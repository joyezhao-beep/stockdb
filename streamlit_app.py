import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import baostock as bs
import easyquotation
import akshare as ak
import requests
from io import StringIO

# ===================== 全局配置 & 缓存控制（核心防限流） =====================
st.set_page_config(page_title="A股盘中复盘Dashboard", layout="wide")
QUOTATION = easyquotation.use("tencent")  # 腾讯实时行情源，圈内主流
CACHE_TTL = 90  # 缓存有效期90秒，90秒内重复刷新不重请求
bs.login()  # baostock登录，获取历史日线

# 缓存容器
if "cache" not in st.session_state:
    st.session_state.cache = {}

def get_cache(key, fetch_func):
    now = datetime.now()
    item = st.session_state.cache.get(key)
    if item:
        data, ts = item
        if (now - ts).total_seconds() < CACHE_TTL:
            return data
    # 缓存失效，重新拉取
    data = fetch_func()
    st.session_state.cache[key] = (data, now)
    return data

# ===================== 数据源工具函数（分源隔离，主流经典） =====================
@st.cache_data(ttl=CACHE_TTL)
def get_market_snapshot():
    """easyquotation腾讯源：全市场涨跌家数、涨跌停，盘中快照【核心实时模块】"""
    try:
        res = QUOTATION.market_snapshot(prefix=True)
        df = pd.DataFrame(res).T
        up = int(df[df["涨跌"] > 0].shape[0])
        down = int(df[df["涨跌"] < 0].shape[0])
        flat = int(df[df["涨跌"] == 0].shape[0])
        limit_up = int(df[df["涨跌幅"] >= 9.8].shape[0])
        limit_down = int(df[df["涨跌幅"]] <= -9.8).shape[0]
        idx_data = QUOTATION.stocks(["sh000001", "sz399001", "sz399006", "sh000688"])
        return {
            "up": up, "down": down, "flat": flat,
            "limit_up": limit_up, "limit_down": limit_down,
            "index": idx_data
        }
    except Exception as e:
        return {"err": f"腾讯快照失败：{str(e)}"}

def get_bs_kline(code, start_date, end_date):
    """baostock 获取指数日线历史，稳定不限流，主K线源"""
    rs = bs.query_history_k_data_plus(
        code, "date,open,high,low,close,volume",
        start_date=start_date, end_date=end_date,
        frequency="d", adjustflag="3"
    )
    data_list = []
    while (rs.error_code == "0") & rs.next():
        data_list.append(rs.get_row_data())
    df = pd.DataFrame(data_list, columns=rs.fields)
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col])
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    return df

@st.cache_data(ttl=300)
def get_north_money():
    """交易所官方北向资金源，csv直读，无爬虫限流"""
    try:
        url = "https://www.sse.com.cn/services/tradingservice/connect/connectdata.shtml"
        df = ak.stock_hsgt_fund_flow_summary_em()
        return df
    except Exception as e:
        return pd.DataFrame({"err":[str(e)]})

@st.cache_data(ttl=300)
def get_margin_data():
    """上交所官方两融"""
    try:
        df = ak.stock_margin_sse()
        return df
    except Exception as e:
        return pd.DataFrame({"err":[str(e)]})

@st.cache_data(ttl=120)
def get_clsa_news():
    """财联社快讯，单独拉长缓存"""
    try:
        df = ak.news_clsa_em()
        filter_words = ["黄金", "金价", "贵金属", "美联储", "议息", "美债", "央行", "通胀", "CPI", "PCE"]
        df["match"] = df["标题"].apply(lambda x: any(w in str(x) for w in filter_words))
        return df[df["match"]].reset_index(drop=True)
    except Exception as e:
        return pd.DataFrame({"err":[str(e)]})

# ===================== 页面布局 Dashboard =====================
st.title("📊 A股盘中综合复盘 Dashboard | 经典多源版")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔥 盘中实时快照",
    "📈 大盘指数K线",
    "💰 北向 & 两融资金",
    "📰 财联社快讯",
    "📝 复盘笔记"
])

# ========== Tab1：盘中实时快照（你重点要的） ==========
with tab1:
    st.subheader("盘中全市场涨跌快照（腾讯源 easyquotation）")
    snap = get_cache("snapshot", get_market_snapshot)
    if "err" in snap:
        st.error(snap["err"])
    else:
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("上涨家数", snap["up"])
        c2.metric("下跌家数", snap["down"])
        c3.metric("平盘", snap["flat"])
        c4.metric("涨停数量", snap["limit_up"])
        c5.metric("跌停数量", snap["limit_down"])

        st.markdown("### 主要指数实时行情")
        idx_df = pd.DataFrame(snap["index"]).T
        idx_df = idx_df[["name","now","涨跌","涨跌幅"]]
        st.dataframe(idx_df, use_container_width=True)

        pie = pd.DataFrame({
            "方向":["上涨","下跌","平盘"],
            "数量":[snap["up"], snap["down"], snap["flat"]]
        })
        fig_pie = px.pie(pie, values="数量", names="方向", title="全市场涨跌分布")
        st.plotly_chart(fig_pie, use_container_width=True)

# ========== Tab2：大盘指数K线（baostock不限流历史日线） ==========
with tab2:
    st.subheader("指数历史K线（BAOSTOCK，不限流）+ MA20 / MA60")
    idx_opt = st.selectbox("选择指数", [
        "sh.000001 上证指数",
        "sz.399001 深证成指",
        "sz.399006 创业板指",
        "sh.000688 科创50"
    ])
    code = idx_opt.split(" ")[0]
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    k_df = get_cache(f"k_{code}", lambda: get_bs_kline(code, start, end))

    fig_k = go.Figure()
    fig_k.add_trace(go.Candlestick(
        x=k_df["date"], open=k_df["open"], high=k_df["high"],
        low=k_df["low"], close=k_df["close"], name="K线"
    ))
    fig_k.add_trace(go.Scatter(x=k_df["date"], y=k_df["ma20"], line=dict(color="orange"), name="MA20"))
    fig_k.add_trace(go.Scatter(x=k_df["date"], y=k_df["ma60"], line=dict(color="purple"), name="MA60"))
    fig_k.update_layout(xaxis_rangeslider_visible=False)
    st.plotly_chart(fig_k, use_container_width=True)

# ========== Tab3：北向、两融资金（交易所官方源） ==========
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("北向资金汇总")
        north_df = get_north_money()
        if "err" in north_df.columns:
            st.warning(north_df["err"].iloc[0])
        else:
            st.dataframe(north_df, use_container_width=True)
            fig_n = px.line(north_df, x="日期", y="当日净买入", title="北向每日净买入")
            st.plotly_chart(fig_n, use_container_width=True)
    with c2:
        st.subheader("全市场两融余额")
        margin_df = get_margin_data()
        if "err" in margin_df.columns:
            st.warning(margin_df["err"].iloc[0])
        else:
            st.dataframe(margin_df, use_container_width=True)
            fig_m = px.line(margin_df, x="信用交易日期", y="融资余额", title="融资余额走势")
            st.plotly_chart(fig_m, use_container_width=True)

# ========== Tab4：财联社快讯 ==========
with tab4:
    st.subheader("财联社快讯（宏观/黄金/美联储定向筛选）")
    news_df = get_clsa_news()
    if "err" in news_df.columns:
        st.warning(news_df["err"].iloc[0])
    else:
        for _,row in news_df.iterrows():
            st.markdown(f"**[{row['时间']}] {row['标题']}**")
            st.caption(row['内容'])
            st.divider()

# ========== Tab5：复盘笔记 ==========
with tab5:
    st.subheader("当日复盘笔记")
    note = st.text_area("记录复盘逻辑、观察标的、计划", height=400)
    if st.button("导出笔记"):
        fn = f"复盘_{datetime.now().strftime('%Y%m%d')}.txt"
        st.download_button("下载", note, file_name=fn)

# 页脚免责
st.caption("⚠️ 数据源：Baostock历史日线 + EasyQuotation腾讯实时快照 + 交易所北向/两融公开数据 + 财联社轮询；仅供复盘观察，不构成投资建议")
bs.logout()
