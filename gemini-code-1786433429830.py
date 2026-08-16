import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="GUGUGUA 選股系統", page_icon="🚀", layout="wide")

st.title("🚀 GUGUGUA 選股 - 全球公司完整財報與 SEPA 風控系統")
st.caption("通用全球/台股全公司財報自動解析，融合『財報、護城河、價值網』與 SEPA 1% 風控")

# 側邊欄設定
st.sidebar.header("⚙️ 1. 股票與資金設定")
raw_ticker = st.sidebar.text_input("股票 / ETF 代號 (全球美股代號或台股純數字)", value="2303").strip().upper()

capital = st.sidebar.number_input("您的帳戶總資金 (NT$ 或 US$)", value=100000, step=10000)
market_ticker = st.sidebar.selectbox("對應大盤指數", ["^TWII (台股加權指數)", "^GSPC (標普500)"])

st.sidebar.markdown("---")
st.sidebar.header("🚩 2. 模式設定")
is_startup = st.sidebar.checkbox("🐣 新創 / 無歷史報表模式 (豁免財報限制)", value=False)

# 主畫面：定性分析表
st.subheader("🏰 核心基本面：護城河與價值網定性檢核")
col_moat, col_vnet = st.columns(2)

with col_moat:
    st.markdown("### 1. 護城河評估（看現在）")
    moat_chk1 = st.checkbox("產品/技術具特許或示範資格，難被對手模仿取代", key="m1")
    moat_chk2 = st.checkbox("具備『定價權』或成本轉嫁能力（毛利率穩定/升級成本能消化）", key="m2")
    moat_chk3 = st.checkbox("客戶轉換成本高，或具備母公司/生態系資源疊加壁壘", key="m3")

with col_vnet:
    st.markdown("### 2. 價值網評估（看未來）")
    vnet_chk1 = st.checkbox("【顧客】受惠政策或趨勢，目標市場需求正在爆炸性湧入", key="v1")
    vnet_chk2 = st.checkbox("【互補者】整體產業生態系或母公司正在免費幫它放大價值", key="v2")
    vnet_chk3 = st.checkbox("【競爭者】市場呈現寡占或技術甩開對手，不必打惡性價格戰", key="v3")
    vnet_chk4 = st.checkbox("【供應商】關鍵零組件與供應鏈穩定，不被單一廠商綁架", key="v4")

moat_passed = moat_chk1 and moat_chk2 and moat_chk3
vnet_passed = vnet_chk1 and vnet_chk2 and vnet_chk3 and vnet_chk4

st.markdown("---")

