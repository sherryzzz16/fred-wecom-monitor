#!/usr/bin/env python3
import urllib.request
import json
import os
import sys
from datetime import datetime

# ================= 配置区域 Configuration =================

# 你的企业微信 Webhook URL。
# 你可以直接在这里填入 URL，或者在运行脚本前设置环境变量 WECOM_WEBHOOK_URL
WECOM_WEBHOOK_URL = os.environ.get("WECOM_WEBHOOK_URL", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=PLACEHOLDER")

# 监控指标的基线 (Baseline) 和阈值 (Threshold)
# 涨幅超过 10% 报警
ALERT_THRESHOLD_PCT = 10.0

SERIES_CONFIG = {
    "BAMLH0A0HYM2": {
        "name": "ICE BofA US High Yield Index OAS",
        "baseline": 2.88,
        "baseline_date": "2026-02-19" # 请根据实际基准日期修改
    },
    "BAMLH0A3HYC": {
        "name": "ICE BofA CCC and Lower US High Yield Index OAS",
        "baseline": 8.88,
        "baseline_date": "2026-02-19" # 请根据实际基准日期修改
    }
}

# ========================================================

def fetch_latest_fred_data(series_id):
    """从 FRED 获取指定 series_id 的最新数据。"""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    
    import subprocess
    try:
        result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, timeout=30)
        lines = result.stdout.splitlines()
        
        valid_data_points = []
        # 从最后几行开始找有效数据 (防止最新一天是 . 代表缺失)
        for line in reversed(lines):
            parts = line.split(',')
            if len(parts) == 2 and parts[1].strip() != '.':
                try:
                    date_str = parts[0].strip()
                    value = float(parts[1].strip())
                    valid_data_points.append((date_str, value))
                    if len(valid_data_points) == 2:
                        break
                except ValueError:
                    continue
                    
        if len(valid_data_points) >= 2:
            return valid_data_points[0][0], valid_data_points[0][1], valid_data_points[1][0], valid_data_points[1][1]
        elif len(valid_data_points) == 1:
            return valid_data_points[0][0], valid_data_points[0][1], None, None
            
    except Exception as e:
        print(f"[{datetime.now()}] 抓取 {series_id} 失败: {e}", file=sys.stderr)
        
    return None, None, None, None

def send_wecom_notification(message):
    """发送企业微信消息。"""
    if "PLACEHOLDER" in WECOM_WEBHOOK_URL:
        print(f"[{datetime.now()}] Webhook URL 是占位符，跳过发送消息。消息内容:\n{message}")
        return False
        
    data = {"msgtype": "text", "text": {"content": message}}
    req = urllib.request.Request(WECOM_WEBHOOK_URL, data=json.dumps(data).encode('utf-8'), method="POST")
    req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('errcode') == 0:
                print(f"[{datetime.now()}] 企业微信通知发送成功。")
                return True
            else:
                print(f"[{datetime.now()}] 发送失败: {result}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"[{datetime.now()}] 请求企业微信失败: {e}", file=sys.stderr)
        return False

def main():
    messages = []
    has_alert = False
    
    for series_id, config in SERIES_CONFIG.items():
        baseline = config["baseline"]
        baseline_date = config.get("baseline_date", "N/A")
        name = config["name"]
        
        date_latest, current_val, date_prev, prev_val = fetch_latest_fred_data(series_id)
        
        if current_val is None:
            continue
            
        print(f"[{datetime.now()}] {series_id} ({date_latest}): {current_val} (Baseline: {baseline} on {baseline_date})")
        
        pct_change = ((current_val - baseline) / baseline) * 100
        
        daily_change_str = ""
        if prev_val is not None:
            abs_change = current_val - prev_val
            daily_pct_change = (abs_change / prev_val) * 100
            daily_change_str = f"前日数值：{prev_val} % ({date_prev})\n单日变动：{abs_change:+.2f} 个百分点 ({daily_pct_change:+.2f}%)\n"
        
        if pct_change >= ALERT_THRESHOLD_PCT:
            has_alert = True
            messages.append(
                f"【警报：{series_id} 涨幅超过 {ALERT_THRESHOLD_PCT}%！】\n"
                f"指标名称：{name}\n"
                f"最新日期：{date_latest}\n"
                f"最新数值：{current_val} %\n"
                f"{daily_change_str}"
                f"基准数值：{baseline} % ({baseline_date})\n"
                f"累计涨幅：{pct_change:.2f}%\n"
                f"查看原始图表：https://fred.stlouisfed.org/series/{series_id}"
            )
        else:
            messages.append(
                f"【日常播报：{series_id}】\n"
                f"指标名称：{name}\n"
                f"最新日期：{date_latest}\n"
                f"最新数值：{current_val} %\n"
                f"{daily_change_str}"
                f"基准数值：{baseline} % ({baseline_date})\n"
                f"累计涨幅：{pct_change:.2f}%\n"
                f"查看原始图表：https://fred.stlouisfed.org/series/{series_id}"
            )
            
    if messages:
        header = "📊 FRED 高收益债利差预警\n\n" if has_alert else "📊 FRED 高收益债利差日常播报\n\n"
        final_message = header + "\n--------------------\n".join(messages)
        send_wecom_notification(final_message)

if __name__ == "__main__":
    main()
