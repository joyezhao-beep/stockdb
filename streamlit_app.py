import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="宏观&A股四维复盘看板", layout="wide")
tab_gold, tab_a = st.tabs(["🟡 黄金宏观因子观测", "🟢 A股四维大盘复盘看板"])

# ===================== 黄金模块（财联社快讯） =====================
with tab_gold:
    st.header("黄金驱动宏观因子")
    st.warning("⚠️ 黄金相关海外数据依赖yfinance，Streamlit云环境容易超时；失败仅本板块告警，A股不受影响")
    st.caption("金价核心驱动：TIPS实际利率 > 美元指数 > 央行购金 > 通胀 & 恐慌")

    try:
        import yfinance as yf
        tickers = ["^TIP", "^TNX", "DX-Y.NYB", "GC=F"]
        end = datetime.now()
        start = end - timedelta(days=250)
        raw = yf.download(tickers, start=start, end=end)["Close"]
        raw.columns = ["TIPS_10Y", "美债10Y", "DXY美元指数", "COMEX黄金"]
        raw = raw.dropna()

        fig_gold = go.Figure()
        fig_gold.add_trace(go.Scatter(x=raw.index, y=raw["TIPS_10Y"], name="10Y TIPS实际利率", yaxis="y1"))
        fig_gold.add_trace(go.Scatter(x=raw.index, y=raw["COMEX黄金"], name="COMEX黄金", yaxis="y2"))
        fig_gold.update_layout(yaxis2=dict(overlaying="y", side="right"), title="TIPS实际利率 vs COMEX黄金")
        st.plotly_chart(fig_gold, use_container_width=True)

        fig_dxy = px.line(raw, x=raw.index, y="DXY美元指数", title="美元指数DXY")
        st.plotly_chart(fig_dxy, use_container_width=True)

    except Exception as e:
        st.warning(f"海外行情接口拉取失败：{e}")

    st.subheader("全球央行购金（月度低频）")
    st.info("央行购金公开免费高频接口较少，需要定期手动更新月度数据")

    st.divider()
    st.subheader("📰 财联社快讯（黄金/美联储/央行/大宗商品）")
    try:
        clsa_df = ak.news_clsa_em()
        keyword_filter = ["黄金", "金价", "贵金属", "美联储", "议息", "美债", "央行", "购金", "美元", "通胀", "CPI", "PCE"]
        def match_title(title):
            return any(k in title for k in keyword_filter)
        clsa_filtered = clsa_df[clsa_df["标题"].apply(match_title)].reset_index(drop=True)

        if len(clsa_filtered) == 0:
            st.info("暂无匹配关键词的快讯，可刷新页面重新拉取")
        else:
            for idx, row in clsa_filtered.iterrows():
                st.markdown(f"**【{row['时间']}】{row['标题']}**")
                st.caption(row["内容"])
                st.markdown("---")
    except Exception as e:
        st.warning(f"财联社快讯接口拉取失败：{e}")

