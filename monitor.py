import yfinance as yf
from datetime import datetime, timezone, timedelta
import time

# ====================== 时间工具函数 ======================
def get_beijing_time():
    """获取北京时间 (UTC+8)"""
    return datetime.now(timezone(timedelta(hours=8)))

def get_us_eastern_time():
    """获取美国东部时间 (UTC-5，冬令时；UTC-4，夏令时)"""
    # 简单处理：3月第二个周日到11月第一个周日是夏令时(UTC-4)
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year
    # 夏令时判断（简化版）
    dst_start = datetime(year, 3, 8, 2, tzinfo=timezone.utc)
    dst_end = datetime(year, 11, 1, 2, tzinfo=timezone.utc)
    is_dst = dst_start <= now_utc < dst_end
    offset = -4 if is_dst else -5
    return now_utc.astimezone(timezone(timedelta(hours=offset)))

def format_timestamp(data_timestamp):
    """格式化数据时间戳，显示北京时间+美国时间"""
    if data_timestamp is None:
        return "时间未知"
    
    # 数据时间戳通常是 UTC
    if data_timestamp.tzinfo is None:
        data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)
    
    beijing = data_timestamp.astimezone(timezone(timedelta(hours=8)))
    eastern = data_timestamp.astimezone(timezone(timedelta(hours=-5)))
    
    return f"北京: {beijing.strftime('%m-%d %H:%M')} | 纽约: {eastern.strftime('%m-%d %H:%M')}"

# ====================== 商品配置 ======================
COMMODITIES = [
    {"code": "HG=F", "name": "CME高等级铜期货", "icon": "📊", "unit": "美元/磅"},
    {"code": "CL=F", "name": "NYMEX WTI原油期货", "icon": "🛢️", "unit": "美元/桶"},
    {"code": "BZ=F", "name": "ICE布伦特原油期货", "icon": "🛢️", "unit": "美元/桶"},
    {"code": "GC=F", "name": "COMEX黄金期货", "icon": "🥇", "unit": "美元/盎司"},
    {"code": "DX-Y.NYB", "name": "美元指数", "icon": "💵", "unit": "", "fallback": "DX=F"},  # 主代码+备选
    {"code": "^TNX", "name": "美国10年期国债收益率", "icon": "📈", "unit": "%"},
]

# ====================== 数据获取函数 ======================
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

def get_market_data(item, period="1mo"):
    """获取市场数据，支持备选代码"""
    ticker = item["code"]
    fallback = item.get("fallback")
    
    # 尝试主代码
    hist, error = fetch_with_retry(ticker, period)
    
    # 如果失败且有备选，尝试备选
    if hist is None and fallback:
        print(f"   ℹ️ 尝试备选代码: {fallback}")
        hist, error = fetch_with_retry(fallback, period)
        if hist is not None:
            print(f"   ✅ 使用备选代码 {fallback} 获取成功")
    
    if error or hist is None:
        return None, error or "无数据返回"
    
    try:
        close = hist["Close"]
        price = close.iloc[-1]
        change_pct = (price / close.iloc[-2] - 1) * 100
        
        week_change = (price / close.iloc[-5] - 1) * 100 if len(hist) >= 5 else 0
        month_change = (price / close.iloc[-20] - 1) * 100 if len(hist) >= 20 else 0
        volatility = close.pct_change().std() * (252 ** 0.5) * 100 if len(hist) >= 20 else 0
        
        # 处理收益率特殊显示（^TNX 是收益率点数）
        if ticker == "^TNX" or fallback == "^TNX":
            display_price = round(price, 2)
        else:
            display_price = round(price, 4)
        
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
        }, None
    except Exception as e:
        return None, f"解析失败: {str(e)[:50]}"

def get_item(results, code):
    """从结果列表中查找指定代码的数据"""
    return next((r for r in results if r["code"] == code), None)

