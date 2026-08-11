import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="萬用雙引擎印鈔機系統", page_icon="🚀", layout="wide")

st.title("🚀 萬用雙引擎印鈔機 - 自動檢核與風控系統")
st.caption("自動抓取財報季增率、均線多頭與 VCP 波動收縮，實現 1% 帳戶風險控管")

# 側邊欄設定
st.sidebar.header("⚙️ 參數設定")
ticker_input = st.sidebar.text_input("股票代號 (美股如 NVDA, 台積電 ADR 如 TSM)", value="NVDA").upper()
capital = st.sidebar.number_input("您的帳戶總資金 (NT$ 或 US$)", value=100000, step=10000)
market_ticker = st.sidebar.selectbox("對應大盤指數", ["^GSPC (標普500)", "^TWII (台股加權指數)"])

if st.sidebar.button("🔍 開始自動檢核"):
    with st.spinner("正在抓取最新財報與 K 線數據..."):
        try:
            stock = yf.Ticker(ticker_input)
            df = stock.history(period="1y")
            
            if df.empty:
                st.error("❌ 查無此股票代號，請確認後重試！")
            else:
                # 取得大盤數據
                mkt_symbol = market_ticker.split(" ")[0]
                mkt_df = yf.Ticker(mkt_symbol).history(period="6m")
                
                # --- 指標 1：基本面 (EPS & 營收季增) ---
                financials = stock.quarterly_financials
                chk1 = False
                eps_growth, rev_growth = 0, 0
                
                if not financials.empty and len(financials.columns) >= 2:
                    try:
                        rev_curr = financials.loc['Total Revenue'][0] if 'Total Revenue' in financials.index else financials.loc['Operating Revenue'][0]
                        rev_prev = financials.loc['Total Revenue'][1] if 'Total Revenue' in financials.index else financials.loc['Operating Revenue'][1]
                        rev_growth = ((rev_curr - rev_prev) / abs(rev_prev)) * 100
                        
                        net_curr = financials.loc['Net Income'][0]
                        net_prev = financials.loc['Net Income'][1]
                        eps_growth = ((net_curr - net_prev) / abs(net_prev)) * 100
                        
                        if eps_growth > 20 and rev_growth > 15:
                            chk1 = True
                    except Exception:
                        pass

                # --- 指標 2：大盤趨勢 ---
                mkt_sma50 = mkt_df['Close'].rolling(50).mean().iloc[-1]
                chk2 = mkt_df['Close'].iloc[-1] > mkt_sma50

                # --- 指標 3：均線多頭排列 ---
                df['SMA50'] = df['Close'].rolling(50).mean()
                df['SMA150'] = df['Close'].rolling(150).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()
                
                curr_price = df['Close'].iloc[-1]
                sma50 = df['SMA50'].iloc[-1]
                sma150 = df['SMA150'].iloc[-1]
                sma200 = df['SMA200'].iloc[-1]
                
                chk3 = (curr_price > sma50 > sma150 > sma200)

                # --- 指標 4：VCP 型態 (波動與成交量收縮) ---
                vol_recent = df['Volume'].iloc[-5:].mean()
                vol_prior = df['Volume'].iloc[-20:-5].mean()
                range_recent = (df['High'].iloc[-5:] - df['Low'].iloc[-5:]).mean()
                range_prior = (df['High'].iloc[-20:-5] - df['Low'].iloc[-20:-5]).mean()
                
                chk4 = (vol_recent < vol_prior) and (range_recent < range_prior)

                # --- 呈現四項指標結果 ---
                st.subheader(f"📊 {ticker_input} SEPA 自動檢核結果")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("1. 財報季增長", "✅ 通過" if chk1 else "❌ 未達標", f"EPS +{eps_growth:.1f}% / 營收 +{rev_growth:.1f}%")
                c2.metric("2. 大盤上升趨勢", "✅ 通過" if chk2 else "❌ 修正期", "指數 > 50MA")
                c3.metric("3. 均線多頭排列", "✅ 通過" if chk3 else "❌ 非多頭", "現價 > 50 > 150 > 200MA")
                c4.metric("4. VCP 波動收縮", "✅ 通過" if chk4 else "❌ 未收縮", "量縮且波幅窄")

                all_passed = chk1 and chk2 and chk3 and chk4

                if all_passed:
                    st.success("🎉 完美！所有條件均符合 SEPA / VCP 強勢進場型態！")
                    
                    # 風控計算
                    stop_price = df['Low'].iloc[-10:].min() # 以近10日低點作為硬停損點
                    risk_per_share = curr_price - stop_price
                    risk_pct = (risk_per_share / curr_price) * 100
                    
                    max_risk_amount = capital * 0.01
                    shares_to_buy = int(max_risk_amount // risk_per_share) if risk_per_share > 0 else 0
                    exposure = shares_to_buy * curr_price
                    
                    st.markdown("---")
                    st.subheader("🦅 1% 風險控管建議買入部位")
                    st.write(f"- 當前突破買入價：**${curr_price:.2f}**")
                    st.write(f"- 自動建議硬停損價：**${stop_price:.2f}** (停損距離: {risk_pct:.1f}%)")
                    
                    if risk_pct > 8.0:
                        st.warning("⚠️ 警告：目前停損距離超過 8%，代表波動收縮不夠緊密，建議等待價格重新整理！")
                    
                    st.markdown(f"👉 **建議買入數量：:red[{shares_to_buy:,} 股]**")
                    st.write(f"- 單筆最大承擔虧損 (1%)：**${max_risk_amount:,.2f}**")
                    st.write(f"- 動用總資金 (名目曝險)：**${exposure:,.2f}** (佔帳戶 {(exposure/capital)*100:.1f}%)")
                else:
                    st.error("⛔ 交易否決：未完全符合雙重檢核標準，請勿盲目進場！")

        except Exception as e:
            st.error(f"資料抓取失敗或數據不足：{e}")