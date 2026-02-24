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
    },
    "BAMLH0A3HYC": {
        "name": "ICE BofA CCC and Lower US High Yield Index OAS",
        "baseline": 8.88,
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
        # 从最后几行开始找有效数据 (防止最新一天是 . 代表缺失)
        for line in reversed(lines):
            parts = line.split(',')
            if len(parts) == 2 and parts[1].strip() != '.':
                try:
                    date_str = parts[0].strip()
                    value = float(parts[1].strip())
                    return date_str, value
                except ValueError:
                    continue
    except Exception as e:
        print(f"[{datetime.now()}] 抓取 {series_id} 失败: {e}", file=sys.stderr)
        
    return None, None

def send_wecom_notification(message):
    """发送企业微信消息。"""
    if "PLACEHOLDER" in WECOM_WEBHOOK_URL:
        print(f"[{datetime.now()}] Webhook URL 是占位符，跳过发送消息。消息内容:\n{message}")
        return False
        
    data = {"msgtype": "markdown", "markdown": {"content": message}}
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
    alerts = []
    
    for series_id, config in SERIES_CONFIG.items():
        baseline = config["baseline"]
        name = config["name"]
        
        date_latest, current_val = fetch_latest_fred_data(series_id)
        
        if current_val is None:
            continue
            
        print(f"[{datetime.now()}] {series_id} ({date_latest}): {current_val} (Baseline: {baseline})")
        
        pct_change = ((current_val - baseline) / baseline) * 100
        
        if pct_change >= ALERT_THRESHOLD_PCT:
            alerts.append(
                f"**<font color='warning'>警报：{series_id} 涨幅超过 {ALERT_THRESHOLD_PCT}%！</font>**\n"
                f"> 指标名称：**{name}**\n"
                f"> 最新日期：{date_latest}\n"
                f"> 最新数值：**{current_val} %**\n"
                f"> 基准数值：{baseline} %\n"
                f"> 累计涨幅：<font color='comment'>{pct_change:.2f}%</font>\n"
                f"[查看原始图表](https://fred.stlouisfed.org/series/{series_id})"
            )
            
    if alerts:
        message = "### 📊 \bFRED 高收益债利差预警\n\n" + "\n---\n".join(alerts)
        send_wecom_notification(message)

if __name__ == "__main__":
    main()
