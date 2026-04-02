import yfinance as yf
from datetime import datetime

COMMODITIES = [
    {"code": "HG=F", "name": "CME高等级铜期货", "icon": "📊", "unit": "美元/磅"},
    {"code": "CL=F", "name": "NYMEX WTI原油期货", "icon": "🛢️", "unit": "美元/桶"},
    {"code": "BZ=F", "name": "ICE布伦特原油期货", "icon": "🛢️", "unit": "美元/桶"},
    {"code": "GC=F", "name": "COMEX黄金期货", "icon": "🥇", "unit": "美元/盎司"},
    {"code": "DX-Y.NYB", "name": "美元指数", "icon": "💵", "unit": ""},
    {"code": "^TNX", "name": "美国10年期国债收益率", "icon": "📈", "unit": "%"},
]

def get_market_data(ticker, period="1mo"):
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if len(hist) < 2:
            return None, "数据不足"
        
        close = hist["Close"]
        price = close.iloc[-1]
        change_pct = (price / close.iloc[-2] - 1) * 100
        
        week_change = (price / close.iloc[-5] - 1) * 100 if len(hist) >= 5 else 0
        month_change = (price / close.iloc[-20] - 1) * 100 if len(hist) >= 20 else 0
        volatility = close.pct_change().std() * (252 ** 0.5) * 100 if len(hist) >= 20 else 0
        
        return {
            "price": round(price, 4),
            "change": round(price - close.iloc[-2], 4),
            "change_pct": round(change_pct, 2),
            "week_change": round(week_change, 2),
            "month_change": round(month_change, 2),
            "volatility": round(volatility, 2),
            "high_20d": round(hist["High"].iloc[-20:].max(), 4) if len(hist) >= 20 else 0,
            "low_20d": round(hist["Low"].iloc[-20:].min(), 4) if len(hist) >= 20 else 0,
            "timestamp": hist.index[-1],
        }, None
    except Exception as e:
        return None, f"获取失败: {e}"

def get_item(results, code):
    return next((r for r in results if r["code"] == code), None)

def analyze_correlation(results):
    oil_wti, oil_brent = get_item(results, "CL=F"), get_item(results, "BZ=F")
    gold, dxy = get_item(results, "GC=F"), get_item(results, "DX-Y.NYB")
    copper = get_item(results, "HG=F")
    
    correlations = []
    if oil_wti and oil_brent:
        spread = abs(oil_wti["price"] - oil_brent["price"])
        correlations.append(f"   🛢️ WTI-布伦特价差: ${spread:.2f}/桶 (WTI{'溢价' if oil_wti['price'] > oil_brent['price'] else '折价'})")
    
    pairs = [
        (gold, dxy, "🥇 黄金-美元", "黄金", "美元"),
        (oil_wti, dxy, "💵 原油-美元", "原油", "美元"),
        (copper, oil_wti, "📊 铜-原油", "铜", "原油"),
    ]
    for a, b, label, name_a, name_b in pairs:
        if a and b:
            relation = "负相关" if a["change_pct"] * b["change_pct"] < 0 else ("正相关" if "黄金" in label else "同向")
            if "铜" in label:
                relation = "同向" if a["change_pct"] * b["change_pct"] > 0 else "背离"
            correlations.append(f"   {label}: {relation}走势 ({name_a}{a['change_pct']:+}% vs {name_b}{b['change_pct']:+}%)")
    
    return correlations

def generate_insights(results):
    oil_wti = get_item(results, "CL=F")
    gold = get_item(results, "GC=F")
    copper = get_item(results, "HG=F")
    dxy = get_item(results, "DX-Y.NYB")
    
    insights = []
    
    if oil_wti and abs(oil_wti["change_pct"]) >= 5:
        direction = "暴涨" if oil_wti["change_pct"] > 0 else "暴跌"
        insights.append(f"\n🛢️ 【原油{direction}】")
        insights.append(f"   • 日涨跌: {oil_wti['change_pct']:+}%  |  周涨跌: {oil_wti['week_change']:+}%  |  月涨跌: {oil_wti['month_change']:+}%")
        if oil_wti["high_20d"] > 0:
            position = "接近" if oil_wti["price"] > oil_wti["high_20d"] * 0.95 else "远离"
            insights.append(f"   • 价格位置: {position}20日高点${oil_wti['high_20d']:.2f}")
    
    if gold and abs(gold["change_pct"]) >= 1:
        insights.append(f"\n🥇 【黄金波动】")
        insights.append(f"   • 日涨跌: {gold['change_pct']:+}%  |  周涨跌: {gold['week_change']:+}%  |  月涨跌: {gold['month_change']:+}%")
        if gold["change_pct"] < -1:
            insights.append("   • 异常现象: 地缘危机中黄金反而下跌")
    
    if copper and abs(copper["change_pct"]) >= 1:
        insights.append(f"\n📊 【铜价波动】")
        insights.append(f"   • 日涨跌: {copper['change_pct']:+}%")
        if copper["change_pct"] < 0 and oil_wti and oil_wti["change_pct"] > 5:
            insights.append("   • 市场信号: 铜油背离 - 经济衰退预期升温")
    
    if dxy:
        insights.append(f"\n💵 【美元指数】")
        insights.append(f"   • 当前水平: {dxy['price']:.2f}  |  涨跌: {dxy['change_pct']:+}%")
        position = "100关口下方，相对弱势区间" if dxy["price"] < 100 else "100关口上方，相对强势区间"
        insights.append(f"   • 技术位置: {position}")
    
    return insights

# ====================== 主程序 ======================
print(f"===== 大宗商品实时监控 =====")
print(f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

results = []
for item in COMMODITIES:
    data, error = get_market_data(item["code"])
    print(f"{item['icon']} {item['name']} ({item['code']})")
    
    if data:
        icon = "🟢🔺" if data["change"] > 0 else ("🔴🔻" if data["change"] < 0 else "⚪➖")
        print(f"   💰 当前价: {data['price']} {item['unit']}")
        print(f"   {icon[0]} 日涨跌: {icon[1]} {data['change']:+} ({data['change_pct']:+}%)")
        print(f"   📅 周涨跌: {data['week_change']:+}%  |  月涨跌: {data['month_change']:+}%")
        if data["volatility"] > 0:
            print(f"   📊 波动率: {data['volatility']:.1f}%  |  20日区间: {data['low_20d']}-{data['high_20d']}")
        print(f"   🕐 时间: {data['timestamp'].strftime('%m-%d %H:%M')}")
        results.append({"code": item["code"], "name": item["name"], "icon": item["icon"], **data})
    else:
        print(f"   ❌ {error}")
    print()

# ====================== 深度波动分析 ======================
print("=" * 50)
print("📊 深度波动分析")
print("=" * 50)

big_movers = sorted([r for r in results if abs(r["change_pct"]) >= 1], key=lambda x: abs(x["change_pct"]), reverse=True)
if big_movers:
    print("\n⚠️ 显著波动品种 (|涨跌幅| ≥ 1%):")
    for r in big_movers:
        direction = "上涨" if r["change_pct"] > 0 else "下跌"
        print(f"   {r['icon']} {r['name']}: {direction} {abs(r['change_pct'])}%")

print("\n🔗 跨品种相关性分析:")
for c in analyze_correlation(results):
    print(c)

print("\n💡 深度洞察:")
for i in generate_insights(results):
    print(i)

print("\n✅ 分析完成")
