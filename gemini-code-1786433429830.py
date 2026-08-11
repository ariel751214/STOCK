import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="萬用雙引擎印鈔機系統", page_icon="🚀", layout="wide")

st.title("🚀 萬用雙引擎印鈔機 - 財女珍妮與 SEPA 全方位風控系統")
st.caption("融合『財報看過去、護城河看現在、價值網看未來』與新創彈性檢核模組")

# 側邊欄設定
st.sidebar.header("⚙️ 1. 股票與資金設定")
raw_ticker = st.sidebar.text_input("股票 / ETF 代號 (如 NVDA, 2330, 2237, 0056)", value="2237").strip().upper()

# 自動處理台股後綴 (.TW / .TWO)
if raw_ticker.isdigit():
    ticker_input = f"{raw_ticker}.TW"
else:
    ticker_input = raw_ticker

capital = st.sidebar.number_input("您的帳戶總資金 (NT$ 或 US$)", value=100000, step=10000)
market_ticker = st.sidebar.selectbox("對應大盤指數", ["^TWII (台股加權指數)", "^GSPC (標普500)"])

st.sidebar.markdown("---")
st.sidebar.header("🚩 2. 特殊公司模組設定")
is_startup = st.sidebar.checkbox("🐣 此公司為『新創 / 無歷史報表公司』", value=False, help="勾選後將免除過去 EPS 季增限制，改重護城河、價值網與 SEPA 技術面")

# 主畫面：財女珍妮定性分析表
st.subheader("🏰 財女珍妮：護城河與價值網定性檢核")
col_moat, col_vnet = st.columns(2)

with col_moat:
    st.markdown("### 1. 護城河評估（看現在）")
    moat_chk1 = st.checkbox("產品/技術具特許或示範資格，難被對手模仿取代", value=True if raw_ticker=="2237" else False)
    moat_chk2 = st.checkbox("具備『定價權』或成本轉嫁能力（毛利率穩定/升級成本能消化）")
    moat_chk3 = st.checkbox("客戶轉換成本高，或具備母公司/生態系資源疊加壁壘", value=True if raw_ticker=="2237" else False)

with col_vnet:
    st.markdown("### 2. 價值網評估（看未來）")
    vnet_chk1 = st.checkbox("【顧客】受惠政策或趨勢，目標市場需求正在爆炸性湧入", value=True if raw_ticker=="2237" else False)
    vnet_chk2 = st.checkbox("【互補者】整體產業生態系或母公司正在免費幫它放大價值", value=True if raw_ticker=="2237" else False)
    vnet_chk3 = st.checkbox("【競爭者】市場呈現寡占或技術甩開對手，不必打惡性價格戰")
    vnet_chk4 = st.checkbox("【供應商】關鍵零組件與供應鏈穩定，不被單一廠商綁架")

moat_passed = moat_chk1 and moat_chk2 and moat_chk3
vnet_passed = vnet_chk1 and vnet_chk2 and vnet_chk3 and vnet_chk4

st.markdown("---")

