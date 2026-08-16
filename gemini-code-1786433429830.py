import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

st.set_page_config(page_title="GUGUGUA 雙軌選股與風控系統", page_icon="🦅", layout="wide")

st.title("🦅 GUGUGUA 智能選股系統：成長價差 vs 穩健領息")
st.caption("專為新手設計：自動分析『高成長飆股突破』與『穩健護城河領息』雙軌策略，搭配白話文解析與 1% 風控")

# 側邊欄設定
st.sidebar.header("⚙️ 1. 股票與資金設定")
raw_ticker = st.sidebar.text_input("股票 / ETF 代號 (如 2330, 2412, NVDA, 0056)", value="0056").strip().upper()

capital = st.sidebar.number_input("您的可用投資閒錢 (NT$ 或 US$)", value=100000, step=10000, help="請輸入專門用於股票投資的閒置資金，切勿輸入生活費或緊急預備金")
market_ticker = st.sidebar.selectbox("對應大盤指數", ["^TWII (台股加權指數)", "^GSPC (標普500)"])

st.sidebar.markdown("---")
st.sidebar.header("🚩 2. 特殊彈性設定")
is_startup = st.sidebar.checkbox("🐣 新創 / 轉型股模式 (豁免過去財報限制)", value=False)
manual_override = st.sidebar.checkbox("🛠️ 啟用手動覆寫面板", value=False)

if manual_override:
    st.subheader("🛠️ 備用手動覆寫面板")
    col_m, col_v = st.columns(2)
    with col_m:
        m_override_1 = st.checkbox("手動認可：具特許技術/高資本壁壘", value=True)
        m_override_2 = st.checkbox("手動認可：具定價權（毛利穩定）", value=True)
    with col_v:
        v_override_1 = st.checkbox("手動認可：顧客需求湧入", value=True)
        v_override_2 = st.checkbox("手動認可：供應鏈與現金流抗風險強", value=True)

st.markdown("---")

# 安全新聞抓取（RSS Feed 防限流）
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_rss_news(symbol):
    news_items = []
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:6]:
                title = item.find('title').text if item.find('title') is not None else ''
                link = item.find('link').text if item.find('link') is not None else '#'
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else '近期'
                news_items.append({
                    "時間": pub_date[:16],
                    "媒體": "Yahoo Finance",
                    "標題": title,
                    "網址": link
                })
    except Exception:
        pass
    return news_items

# 快取數據抓取函數
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker_symbol):
    try:
        history_df = yf.download(ticker_symbol, period="2y", progress=False)
        if isinstance(history_df.columns, pd.MultiIndex):
            history_df.columns = history_df.columns.get_level_values(0)

        if history_df is None or history_df.empty:
            stock_obj = yf.Ticker(ticker_symbol)
            history_df = stock_obj.history(period="2y")
        else:
            stock_obj = yf.Ticker(ticker_symbol)

        if history_df is None or history_df.empty:
            return None, None, None, ticker_symbol

        try:
            q_fin = stock_obj.quarterly_income_stmt
            if q_fin is None or q_fin.empty:
                q_fin = stock_obj.quarterly_financials
        except Exception:
            q_fin = None

        try:
            info_dict = stock_obj.fast_info
            info_data = {
                'marketCap': getattr(info_dict, 'market_cap', 0),
                'lastPrice': getattr(info_dict, 'last_price', 0)
            }
        except Exception:
            info_data = {}

        return history_df, q_fin, info_data, ticker_symbol
    except Exception:
        return None, None, None, ticker_symbol

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_data(mkt_sym):
    try:
        mkt_df = yf.download(mkt_sym, period="1y", progress=False)
        if isinstance(mkt_df.columns, pd.MultiIndex):
            mkt_df.columns = mkt_df.columns.get_level_values(0)
        return mkt_df
    except Exception:
        return None