# ====================== 分析函数 ======================
def analyze_correlation(results):
    """分析跨品种相关性"""
    oil_wti = get_item(results, "CL=F")
    oil_brent = get_item(results, "BZ=F")
    gold = get_item(results, "GC=F")
    dxy = get_item(results, "DX-Y.NYB")
    if dxy is None:
        dxy = get_item(results, "DX=F")
    copper = get_item(results, "HG=F")
    
    correlations = []
    
    if oil_wti and oil_brent:
        spread = abs(oil_wti["price_raw"] - oil_brent["price_raw"])
        premium = "溢价" if oil_wti["price_raw"] > oil_brent["price_raw"] else "折价"
        correlations.append(f"   🛢️ WTI-布伦特价差: ${spread:.2f}/桶 (WTI{premium})")
    
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
    dxy = get_item(results, "DX-Y.NYB")
    if dxy is None:
        dxy = get_item(results, "DX=F")
    tnx = get_item(results, "^TNX")
    
    insights = []
    
    if oil_wti and abs(oil_wti["change_pct"]) >= 3:
        direction = "暴涨" if oil_wti["change_pct"] > 0 else "暴跌"
        insights.append(f"\n🛢️ 【原油{direction}】")
        insights.append(f"   • 日涨跌: {oil_wti['change_pct']:+}%  |  周涨跌: {oil_wti['week_change']:+}%  |  月涨跌: {oil_wti['month_change']:+}%")
        if oil_wti["high_20d"] > 0:
            position = "接近" if oil_wti["price_raw"] > oil_wti["high_20d"] * 0.95 else "远离"
            insights.append(f"   • 价格位置: {position}20日高点 ${oil_wti['high_20d']:.2f}")
    
    if gold and abs(gold["change_pct"]) >= 1:
        insights.append(f"\n🥇 【黄金波动】")
        insights.append(f"   • 日涨跌: {gold['change_pct']:+}%  |  周涨跌: {gold['week_change']:+}%  |  月涨跌: {gold['month_change']:+}%")
        if gold["change_pct"] < -1:
            insights.append("   • 异常现象: 地缘危机中黄金反而下跌")
    
    if copper and abs(copper["change_pct"]) >= 1:
        insights.append(f"\n📊 【铜价波动】")
        insights.append(f"   • 日涨跌: {copper['change_pct']:+}%")
        if copper["change_pct"] < 0 and oil_wti and oil_wti["change_pct"] > 3:
            insights.append("   • 市场信号: 铜油背离 - 经济衰退预期升温")
    
    if dxy:
        insights.append(f"\n💵 【美元指数】")
        insights.append(f"   • 当前水平: {dxy['price']:.2f}  |  涨跌: {dxy['change_pct']:+}%")
        position = "100关口下方，相对弱势区间" if dxy["price_raw"] < 100 else "100关口上方，相对强势区间"
        insights.append(f"   • 技术位置: {position}")
    
    if tnx:
        insights.append(f"\n📈 【美债收益率】")
        insights.append(f"   • 10年期收益率: {tnx['price']}{tnx['unit']}")
        if abs(tnx["change_pct"]) >= 5:
            direction = "飙升" if tnx["change_pct"] > 0 else "骤降"
            insights.append(f"   • 异动提醒: 收益率{direction} {abs(tnx['change_pct']):.1f}%")
    
    return insights

# ====================== 主程序 ======================
print(f"===== 大宗商品实时监控 =====")
print(f"⏰ 北京时间: {get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"🗽 美国东部时间: {get_us_eastern_time().strftime('%Y-%m-%d %H:%M:%S')}")
print()

results = []
failed_items = []

for item in COMMODITIES:
    print(f"{item['icon']} {item['name']} ({item['code']})")
    data, error = get_market_data(item)
    
    if data:
        icon = "🟢🔺" if data["change"] > 0 else ("🔴🔻" if data["change"] < 0 else "⚪➖")
        unit = item["unit"]
        print(f"   💰 当前价: {data['price']} {unit}")
        print(f"   {icon[0]} 日涨跌: {icon[1]} {data['change']:+} ({data['change_pct']:+}%)")
        print(f"   📅 周涨跌: {data['week_change']:+}%  |  月涨跌: {data['month_change']:+}%")
        if data["volatility"] > 0:
            print(f"   📊 波动率: {data['volatility']:.1f}%  |  20日区间: {data['low_20d']}-{data['high_20d']}")
        print(f"   🕐 {format_timestamp(data['timestamp'])}")
        results.append({"code": item["code"], "name": item["name"], "icon": item["icon"], **data})
    else:
        print(f"   ❌ {error}")
        failed_items.append(item["name"])
    print()

# ====================== 深度分析 ======================
if results:
    print("=" * 60)
    print("📊 深度波动分析")
    print("=" * 60)
    
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
