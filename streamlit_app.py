import streamlit as st
import akshare as ak
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="A股RPS行情看板", layout="wide")
st.title("📈 A股RPS行情看板")

# 大盘指数（接口已更换为 index_zh_spot_sina）
st.subheader("大盘指数")
try:
    index_df = ak.index_zh_spot_sina()
    show_cols = ["代码", "名称", "最新价", "涨跌幅", "成交量"]
    st.dataframe(index_df[show_cols], use_container_width=True)
except Exception as e:
    st.warning(f"大盘数据获取失败：{e}")

# 北向资金（修改y轴字段：当日成交净买额）
st.subheader("北向资金")
try:
    north_df = ak.stock_hsgt_hist_em(symbol="北向资金")
    fig_north = px.line(north_df, x="日期", y="当日成交净买额", title="北向资金净流入")
    st.plotly_chart(fig_north, use_container_width=True)
except Exception as e:
    st.warning(f"北向数据获取失败：{e}")

# 行业板块涨幅榜
st.subheader("行业板块涨幅榜")
try:
    sector_df = ak.stock_board_industry_name_em()
    fig_sector = px.bar(sector_df.head(20), x="板块名称", y="涨跌幅", title="板块涨跌幅TOP20")
    st.plotly_chart(fig_sector, use_container_width=True)
except Exception as e:
    st.warning(f"板块数据获取失败：{e}")

st.caption("⚠️ 说明：本页面仅用于数据复盘，不构成任何投资建议")