if st.sidebar.button("🔍 開始全方位智能診斷"):
    with st.spinner("正在自動運算財報、護城河、技術線型與即時新聞..."):
        try:
            df, q_fin, info, ticker_used = None, None, {}, raw_ticker

            if raw_ticker.isdigit():
                candidates = [f"{raw_ticker}.TW", f"{raw_ticker}.TWO"]
            else:
                candidates = [raw_ticker]

            for c_ticker in candidates:
                res_df, res_qfin, res_info, res_t = fetch_stock_data(c_ticker)
                if res_df is not None and not res_df.empty:
                    df, q_fin, info, ticker_used = res_df, res_qfin, res_info, res_t
                    break

            if df is None or df.empty or len(df) < 5:
                st.error(f"❌ 查無代號 {raw_ticker}，請確認代號格式是否正確！")
            else:
                mkt_symbol = market_ticker.split(" ")[0]
                mkt_df = fetch_market_data(mkt_symbol)
                is_etf = raw_ticker.startswith("00") or "ETF" in raw_ticker

                # 1. 規模判斷
                market_cap = info.get('marketCap', 0) or 0
                is_large_cap = market_cap >= 10_000_000_000 or raw_ticker in ["2330", "2412", "NVDA", "AAPL", "MSFT", "2454", "2317"]
                
                if is_etf:
                    cap_label = "指數型 ETF 產品"
                elif is_large_cap:
                    cap_label = "大型權值巨頭"
                else:
                    cap_label = "中小型潛力股"

                req_eps = 15.0 if is_large_cap else 20.0
                req_rev = 10.0 if is_large_cap else 15.0

                # 2. 財報解析
                rev_growth, eps_growth, gross_margin = 0.0, 0.0, 0.0
                has_fin = False

                if is_startup or is_etf:
                    has_fin = True
                else:
                    rev_aliases = ['Total Revenue', 'Operating Revenue', 'Revenue']
                    net_aliases = ['Net Income', 'Net Income Common Stockholders', 'NetIncome']
                    gp_aliases = ['Gross Profit', 'GrossProfit']

                    rev_row = next((r for r in rev_aliases if q_fin is not None and r in q_fin.index), None)
                    net_row = next((r for r in net_aliases if q_fin is not None and r in q_fin.index), None)
                    gp_row = next((r for r in gp_aliases if q_fin is not None and r in q_fin.index), None)

                    if rev_row and net_row:
                        try:
                            rev_c = float(q_fin.loc[rev_row].iloc[0])
                            rev_p = float(q_fin.loc[rev_row].iloc[1])
                            net_c = float(q_fin.loc[net_row].iloc[0])
                            net_p = float(q_fin.loc[net_row].iloc[1])

                            if rev_p != 0: rev_growth = ((rev_c - rev_p) / abs(rev_p)) * 100
                            if net_p != 0: eps_growth = ((net_c - net_p) / abs(net_p)) * 100
                            if gp_row and rev_c != 0: gross_margin = (float(q_fin.loc[gp_row].iloc[0]) / rev_c) * 100
                            has_fin = True
                        except Exception:
                            pass

                # 3. 護城河與價值網
                moat_pass = gross_margin >= 25.0 or is_large_cap or is_etf
                vnet_pass = rev_growth >= 0.0 or is_large_cap or is_etf

                # 4. 技術面 (SEPA)
                df['SMA50'] = df['Close'].rolling(50).mean()
                df['SMA150'] = df['Close'].rolling(150).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()
                curr_price = float(df['Close'].iloc[-1])
                sma50 = float(df['SMA50'].iloc[-1])

                chk_ma = False
                if len(df) >= 200 and not np.isnan(df['SMA200'].iloc[-1]):
                    chk_ma = (curr_price > sma50 > float(df['SMA150'].iloc[-1]) > float(df['SMA200'].iloc[-1]))
                elif len(df) >= 150 and not np.isnan(df['SMA150'].iloc[-1]):
                    chk_ma = (curr_price > sma50 > float(df['SMA150'].iloc[-1]))
                else:
                    chk_ma = (curr_price > sma50)

                chk_vcp = False
                if len(df) >= 20:
                    vol_recent = df['Volume'].iloc[-5:].mean()
                    vol_prior = df['Volume'].iloc[-20:-5].mean()
                    range_recent = (df['High'].iloc[-5:] - df['Low'].iloc[-5:]).mean()
                    range_prior = (df['High'].iloc[-20:-5] - df['Low'].iloc[-20:-5]).mean()
                    chk_vcp = bool((vol_recent < vol_prior) and (range_recent < range_prior))

                growth_finance_pass = (eps_growth > req_eps and rev_growth > req_rev) if not (is_startup or is_etf) else True
                tech_sepa_pass = chk_ma and chk_vcp

                # ==========================================
                # 看板摘要展示
                # ==========================================
                st.subheader(f"📊 {raw_ticker} ({ticker_used}) 智能診斷摘要")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("公司屬性", cap_label, f"現價 NT$ {curr_price:.2f}")
                if is_etf:
                    c2.metric("最新季 EPS 成長率", "ETF 不適用", "一籃子分散持股")
                    c3.metric("最新季營收成長率", "ETF 不適用", "指數成分股配置")
                else:
                    c2.metric("最新季 EPS 成長率", f"{eps_growth:+.2f}%", f"門檻 > {req_eps}%")
                    c3.metric("最新季營收成長率", f"{rev_growth:+.2f}%", f"門檻 > {req_rev}%")

                st.markdown("---")

                # ==========================================
                # 雙軌策略診斷區塊
                # ==========================================
                tab_growth, tab_dividend = st.tabs(["🚀 策略 A：高成長技術突破（賺價差/飆股）", "🛡️ 策略 B：穩健護城河防禦（領股息/存股）"])

                # --- 策略 A：高成長價差 ---
                with tab_growth:
                    st.markdown("### 🎯 適合目標：追求短中期股價爆發力、賺取波段價差")
                    if growth_finance_pass and tech_sepa_pass and moat_pass and not is_etf:
                        st.success("✅ **【建議進場】符合高成長 SEPA 飆股突破標準！**")
                        
                        stop_price = float(df['Low'].iloc[-10:].min())
                        risk_per_share = curr_price - stop_price
                        risk_pct = (risk_per_share / curr_price) * 100 if curr_price > 0 else 0
                        max_risk_amount = capital * 0.01
                        shares_to_buy = int(max_risk_amount // risk_per_share) if risk_per_share > 0 else 0
                        exposure = shares_to_buy * curr_price

                        st.markdown("#### 🦅 1% 風險控管部位建議")
                        st.write(f"- 當前突破價：**NT$ {curr_price:.2f}**")
                        st.write(f"- 自動建議硬停損價：**NT$ {stop_price:.2f}** (停損幅度: {risk_pct:.1f}%)")
                        st.markdown(f"👉 **建議買入數量：:red[{shares_to_buy:,} 股]**")
                        st.write(f"- 單筆承擔最大風險 (1% 閒錢)：**NT$ {max_risk_amount:,.2f}**")
                        st.write(f"- 動用總資金 (名目曝險)：**NT$ {exposure:,.2f}** (佔投資閒錢 {(exposure/capital)*100:.1f}%)")
                    else:
                        st.error("⛔ **【暫不適合價差突破】未達飆股進場標準，原因如下：**")
                        
                        if is_etf:
                            st.write("ℹ️ **標的性質為指數型 ETF**：ETF 是一籃子股票分散組合，價格隨大盤指數緩步推進，天生缺乏單一個股的『高 EPS 爆發性』與『VCP 籌碼收斂突破型態』，不適合作為短線飆股價差操作。")
                        else:
                            if not growth_finance_pass:
                                st.write(f"❌ **獲利成長動能不足**：EPS 成長 {eps_growth:+.1f}% (門檻 >{req_eps}%) 或營收成長 {rev_growth:+.1f}% (門檻 >{req_rev}%)，代表近期沒有爆炸性業績支撐股價快速飆漲。")
                            if not chk_ma:
                                st.write("❌ **均線未呈多頭排列**：股價未處於均線之上發散（50MA > 150MA > 200MA），代表目前沒有主力大資金在強烈推升攻擊趨勢。")
                            if not chk_vcp:
                                st.write("❌ **波動未完成收縮 (VCP)**：近期價格波動幅度與成交量未呈現階梯式收窄，代表市場浮額尚未清洗乾淨，容易買在震盪洗盤區。")

                # --- 策略 B：穩健領息存股 ---
                with tab_dividend:
                    st.markdown("### 🛡️ 適合目標：追求長期穩定配息、低波動、睡得著覺的資產配置")
                    if is_etf or (moat_pass and vnet_pass and (gross_margin >= 20.0 or is_large_cap)):
                        st.success("✅ **【極為適合領息存股】具備頂級護城河與防禦體質！**")
                        if is_etf:
                            st.markdown(f"""
                            * **一籃子分散風險**：`{raw_ticker}` 為高股息/指數型 ETF，持有多檔優質龍頭成分股，完全免除單一公司倒閉或財報造假的下檔風險。
                            * **被動現金流首選**：成分股定期汰弱留強，配息穩定度高，是打造長期被動收入與退休資產配置的核心工具。
                            * **存股建議**：不需理會短期的技術線型震盪，適合採取**『定期定額分批買進、股息再投入』**策略長期累積張數。
                            """)
                        else:
                            st.markdown(f"""
                            * **護城河極深**：毛利率達 **{gross_margin:.1f}%** 且具備產業特許/龍頭地位，產品難以被對手取代。
                            * **營運穩健抗跌**：即便獲利沒有爆發性成長，但現金流與營收穩定，倒閉或大幅虧損風險極低。
                            * **存股建議**：此類股票不需理會短期的技術指標波動，適合採取**定期定額分批買進、長期領取股息**的配置策略。
                            """)
                    else:
                        st.warning("⚠️ **【領息需謹慎】** 該公司毛利較低或營運波動較大，長期存股需留意配息穩定度。")

                # ==========================================
                # 即時新聞列表
                # ==========================================
                parsed_news = fetch_rss_news(ticker_used)
                if parsed_news:
                    with st.expander(f"📰 查看 {raw_ticker} 即時新聞與直達連結 ({len(parsed_news)} 則)", expanded=True):
                        for n in parsed_news:
                            if n['網址'] and n['網址'] != '#':
                                st.markdown(f"- **[{n['時間']}]** `{n['媒體']}` 👉 [{n['標題']}]({n['網址']})")
                            else:
                                st.markdown(f"- **[{n['時間']}]** `{n['媒體']}` {n['標題']}")

        except Exception as e:
            st.error(f"資料抓取失敗或數據不足：{e}")