if st.sidebar.button("🔍 開始綜合自動檢核"):
    with st.spinner("正在抓取最新數據與 K 線..."):
        try:
            stock = yf.Ticker(ticker_input)
            df = stock.history(period="2y")
            
            # 若上市 (.TW) 抓不到，自動嘗試上櫃 (.TWO)
            if (df is None or df.empty) and raw_ticker.isdigit():
                ticker_input = f"{raw_ticker}.TWO"
                stock = yf.Ticker(ticker_input)
                df = stock.history(period="2y")

            if df is None or df.empty or len(df) < 20:
                st.error("❌ 查無此股票代號或 K 線資料不足，請確認後重試！")
            else:
                mkt_symbol = market_ticker.split(" ")[0]
                mkt_df = yf.Ticker(mkt_symbol).history(period="1y")
                
                # --- 指標 1：財報 (看過去，支援新創/ETF 彈性處理) ---
                financials = stock.quarterly_financials
                chk1 = False
                eps_growth, rev_growth, gross_margin = 0, 0, 0
                is_etf = False
                
                if not is_startup and financials is not None and not financials.empty and len(financials.columns) >= 2:
                    try:
                        rev_curr = financials.loc['Total Revenue'][0] if 'Total Revenue' in financials.index else financials.loc['Operating Revenue'][0]
                        rev_prev = financials.loc['Total Revenue'][1] if 'Total Revenue' in financials.index else financials.loc['Operating Revenue'][1]
                        rev_growth = ((rev_curr - rev_prev) / abs(rev_prev)) * 100
                        
                        net_curr = financials.loc['Net Income'][0]
                        net_prev = financials.loc['Net Income'][1]
                        eps_growth = ((net_curr - net_prev) / abs(net_prev)) * 100
                        
                        if 'Gross Profit' in financials.index:
                            gross_margin = (financials.loc['Gross Profit'][0] / rev_curr) * 100
                        
                        if eps_growth > 20 and rev_growth > 15:
                            chk1 = True
                    except Exception:
                        is_etf = True
                        chk1 = True
                else:
                    chk1 = True # 新創模式或 ETF 自動通過財報硬性限制

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
                st.subheader(f"📊 {raw_ticker} ({ticker_input}) 綜合診斷看板")
                
                m1, m2, m3, m4 = st.columns(4)
                if is_startup:
                    m1.metric("財報 (過去)", "🌱 新創模組", "豁免過去歷史報表限制")
                elif is_etf:
                    m1.metric("財報 (過去)", "ℹ️ ETF 不適用", "自動跳過個股財報")
                else:
                    m1.metric("財報 (過去)", "✅ 強勁" if chk1 else "❌ 未達標", f"毛利率: {gross_margin:.1f}%")
                
                m2.metric("護城河 (現在)", "✅ 具備" if moat_passed else "⚠️ 未勾全", "特許技術/定價權/轉嫁力")
                m3.metric("價值網 (未來)", "✅ 爆發" if vnet_passed else "⚠️ 需觀察", "政策需求/生態系/供應鏈")
                m4.metric("技術面 (SEPA)", "✅ 多頭VCP" if (chk2 and chk3 and chk4) else "❌ 未達標", "大盤/均線多頭/VCP量縮")

                all_passed = chk1 and chk2 and chk3 and chk4 and moat_passed and vnet_passed

                if all_passed:
                    st.success("🎉 所有條件（護城河/價值網/SEPA技術風控）全數通過，具備極強進場爆發潛力！")
                    
                    # 1% 風控部位計算
                    stop_price = df['Low'].iloc[-10:].min()
                    risk_per_share = curr_price - stop_price
                    risk_pct = (risk_per_share / curr_price) * 100 if curr_price > 0 else 0
                    
                    max_risk_amount = capital * 0.01
                    shares_to_buy = int(max_risk_amount // risk_per_share) if risk_per_share > 0 else 0
                    exposure = shares_to_buy * curr_price
                    
                    st.markdown("---")
                    st.subheader("🦅 1% 風險控管建議買入部位")
                    st.write(f"- 當前突破價：**NT$ {curr_price:.2f}**")
                    st.write(f"- 自動建議硬停損價：**NT$ {stop_price:.2f}** (停損距離: {risk_pct:.1f}%)")
                    
                    if risk_pct > 8.0:
                        st.warning("⚠️ 警告：目前停損距離超過 8%，代表波動收縮不夠緊密，建議等待價格重新整理！")
                    
                    st.markdown(f"👉 **建議買入數量：:red[{shares_to_buy:,} 股]**")
                    st.write(f"- 單筆最大承擔虧損 (1%)：**NT$ {max_risk_amount:,.2f}**")
                    st.write(f"- 動用總資金 (名目曝險)：**NT$ {exposure:,.2f}** (佔帳戶 {(exposure/capital)*100:.1f}%)")
                else:
                    st.error("⛔ 交易否決：未完全符合檢核標準，請耐心等待護城河/價值網確認或技術面築底！")

        except Exception as e:
            st.error(f"資料抓取失敗或數據不足：{e}")