# ===================== A股四维复盘模块 =====================
with tab_a:
    st.header("A股四维复盘：资金｜情绪｜估值｜动量")
    sub_all, sub_kc50, sub_sector, sub_note = st.tabs(["全市场大盘", "科创50对照", "核心板块强弱", "📝复盘笔记"])

    def calc_rps(series, period=120):
        ret = series.pct_change(period)
        rps = ret.rank(pct=True)*100
        return rps

    def render_index_dashboard(index_code, index_name):
        st.subheader(f"【{index_name}】四维跟踪")
        col1,col2,col3,col4 = st.columns(4)
        with col1: st.markdown("**💰资金面**")
        with col2: st.markdown("**😰情绪面**")
        with col3: st.markdown("**📊估值面**")
        with col4: st.markdown("**📈趋势动量RPS**")

        trade_df = None
        # ---- 资金面：成交额
        try:
            st.markdown("##### 指数成交额")
            trade_df = ak.stock_zh_a_hist(symbol=index_code, period="daily", start_date="20250101", adjust="qfq")
            fig_vol = px.line(trade_df, x="日期", y="成交额", title=f"{index_name} 成交额")
            st.plotly_chart(fig_vol, use_container_width=True)
        except Exception as e:
            st.warning(f"成交额数据失败：{e}")

        try:
            st.markdown("##### 北向资金")
            north = ak.stock_hsgt_hist_em(symbol="北向资金")
            fig_north = px.line(north, x="日期", y="当日成交净买额", title="北向资金当日净买入")
            st.plotly_chart(fig_north, use_container_width=True)
        except Exception as e:
            st.warning(f"北向资金失败：{e}")

        try:
            st.markdown("##### 两融余额")
            margin = ak.stock_margin_sse()
            # ✅ 这里修正：时间列是【信用交易日期】，不是“日期”
            fig_margin = px.line(margin, x="信用交易日期", y="融资余额", title="全市场融资余额")
            st.plotly_chart(fig_margin, use_container_width=True)
        except Exception as e:
            st.warning(f"两融数据失败：{e}")

        # ---- 情绪面
        try:
            st.markdown("##### 涨跌家数")
            updown = ak.stock_zh_a_spot_em()
            up = len(updown[updown["涨跌幅"]>0])
            down = len(updown[updown["涨跌幅"]<0])
            flat = len(updown[updown["涨跌幅"]==0])
            pie_df = pd.DataFrame({"方向":["上涨","下跌","平盘"], "数量":[up,down,flat]})
            fig_updown = px.pie(pie_df, values="数量", names="方向", title="当日涨跌家数")
            st.plotly_chart(fig_updown, use_container_width=True)
        except Exception as e:
            st.warning(f"涨跌家数失败：{e}（东财限流，等待一段时间再刷新）")

        # ---- 估值面
        st.markdown("##### 估值提示")
        st.info("PE/PB分位数、ERP股债溢价，免费akshare公开数据源有限，预留面板位置")

        # ---- 趋势动量 RPS
        if trade_df is not None and len(trade_df) > 0:
            try:
                trade_df["ma20"] = trade_df["收盘"].rolling(20).mean()
                trade_df["ma60"] = trade_df["收盘"].rolling(60).mean()
                fig_k = go.Figure()
                fig_k.add_trace(go.Scatter(x=trade_df["日期"], y=trade_df["收盘"], name="价格"))
                fig_k.add_trace(go.Scatter(x=trade_df["日期"], y=trade_df["ma20"], name="MA20"))
                fig_k.add_trace(go.Scatter(x=trade_df["日期"], y=trade_df["ma60"], name="MA60"))
                fig_k.update_layout(title=f"{index_name} K线+均线")
                st.plotly_chart(fig_k, use_container_width=True)
            except Exception as e:
                st.warning(f"指数趋势图失败：{e}")
        else:
            st.warning("指数K线图：行情数据获取失败，无法绘制均线图表")

    with sub_all:
        render_index_dashboard("000001", "上证大盘")

    with sub_kc50:
        render_index_dashboard("000688", "科创50")

    with sub_sector:
        st.subheader("核心板块RPS强弱扫描（东财）")
        sector_list = ["半导体", "蓝筹白马", "红利高股息", "创新药", "光伏锂电"]
        sel_sector = st.selectbox("选择板块查看", sector_list)
        st.info(f"正在加载【{sel_sector}】板块成分股，计算个股RPS相对强度")
        try:
            stock_df = ak.stock_board_industry_cons_em(name=sel_sector)
            st.dataframe(stock_df, use_container_width=True)
            st.caption("⚠️ 东财接口容易限流，短时间频繁刷新会断开，建议间隔几分钟再刷新")
        except Exception as e:
            st.warning(f"板块成分获取失败（东财限流）：{e}")

    with sub_note:
        st.subheader("📝 当日复盘笔记")
        note = st.text_area("在这里写下你的每日复盘：资金、情绪、板块判断、计划", height=350)
        st.download_button("下载复盘文本", note, file_name=f"复盘_{datetime.now().strftime('%Y%m%d')}.txt")

st.caption("⚠️ 免责声明：本页面仅为公开数据复盘工具，所有图表、指标、新闻不构成任何投资建议")
