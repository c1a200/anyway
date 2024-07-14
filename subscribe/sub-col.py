# -*- coding: utf-8 -*-

import os
import re
import subprocess
import sys
import time
import random
import yaml
import base64
import json
import requests
from datetime import datetime

import utils
import clash
from logger import logger
from workflow import TaskConfig
import executable

PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_BASE = os.path.join(PATH, "data")
SUBSCRIBES_FILE = os.path.join(DATA_BASE, "subscribes.txt")

def fetch_gist_content(gist_url, headers):
    response = requests.get(gist_url, headers=headers)
    response.raise_for_status()
    return response.json()

def update_gist_content(gist_url, headers, files_update):
    response = requests.patch(gist_url, headers=headers, json={"files": files_update})
    response.raise_for_status()
    return response.json()

def clash_to_v2ray(clash_config):
    proxies = clash_config.get('proxies', [])
    v2ray_nodes = []
    for proxy in proxies:
        v2ray_node = {
            "v": "2",
            "ps": proxy.get("name", ""),
            "add": proxy.get("server", ""),
            "port": str(proxy.get("port", "")),
            "id": proxy.get("uuid", ""),
            "aid": str(proxy.get("alterId", "0")),
            "net": proxy.get("network", "tcp"),
            "type": "none",
            "host": proxy.get("host", ""),
            "path": proxy.get("path", ""),
            "tls": "tls" if proxy.get("tls", False) else ""
        }
        v2ray_nodes.append("vmess://" + base64.urlsafe_b64encode(json.dumps(v2ray_node).encode()).decode())
    return v2ray_nodes

def load_subscriptions(username: str, gist_id: str, access_token: str, filename: str) -> list[str]:
    if not filename:
        return []

    subscriptions = set()

    pattern = r"^https?:\/\/[^\s]+"
    local_file = os.path.join(DATA_BASE, filename)
    if os.path.exists(local_file) and os.path.isfile(local_file):
        with open(local_file, "r", encoding="utf8") as f:
            items = re.findall(pattern, str(f.read()), flags=re.M)
            if items:
                subscriptions.update(items)

    if username and gist_id and access_token:
        gist_url = f'https://api.github.com/gists/{gist_id}'
        headers = {
            'Authorization': f'token {access_token}'
        }
        gist_content = fetch_gist_content(gist_url, headers)
        if filename in gist_content['files']:
            content = gist_content['files'][filename]['content']
            items = re.findall(pattern, content, flags=re.M)
            if items:
                subscriptions.update(items)

    return list(subscriptions)

def filter_fastest_proxies(proxies: list, max_count: int = 100) -> list:
    clash_bin, _ = executable.which_bin()
    workspace = os.path.join(PATH, "clash")
    binpath = os.path.join(workspace, clash_bin)
    filename = "config.yaml"
    
    proxies = clash.generate_config(workspace, proxies, filename)

    utils.chmod(binpath)

    logger.info(f"startup clash now, workspace: {workspace}, config: {filename}")
    process = subprocess.Popen(
        [
            binpath,
            "-d",
            workspace,
            "-f",
            os.path.join(workspace, filename),
        ]
    )
    logger.info(f"clash start success, begin check proxies, num: {len(proxies)}")

    time.sleep(random.randint(3, 6))
    params = [
        [p, clash.EXTERNAL_CONTROLLER, 5000, "https://www.google.com/generate_204", 5000, False]
        for p in proxies
        if isinstance(p, dict)
    ]

    masks = utils.multi_thread_run(
        func=clash.check,
        tasks=params,
        num_threads=64,
        show_progress=True,
    )

    try:
        process.terminate()
    except:
        logger.error(f"terminate clash process error")

    nodes = [proxies[i] for i in range(len(proxies)) if masks[i]]
    if len(nodes) > max_count:
        nodes = sorted(nodes, key=lambda x: x.get('delay', float('inf')))[:max_count]

    return nodes

def main():
    gist_pat = os.getenv("GIST_PAT")
    gist_username = os.getenv("GIST_USERNAME")
    gist_id = os.getenv("GIST_ID")
    v2ray_gist_link = os.getenv("V2RAY_GIST_LINK")

    if not gist_pat or not gist_username or not gist_id or not v2ray_gist_link:
        print("Error: Environment variables GIST_PAT, GIST_USERNAME, GIST_ID and V2RAY_GIST_LINK must be set", file=sys.stderr)
        sys.exit(1)

    subscriptions = load_subscriptions(gist_username, gist_id, gist_pat, SUBSCRIBES_FILE)
    if not subscriptions:
        print("No valid subscriptions found.", file=sys.stderr)
        sys.exit(1)

    proxies = []
    for sub in subscriptions:
        content = utils.http_get(sub)
        nodes = clash.parse_proxies(content)
        proxies.extend(nodes)

    if not proxies:
        print("No valid proxies found.", file=sys.stderr)
        sys.exit(1)

    fastest_proxies = filter_fastest_proxies(proxies, max_count=100)

    data = {"proxies": fastest_proxies}
    output_file = os.path.join(DATA_BASE, "fastest_proxies.yaml")
    with open(output_file, "w+", encoding="utf8") as f:
        yaml.dump(data, f, allow_unicode=True)

    print(f"Found {len(fastest_proxies)} fastest proxies, saved to {output_file}")

    # 上传到 V2RAY_GIST_LINK
    try:
        gist_id = v2ray_gist_link.split('/')[-1]
        gist_url = f'https://api.github.com/gists/{gist_id}'
        headers = {
            'Authorization': f'token {gist_pat}'
        }

        with open(output_file, "r", encoding="utf8") as f:
            clash_config_content = f.read()

        clash_config = yaml.safe_load(clash_config_content)
        v2ray_nodes = clash_to_v2ray(clash_config)

        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        update_v2ray_node = {
            "v": "2",
            "ps": f"Update Date: {current_date}",
            "add": "127.0.0.1",
            "port": "0",
            "id": "00000000-0000-0000-0000-000000000000",
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": ""
        }
        v2ray_nodes.insert(0, "vmess://" + base64.urlsafe_b64encode(json.dumps(update_v2ray_node).encode()).decode())

        combined_v2ray_content = "\n".join(v2ray_nodes)

        files_update = {
            'v2ray.txt': {
                'content': combined_v2ray_content
            }
        }
        update_gist_content(gist_url, headers, files_update)
        print("Successfully updated the Gist with new V2ray content.")
    except Exception as e:
        print(f"Error converting Clash config or updating Gist: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
