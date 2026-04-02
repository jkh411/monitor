import yfinance as yf
from datetime import datetime
import time

COMMODITIES = [
    {"code": "HG=F", "name": "CME高等级铜期货", "icon": "📊", "unit": "美元/磅"},
    {"code": "CL=F", "name": "NYMEX WTI原油期货", "icon": "🛢️", "unit": "美元/桶"},
    {"code": "BZ=F", "name": "ICE布伦特原油期货", "icon": "🛢️", "unit": "美元/桶"},
    {"code": "GC=F", "name": "COMEX黄金期货", "icon": "🥇", "unit": "美元/盎司"},
    {"code": "DX=F", "name": "美元指数", "icon": "💵", "unit": ""},  # 修正：用 DX=F 替代 DX-Y.NYB
    {"code": "^TNX", "name": "美国10年期国债收益率", "icon": "📈", "unit": "%"},
]

def fetch_with_retry(ticker, period="1mo", retries=3, delay=2):
    """带重试机制的数据获取"""
    for i in range(retries):
        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period=period)
            if not hist.empty and len(hist) >= 2:
                return hist, None
            else:
                print(f"   ⚠️ {ticker}: 数据为空，第{i+1}次重试...")
        except Exception as e:
            print(f"   ⚠️ {ticker}: 请求失败 ({str(e)[:50]})，第{i+1}次重试...")
        
        if i < retries - 1:
            time.sleep(delay)
    
    return None, f"获取失败，已重试{retries}次"

def get_market_data(ticker, period="1mo"):
    """获取市场数据，带重试机制"""
    hist, error = fetch_with_retry(ticker, period)
    
    if error or hist is None:
        return None, error or "无数据返回"
    
    try:
        close = hist["Close"]
        price = close.iloc[-1]
        change_pct = (price / close.iloc[-2] - 1) * 100
        
        # 周变化（约5个交易日）
        week_change = (price / close.iloc[-5] - 1) * 100 if len(hist) >= 5 else 0
        # 月变化（约20个交易日）
        month_change = (price / close.iloc[-20] - 1) * 100 if len(hist) >= 20 else 0
        # 年化波动率
        volatility = close.pct_change().std() * (252 ** 0.5) * 100 if len(hist) >= 20 else 0
        
        # 处理收益率特殊显示（^TNX 是收益率点数，不是价格）
        if ticker == "^TNX":
            display_price = round(price, 2)
            display_unit = "%"
        else:
            display_price = round(price, 4)
            display_unit = ""
        
        return {
            "price": display_price,
            "price_raw": round(price, 4),
            "change": round(price - close.iloc[-2], 4),
            "change_pct": round(change_pct, 2),
            "week_change": round(week_change, 2),
            "month_change": round(month_change, 2),
            "volatility": round(volatility, 2),
            "high_20d": round(hist["High"].iloc[-20:].max(), 4) if len(hist) >= 20 else 0,
            "low_20d": round(hist["Low"].iloc[-20:].min(), 4) if len(hist) >= 20 else 0,
            "timestamp": hist.index[-1],
            "unit": display_unit,
        }, None
    except Exception as e:
        return None, f"解析失败: {str(e)[:50]}"

def get_item(results, code):
    """从结果列表中查找指定代码的数据"""
    return next((r for r in results if r["code"] == code), None)

def analyze_correlation(results):
    """分析跨品种相关性"""
    oil_wti = get_item(results, "CL=F")
    oil_brent = get_item(results, "BZ=F")
    gold = get_item(results, "GC=F")
    dxy = get_item(results, "DX=F")
    copper = get_item(results, "HG=F")
    
    correlations = []
    
    # WTI-布伦特价差
    if oil_wti and oil_brent:
        spread = abs(oil_wti["price_raw"] - oil_brent["price_raw"])
        premium = "溢价" if oil_wti["price_raw"] > oil_brent["price_raw"] else "折价"
        correlations.append(f"   🛢️ WTI-布伦特价差: ${spread:.2f}/桶 (WTI{premium})")
    
    # 相关性分析
    pairs = [
        (gold, dxy, "🥇 黄金-美元", "黄金", "美元"),
        (oil_wti, dxy, "💵 原油-美元", "原油", "美元"),
        (copper, oil_wti, "📊 铜-原油", "铜", "原油"),
    ]
    
    for a, b, label, name_a, name_b in pairs:
        if a and b:
            product = a["change_pct"] * b["change_pct"]
            if "黄金" in label:
                relation = "负相关" if product < 0 else "正相关"
            elif "铜" in label:
                relation = "同向" if product > 0 else "背离"
            else:
                relation = "同向" if product > 0 else "反向"
            correlations.append(f"   {label}: {relation}走势 ({name_a}{a['change_pct']:+}% vs {name_b}{b['change_pct']:+}%)")
    
    return correlations

