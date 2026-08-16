import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

st.set_page_config(page_title="GUGUGUA 全自動選股系統", page_icon="🚀", layout="wide")

st.title("🚀 GUGUGUA 選股 - 基本面、新聞情緒與 SEPA 風控系統")
st.caption("全自動解析『財報、護城河、價值網、即時新聞情緒』與 SEPA 1% 風控")

# 側邊欄設定
st.sidebar.header("⚙️ 1. 股票與資金設定")
raw_ticker = st.sidebar.text_input("股票 / ETF 代號 (如 NVDA, 2330, 2303, 0056)", value="2330").strip().upper()

capital = st.sidebar.number_input("您的帳戶總資金 (NT$ 或 US$)", value=100000, step=10000)
market_ticker = st.sidebar.selectbox("對應大盤指數", ["^TWII (台股加權指數)", "^GSPC (標普500)"])

st.sidebar.markdown("---")
st.sidebar.header("🚩 2. 模式設定")
is_startup = st.sidebar.checkbox("🐣 新創 / 無歷史報表模式 (豁免財報限制)", value=False)
manual_override = st.sidebar.checkbox("🛠️ 啟用手動備用覆寫 (手動自訂護城河/價值網)", value=False)

if manual_override:
    st.subheader("🛠️ 備用手動覆寫面板 (已開啟手動控制)")
    col_m, col_v = st.columns(2)
    with col_m:
        m_override_1 = st.checkbox("手動認可：具特許技術/高資本壁壘", value=True)
        m_override_2 = st.checkbox("手動認可：具定價權（毛利穩定）", value=True)
        m_override_3 = st.checkbox("手動認可：轉換成本與規模壁壘高", value=True)
    with col_v:
        v_override_1 = st.checkbox("手動認可：顧客需求爆發性湧入", value=True)
        v_override_2 = st.checkbox("手動認可：競爭力甩開對手（無價格戰）", value=True)
        v_override_3 = st.checkbox("手動認可：供應鏈與現金流抗風險強", value=True)

st.markdown("---")

# 快取數據抓取函數（快取 1 小時，避免被 Yahoo 限流）
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker_symbol):
    stock_obj = yf.Ticker(ticker_symbol)
    history_df = stock_obj.history(period="2y")
    
    # 若抓取不到，回傳空值
    if history_df is None or history_df.empty:
        return None, None, None, None, None

    # 嘗試抓取財報
    try:
        q_fin = stock_obj.quarterly_income_stmt
        if q_fin is None or q_fin.empty:
            q_fin = stock_obj.quarterly_financials
    except Exception:
        q_fin = None

    # 嘗試抓取 Info
    try:
        info_dict = stock_obj.info
    except Exception:
        info_dict = {}

    # 嘗試抓取新聞
    try:
        news_data = stock_obj.news
    except Exception:
        news_data = []

    return history_df, q_fin, info_dict, news_data, ticker_symbol

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_data(mkt_sym):
    m_stock = yf.Ticker(mkt_sym)
    return m_stock.history(period="1y")

