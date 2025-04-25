import os
import json
import requests
from datetime import datetime
import csv

# Load credentials from environment variables
ZABBIX_URL = os.getenv("ZABBIX_URL")  # e.g., "http://zabbix-server/api_jsonrpc.php"
ZABBIX_USER = os.getenv("ZABBIX_USER")
ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD")
REPO_PATH = "/dghc"  # Clone your repo here first

# Headers for Zabbix API
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('ZABBIX_API_TOKEN')}",  # Optional: if using GitHub API
    # "User-Agent": "ZabbixGitBot/1.0"
}

# Fields to redact (case-insensitive)
REDACTED_FIELDS = {
    'system name', 'system description', 'host name',
    'ip address', 'mac address', 'serial number', 'redacted'
}

# --------------------------------------
# Zabbix API Functions (Raw HTTP Calls)
# --------------------------------------

def zabbix_login():
    print("Logging in to Zabbix...")
    print(f"Zabbix URL: {ZABBIX_URL}")
    """Authenticate and return auth token"""
    payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {
            "username": f"{ZABBIX_USER}",
            "password": f"{ZABBIX_PASSWORD}"
        },
        "id": 1
    }
    try:
        response = requests.post(ZABBIX_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()  # Raise HTTP errors
        result = response.json()
        
        if "error" in result:
            print(f"Zabbix API Error: {result['error']}")
            exit(1)
            
        return result["result"]
        
    except Exception as e:
        print(f"Login failed: {str(e)}")
        print(f"Response text: {response.text if 'response' in locals() else ''}")
        exit(1)

def should_redact(metric_name):
    """Check if metric should be completely excluded"""
    metric_lower = metric_name.lower()
    return any(field in metric_lower for field in REDACTED_FIELDS)

def zabbix_get_hosts():
    """Fetch all monitored hosts"""
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host"],
            "filter": {"status": "0"}  # Only enabled hosts
        },
        "id": 2
    }
    
    response = requests.post(ZABBIX_URL, headers=headers, json=payload)
    print(f"Response get hosts: {response.text}")
    return response.json()["result"]

def zabbix_get_items(hostid):
    """Get items (metrics) for a specific host"""
    payload = {
        "jsonrpc": "2.0",
        "method": "item.get",
        "params": {
            "output": ["itemid", "name", "lastvalue", "units", "lastclock"],
            "hostids": hostid,
            "filter": {
                "state": 0,  # Only enabled items
                "status": 0
            }
        },
        "id": 3
    }
    
    response = requests.post(ZABBIX_URL, headers=headers, json=payload)
    return response.json()["result"]

def generate_readme(metrics_count):
    return f"""# Zabbix Metrics Archive

⚠️ **Note**: Sensitive fields like hostnames and system descriptions are redacted.

## Dataset Info
- Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}
- Total Metrics Collected: {metrics_count}
- Update Frequency: Every 3 hours

## Data Structure
```json
{{
    "host": "redacted",
    "metric": "CPU Usage",
    "value": "12.5",
    "units": "%",
    "timestamp": "2024-05-21T12:00:00"
}}
```
"""



# --------------------------------------
# Data Collection & Git Automation
# --------------------------------------

def main():
    try:
        print(f"Connecting to Zabbix at {ZABBIX_URL}...")
    	# Authenticate with Zabbix
        # auth_token = zabbix_login()
    
    	# Get all hosts
        hosts = zabbix_get_hosts()
    
    	# Prepare data
        # all_metrics = []
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        # Filter sensitive data
        filtered_metrics = []
        for host in hosts:
            items = zabbix_get_items(host["hostid"])
            for item in items:
                if should_redact(item["name"]):
                    item["name"] = "REDACTED"
                    item["lastvalue"] = "REDACTED"

                filtered_metrics.append({
                    "host": "[redacted]",  # Anonymize host name
                    "metric": item["name"],
                    "value": item["lastvalue"],
                    "units": item["units"],
                    "timestamp": timestamp
                })
                # all_metrics.append({
                    # "host": host["host"],
                    # "metric": item["name"],
                    # "value": item["lastvalue"],
                    # "units": item["units"],
                    # "timestamp": datetime.fromtimestamp(int(item["lastclock"])).isoformat()
                # })
        # Generate README
        readme_content = generate_readme(len(filtered_metrics))
        with open("README.md", "w") as f:
            f.write(readme_content)

        # Save as JSON
        json_file = f"data/{timestamp}.json"
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        with open(json_file, "w") as f:
            json.dump(filtered_metrics, f, indent=2)

        # Save as CSV
        csv_file = f"data/{timestamp}.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["host", "metric", "value", "units", "timestamp"])
            writer.writeheader()
            writer.writerows(filtered_metrics)

        # Git operations
        os.chdir(REPO_PATH)
        os.system("git pull --rebase origin main")  # Avoid conflicts
        os.system(f"git add {json_file} {csv_file} README.md")
        os.system(f'git commit -m "Zabbix metrics update: {timestamp}"')
        os.system("git push origin main")
    except Exception as e:
        print(f"Script failed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