def generate_insights(results):
    """生成深度洞察"""
    oil_wti = get_item(results, "CL=F")
    gold = get_item(results, "GC=F")
    copper = get_item(results, "HG=F")
    dxy = get_item(results, "DX=F")
    tnx = get_item(results, "^TNX")
    
    insights = []
    
    # 原油剧烈波动
    if oil_wti and abs(oil_wti["change_pct"]) >= 3:
        direction = "暴涨" if oil_wti["change_pct"] > 0 else "暴跌"
        insights.append(f"\n🛢️ 【原油{direction}】")
        insights.append(f"   • 日涨跌: {oil_wti['change_pct']:+}%  |  周涨跌: {oil_wti['week_change']:+}%  |  月涨跌: {oil_wti['month_change']:+}%")
        if oil_wti["high_20d"] > 0:
            position = "接近" if oil_wti["price_raw"] > oil_wti["high_20d"] * 0.95 else "远离"
            insights.append(f"   • 价格位置: {position}20日高点 ${oil_wti['high_20d']:.2f}")
    
    # 黄金波动
    if gold and abs(gold["change_pct"]) >= 1:
        insights.append(f"\n🥇 【黄金波动】")
        insights.append(f"   • 日涨跌: {gold['change_pct']:+}%  |  周涨跌: {gold['week_change']:+}%  |  月涨跌: {gold['month_change']:+}%")
        if gold["change_pct"] < -1:
            insights.append("   • 异常现象: 地缘危机中黄金反而下跌")
    
    # 铜价波动与经济信号
    if copper and abs(copper["change_pct"]) >= 1:
        insights.append(f"\n📊 【铜价波动】")
        insights.append(f"   • 日涨跌: {copper['change_pct']:+}%")
        if copper["change_pct"] < 0 and oil_wti and oil_wti["change_pct"] > 3:
            insights.append("   • 市场信号: 铜油背离 - 经济衰退预期升温")
    
    # 美元指数
    if dxy:
        insights.append(f"\n💵 【美元指数】")
        insights.append(f"   • 当前水平: {dxy['price']:.2f}  |  涨跌: {dxy['change_pct']:+}%")
        position = "100关口下方，相对弱势区间" if dxy["price_raw"] < 100 else "100关口上方，相对强势区间"
        insights.append(f"   • 技术位置: {position}")
    
    # 美债收益率
    if tnx:
        insights.append(f"\n📈 【美债收益率】")
        insights.append(f"   • 10年期收益率: {tnx['price']}{tnx['unit']}")
        if abs(tnx["change_pct"]) >= 5:
            direction = "飙升" if tnx["change_pct"] > 0 else "骤降"
            insights.append(f"   • 异动提醒: 收益率{direction} {abs(tnx['change_pct']):.1f}%")
    
    return insights

# ====================== 主程序 ======================
print(f"===== 大宗商品实时监控 =====")
print(f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

results = []
failed_items = []

for item in COMMODITIES:
    print(f"{item['icon']} {item['name']} ({item['code']})")
    data, error = get_market_data(item["code"])
    
    if data:
        icon = "🟢🔺" if data["change"] > 0 else ("🔴🔻" if data["change"] < 0 else "⚪➖")
        unit = item["unit"]
        print(f"   💰 当前价: {data['price']} {unit}")
        print(f"   {icon[0]} 日涨跌: {icon[1]} {data['change']:+} ({data['change_pct']:+}%)")
        print(f"   📅 周涨跌: {data['week_change']:+}%  |  月涨跌: {data['month_change']:+}%")
        if data["volatility"] > 0:
            print(f"   📊 波动率: {data['volatility']:.1f}%  |  20日区间: {data['low_20d']}-{data['high_20d']}")
        print(f"   🕐 时间: {data['timestamp'].strftime('%m-%d %H:%M')}")
        results.append({"code": item["code"], "name": item["name"], "icon": item["icon"], **data})
    else:
        print(f"   ❌ {error}")
        failed_items.append(item["name"])
    print()

# ====================== 深度波动分析 ======================
if results:
    print("=" * 50)
    print("📊 深度波动分析")
    print("=" * 50)
    
    big_movers = sorted([r for r in results if abs(r["change_pct"]) >= 1], 
                        key=lambda x: abs(x["change_pct"]), reverse=True)
    if big_movers:
        print("\n⚠️ 显著波动品种 (|涨跌幅| ≥ 1%):")
        for r in big_movers:
            direction = "上涨" if r["change_pct"] > 0 else "下跌"
            print(f"   {r['icon']} {r['name']}: {direction} {abs(r['change_pct']):.1f}%")
    
    print("\n🔗 跨品种相关性分析:")
    for c in analyze_correlation(results):
        print(c)
    
    print("\n💡 深度洞察:")
    for i in generate_insights(results):
        print(i)
else:
    print("\n❌ 所有数据获取失败，请检查网络连接或稍后重试")

if failed_items:
    print(f"\n⚠️ 以下品种获取失败: {', '.join(failed_items)}")

print("\n✅ 分析完成")