if st.sidebar.button("🔍 開始全自動深度檢核"):
    with st.spinner("正在安全提取數據與防限流解析中..."):
        try:
            df, q_fin, info, news_list, ticker_used = None, None, {}, [], raw_ticker

            # 自動嘗試代號順序
            if raw_ticker.isdigit():
                candidates = [f"{raw_ticker}.TW", f"{raw_ticker}.TWO"]
            else:
                candidates = [raw_ticker]

            for c_ticker in candidates:
                res_df, res_qfin, res_info, res_news, res_t = fetch_stock_data(c_ticker)
                if res_df is not None and not res_df.empty:
                    df, q_fin, info, news_list, ticker_used = res_df, res_qfin, res_info, res_news, res_t
                    break

            if df is None or df.empty or len(df) < 10:
                st.error(f"❌ 查無代號 {raw_ticker} 或目前受到 Yahoo 流量限制，請稍候 1~2 分鐘後重試！")
            else:
                mkt_symbol = market_ticker.split(" ")[0]
                mkt_df = fetch_market_data(mkt_symbol)
                
                is_etf = raw_ticker.startswith("00") or "ETF" in raw_ticker

                # ==========================================
                # 1. 財報（看過去）自動運算
                # ==========================================
                rev_growth, eps_growth, gross_margin = 0.0, 0.0, 0.0
                chk_finance = False
                financial_status = "❌ 未達標"
                fin_details = {}

                if is_startup:
                    chk_finance = True
                    financial_status = "🌱 新創豁免"
                elif is_etf:
                    chk_finance = True
                    financial_status = "ℹ️ ETF 商品"
                else:
                    rev_aliases = ['Total Revenue', 'Operating Revenue', 'OperatingRevenue', 'Revenue']
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

                            fin_details = {
                                "最新季營收": f"{rev_c:,.0f}",
                                "營收季增率 (QoQ)": f"{rev_growth:+.2f}% (標準 > 15%)",
                                "最新季淨利": f"{net_c:,.0f}",
                                "淨利季增率 (QoQ)": f"{eps_growth:+.2f}% (標準 > 20%)",
                                "最新季毛利率": f"{gross_margin:.2f}%"
                            }
                            if eps_growth > 20 and rev_growth > 15:
                                chk_finance = True
                                financial_status = "✅ 通過"
                        except Exception:
                            pass

                    if not fin_details and info:
                        rev_growth = (info.get('revenueGrowth', 0) or 0) * 100
                        eps_growth = (info.get('earningsGrowth', 0) or 0) * 100
                        gross_margin = (info.get('grossMargins', 0) or 0) * 100
                        fin_details = {
                            "營收年增率 (YoY)": f"{rev_growth:+.2f}% (標準 > 15%)",
                            "盈餘年增率 (YoY)": f"{eps_growth:+.2f}% (標準 > 20%)",
                            "毛利率": f"{gross_margin:.2f}%"
                        }
                        if eps_growth > 20 and rev_growth > 15:
                            chk_finance = True
                            financial_status = "✅ 通過"

                # ==========================================
                # 2. 護城河（看現在）自動量化運算
                # ==========================================
                roe = (info.get('returnOnEquity', 0) or 0) * 100 if info else 0
                op_margin = (info.get('operatingMargins', 0) or 0) * 100 if info else 0
                g_margin = gross_margin if gross_margin > 0 else ((info.get('grossMargins', 0) or 0) * 100 if info else 0)

                auto_moat_1 = (roe >= 15.0) or (roe == 0 and g_margin >= 35.0)
                auto_moat_2 = g_margin >= 30.0
                auto_moat_3 = op_margin >= 15.0 or (op_margin == 0 and g_margin >= 35.0)

                if manual_override:
                    moat_passed = m_override_1 and m_override_2 and m_override_3
                else:
                    moat_passed = (auto_moat_1 and auto_moat_2 and auto_moat_3) if not is_etf else True

                moat_details = {
                    "ROE 股東權益報酬率 (資本壁壘)": f"{roe:.2f}% ({'✅ 通過 >=15%' if auto_moat_1 else '❌ 未達標'})",
                    "毛利率 (定價權/成本轉嫁)": f"{g_margin:.2f}% ({'✅ 通過 >=30%' if auto_moat_2 else '❌ 未達標'})",
                    "營業利益率 (規模與轉換壁壘)": f"{op_margin:.2f}% ({'✅ 通過 >=15%' if auto_moat_3 else '❌ 未達標'})"
                }

                # ==========================================
                # 3. 價值網（看未來）自動量化運算
                # ==========================================
                net_margin = (info.get('profitMargins', 0) or 0) * 100 if info else 0
                curr_ratio = info.get('currentRatio', 0) or 0.0 if info else 0.0

                auto_vnet_1 = rev_growth >= 10.0
                auto_vnet_2 = net_margin >= 10.0 or (net_margin == 0 and g_margin >= 30.0)
                auto_vnet_3 = (curr_ratio >= 1.2) or (curr_ratio == 0.0)

                if manual_override:
                    vnet_passed = v_override_1 and v_override_2 and v_override_3
                else:
                    vnet_passed = (auto_vnet_1 and auto_vnet_2 and auto_vnet_3) if not is_etf else True

                vnet_details = {
                    "【顧客需求湧入】營收成長動能": f"{rev_growth:+.2f}% ({'✅ 通過 >=10%' if auto_vnet_1 else '❌ 未達標'})",
                    "【甩開價格戰】稅後淨利率": f"{net_margin:.2f}% ({'✅ 通過 >=10%' if auto_vnet_2 else '❌ 未達標'})",
                    "【供應鏈與現金抗風險】流動比率": f"{curr_ratio:.2f} ({'✅ 通過 >=1.2' if auto_vnet_3 else '❌ 未達標'})"
                }

                # ==========================================
                # 4. 新聞即時輿情與情緒分析
                # ==========================================
                pos_words = ['surge', 'jump', 'beat', 'gain', 'growth', 'record', 'high', 'boost', 'upgrade', 'profit', '創高', '大增', '買進', '看好', '成長', '突破']
                neg_words = ['fall', 'drop', 'plunge', 'loss', 'miss', 'cut', 'downgrade', 'slump', 'risk', 'warning', '衰退', '跌破', '虧損', '下修', '風險', '警訊']
                
                pos_count, neg_count = 0, 0
                parsed_news = []

                if news_list:
                    for item in news_list[:6]:
                        title = item.get('title', '')
                        publisher = item.get('publisher', '財經新聞')
                        link = item.get('link', '#')
                        p_time = item.get('providerPublishTime', None)
                        time_str = datetime.fromtimestamp(p_time).strftime('%Y-%m-%d %H:%M') if p_time else "近期"
                        
                        title_lower = title.lower()
                        for pw in pos_words:
                            if pw in title_lower: pos_count += 1
                        for nw in neg_words:
                            if nw in title_lower: neg_count += 1

                        parsed_news.append({"時間": time_str, "來源": publisher, "標題": f"[{title}]({link})"})

                if pos_count > neg_count:
                    news_sentiment = "🔥 正向偏多"
                    news_desc = f"正向詞彙 {pos_count} / 負向詞彙 {neg_count}"
                elif neg_count > pos_count:
                    news_sentiment = "⚠️ 負向偏空"
                    news_desc = f"正向詞彙 {pos_count} / 負向詞彙 {neg_count}"
                else:
                    news_sentiment = "⚖️ 中性平穩"
                    news_desc = "近期無重大極端消息"

                # ==========================================
                # 5. 技術面 (SEPA) 自動運算
                # ==========================================
                chk_mkt = False
                if mkt_df is not None and len(mkt_df) >= 50:
                    mkt_sma50 = mkt_df['Close'].rolling(50).mean().iloc[-1]
                    chk_mkt = mkt_df['Close'].iloc[-1] > mkt_sma50

                df['SMA50'] = df['Close'].rolling(50).mean()
                df['SMA150'] = df['Close'].rolling(150).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()
                
                curr_price = df['Close'].iloc[-1]
                sma50 = df['SMA50'].iloc[-1]
                
                if len(df) >= 200 and not np.isnan(df['SMA200'].iloc[-1]):
                    sma150 = df['SMA150'].iloc[-1]
                    sma200 = df['SMA200'].iloc[-1]
                    chk_ma = (curr_price > sma50 > sma150 > sma200)
                elif len(df) >= 150 and not np.isnan(df['SMA150'].iloc[-1]):
                    sma150 = df['SMA150'].iloc[-1]
                    chk_ma = (curr_price > sma50 > sma150)
                else:
                    chk_ma = (curr_price > sma50)

                chk_vcp = False
                if len(df) >= 20:
                    vol_recent = df['Volume'].iloc[-5:].mean()
                    vol_prior = df['Volume'].iloc[-20:-5].mean()
                    range_recent = (df['High'].iloc[-5:] - df['Low'].iloc[-5:]).mean()
                    range_prior = (df['High'].iloc[-20:-5] - df['Low'].iloc[-20:-5]).mean()
                    chk_vcp = (vol_recent < vol_prior) and (range_recent < range_prior)

                chk_tech = chk_mkt and chk_ma and chk_vcp

                # ==========================================
                # 綜合診斷看板展示
                # ==========================================
                st.subheader(f"📊 {raw_ticker} ({ticker_used}) GUGUGUA 全方位五大維度看板")
                
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("1. 財報 (過去)", financial_status, f"EPS {eps_growth:+.1f}% / 營收 {rev_growth:+.1f}%" if fin_details else "無數據")
                m2.metric("2. 護城河 (現在)", "✅ 具備強護城河" if moat_passed else "❌ 護城河不足", "自動計算 ROE/毛利/營業利益")
                m3.metric("3. 價值網 (未來)", "✅ 具爆發擴張力" if vnet_passed else "❌ 價值網受阻", "自動計算 營收動能/淨利率/流動比")
                m4.metric("4. 新聞輿情", news_sentiment, news_desc)
                m5.metric("5. 技術面 (SEPA)", "✅ 多頭突破臨界" if chk_tech else "❌ 結構未達標", "大盤/均線多頭/VCP量縮")

                with st.expander("📑 查看系統自動抓取的【護城河、價值網與財報】完整量化明細", expanded=False):
                    c_a, c_b = st.columns(2)
                    with c_a:
                        st.markdown("#### 🏰 護城河量化明細")
                        st.table(pd.DataFrame(list(moat_details.items()), columns=["指標名稱", "數值與標準"]))
                    with c_b:
                        st.markdown("#### 🌐 價值網量化明細")
                        st.table(pd.DataFrame(list(vnet_details.items()), columns=["指標名稱", "數值與標準"]))

                if parsed_news:
                    with st.expander(f"📰 查看 {raw_ticker} 最新相關即時財經新聞 ({len(parsed_news)} 則)", expanded=True):
                        for n in parsed_news:
                            st.markdown(f"- **[{n['時間']}]** ({n['來源']}) {n['標題']}")
                else:
                    st.info("ℹ️ 近期暫無此股票之重大新聞流。")

                all_passed = chk_finance and moat_passed and vnet_passed and chk_tech

                if all_passed:
                    st.success("🎉 恭喜！該公司在『財報、護城河、價值網與 SEPA 技術突破』全數滿分通過，極具戰略建倉價值！")
                    
                    stop_price = df['Low'].iloc[-10:].min()
                    risk_per_share = curr_price - stop_price
                    risk_pct = (risk_per_share / curr_price) * 100 if curr_price > 0 else 0
                    
                    max_risk_amount = capital * 0.01
                    shares_to_buy = int(max_risk_amount // risk_per_share) if risk_per_share > 0 else 0
                    exposure = shares_to_buy * curr_price
                    
                    st.markdown("---")
                    st.subheader("🦅 1% 風險控管建議買入部位")
                    st.write(f"- 當前突破價：**${curr_price:.2f}**")
                    st.write(f"- 自動建議硬停損價：**${stop_price:.2f}** (停損距離: {risk_pct:.1f}%)")
                    
                    if risk_pct > 8.0:
                        st.warning("⚠️ 警告：目前停損距離超過 8%，代表波動收縮不夠緊密，建議等待價格重新整理！")
                    
                    st.markdown(f"👉 **建議買入數量：:red[{shares_to_buy:,} 股]**")
                    st.write(f"- 單筆最大承擔虧損 (1%)：**${max_risk_amount:,.2f}**")
                    st.write(f"- 動用總資金 (名目曝險)：**${exposure:,.2f}** (佔帳戶 {(exposure/capital)*100:.1f}%)")
                else:
                    st.error("⛔ 交易否決：未完全符合嚴格標準，系統已自動為您攔截潛在投資風險！")

        except Exception as e:
            st.error(f"資料抓取失敗或數據不足：{e}")