if st.sidebar.button("🔍 開始綜合自動檢核"):
    with st.spinner("正在全球資料庫中抓取最新財報與 K 線歷史..."):
        try:
            df = pd.DataFrame()
            stock = None
            ticker_used = raw_ticker

            # 自動測試所有可能後綴（台股上市 .TW / 上櫃興櫃 .TWO / 原代號）
            if raw_ticker.isdigit():
                candidates = [f"{raw_ticker}.TW", f"{raw_ticker}.TWO"]
            else:
                candidates = [raw_ticker]

            for t in candidates:
                test_stock = yf.Ticker(t)
                test_df = test_stock.history(period="2y")
                if test_df is not None and not test_df.empty:
                    df = test_df
                    stock = test_stock
                    ticker_used = t
                    break

            if df.empty or len(df) < 10:
                st.error(f"❌ 查無代號 {raw_ticker} 或 K 線資料不足，請確認代號是否正確！")
            else:
                mkt_symbol = market_ticker.split(" ")[0]
                mkt_df = yf.Ticker(mkt_symbol).history(period="1y")
                
                is_etf = raw_ticker.startswith("00") or "ETF" in raw_ticker

                # --- 全域財報通用解析引擎 ---
                chk1 = False
                eps_growth = 0.0
                rev_growth = 0.0
                gross_margin = 0.0
                financial_status = "❌ 未達標"
                financial_summary = {}

                if is_startup:
                    chk1 = True
                    financial_status = "🌱 新創豁免"
                elif is_etf:
                    chk1 = True
                    financial_status = "ℹ️ ETF 商品"
                else:
                    # 1. 嘗試抓取季度損益表
                    q_fin = stock.quarterly_income_stmt
                    if q_fin is None or q_fin.empty:
                        q_fin = stock.quarterly_financials

                    # 定義全域相容會計科目清單
                    rev_aliases = ['Total Revenue', 'Operating Revenue', 'OperatingRevenue', 'Gross Revenue', 'Revenue']
                    net_aliases = ['Net Income', 'Net Income Common Stockholders', 'NetIncome', 'Net Income From Continuing Operation Net Minority Interest']
                    gp_aliases = ['Gross Profit', 'GrossProfit']

                    rev_row = None
                    net_row = None
                    gp_row = None

                    if q_fin is not None and not q_fin.empty and len(q_fin.columns) >= 2:
                        for alias in rev_aliases:
                            if alias in q_fin.index:
                                rev_row = alias
                                break
                        for alias in net_aliases:
                            if alias in q_fin.index:
                                net_row = alias
                                break
                        for alias in gp_aliases:
                            if alias in q_fin.index:
                                gp_row = alias
                                break

                    if rev_row and net_row:
                        try:
                            rev_curr = float(q_fin.loc[rev_row].iloc[0])
                            rev_prev = float(q_fin.loc[rev_row].iloc[1])
                            net_curr = float(q_fin.loc[net_row].iloc[0])
                            net_prev = float(q_fin.loc[net_row].iloc[1])

                            if rev_prev != 0:
                                rev_growth = ((rev_curr - rev_prev) / abs(rev_prev)) * 100
                            if net_prev != 0:
                                eps_growth = ((net_curr - net_prev) / abs(net_prev)) * 100

                            if gp_row and rev_curr != 0:
                                gross_margin = (float(q_fin.loc[gp_row].iloc[0]) / rev_curr) * 100

                            financial_summary = {
                                "最新季營收": f"{rev_curr:,.0f}",
                                "上一季營收": f"{rev_prev:,.0f}",
                                "營收季增率 (QoQ)": f"{rev_growth:+.2f}%",
                                "最新季淨利": f"{net_curr:,.0f}",
                                "上一季淨利": f"{net_prev:,.0f}",
                                "淨利/EPS 季增率 (QoQ)": f"{eps_growth:+.2f}%",
                                "最新季毛利率": f"{gross_margin:.2f}%" if gp_row else "依年報計算"
                            }

                            if eps_growth > 20 and rev_growth > 15:
                                chk1 = True
                                financial_status = "✅ 通過"
                            else:
                                financial_status = "❌ 未達標"
                        except Exception:
                            pass

                    # 若季度表解析缺漏，自動切換至全域 Info 即時資料庫
                    if not financial_summary:
                        try:
                            info = stock.info
                            if info and ('revenueGrowth' in info or 'earningsGrowth' in info):
                                rev_growth = (info.get('revenueGrowth', 0) or 0) * 100
                                eps_growth = (info.get('earningsGrowth', 0) or 0) * 100
                                gross_margin = (info.get('grossMargins', 0) or 0) * 100
                                
                                financial_summary = {
                                    "營收成長率 (YoY)": f"{rev_growth:+.2f}%",
                                    "盈餘成長率 (YoY)": f"{eps_growth:+.2f}%",
                                    "最新毛利率": f"{gross_margin:.2f}%",
                                    "本益比 (PE)": f"{info.get('trailingPE', 'N/A')}",
                                    "每股淨值 (BVPS)": f"{info.get('bookValue', 'N/A')}"
                                }

                                if eps_growth > 20 and rev_growth > 15:
                                    chk1 = True
                                    financial_status = "✅ 通過"
                                else:
                                    financial_status = "❌ 未達標"
                        except Exception:
                            financial_status = "⚠️ 財報暫未揭露"

                # --- 指標 2：大盤趨勢 ---
                chk2 = False
                if len(mkt_df) >= 50:
                    mkt_sma50 = mkt_df['Close'].rolling(50).mean().iloc[-1]
                    chk2 = mkt_df['Close'].iloc[-1] > mkt_sma50

                # --- 指標 3：均線多頭排列 ---
                df['SMA50'] = df['Close'].rolling(50).mean()
                df['SMA150'] = df['Close'].rolling(150).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()
                
                curr_price = df['Close'].iloc[-1]
                sma50 = df['SMA50'].iloc[-1]
                
                if len(df) >= 200 and not np.isnan(df['SMA200'].iloc[-1]):
                    sma150 = df['SMA150'].iloc[-1]
                    sma200 = df['SMA200'].iloc[-1]
                    chk3 = (curr_price > sma50 > sma150 > sma200)
                elif len(df) >= 150 and not np.isnan(df['SMA150'].iloc[-1]):
                    sma150 = df['SMA150'].iloc[-1]
                    chk3 = (curr_price > sma50 > sma150)
                else:
                    chk3 = (curr_price > sma50)

                # --- 指標 4：VCP 型態 ---
                chk4 = False
                if len(df) >= 20:
                    vol_recent = df['Volume'].iloc[-5:].mean()
                    vol_prior = df['Volume'].iloc[-20:-5].mean()
                    range_recent = (df['High'].iloc[-5:] - df['Low'].iloc[-5:]).mean()
                    range_prior = (df['High'].iloc[-20:-5] - df['Low'].iloc[-20:-5]).mean()
                    chk4 = (vol_recent < vol_prior) and (range_recent < range_prior)

                # --- 綜合診斷看板 ---
                st.subheader(f"📊 {raw_ticker} ({ticker_used}) 綜合診斷看板")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("財報 (過去)", financial_status, f"EPS {eps_growth:+.1f}% / 營收 {rev_growth:+.1f}%" if financial_summary else "標準: EPS>20% 營收>15%")
                m2.metric("護城河 (現在)", "✅ 具備" if moat_passed else "⚠️ 未勾全", "特許技術/定價權/轉嫁力")
                m3.metric("價值網 (未來)", "✅ 爆發" if vnet_passed else "⚠️ 需觀察", "政策需求/生態系/供應鏈")
                m4.metric("技術面 (SEPA)", "✅ 多頭VCP" if (chk2 and chk3 and chk4) else "❌ 未達標", "大盤/均線多頭/VCP量縮")

                # 自動展示完整財報明細表
                if financial_summary:
                    with st.expander("📑 查看系統自動抓取的詳細財報數據明細", expanded=True):
                        st.table(pd.DataFrame(list(financial_summary.items()), columns=["財務會計指標", "數據數值"]))

                all_passed = chk1 and chk2 and chk3 and chk4 and moat_passed and vnet_passed

                if all_passed:
                    st.success("🎉 所有條件（財報/護城河/價值網/SEPA風控）全數通過，具備極強進場爆發潛力！")
                    
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
                    st.error("⛔ 交易否決：未完全符合檢核標準，請耐心等待基本面確認或技術面築底！")

        except Exception as e:
            st.error(f"資料抓取失敗或數據不足：{e}")
