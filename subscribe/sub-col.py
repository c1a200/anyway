# -*- coding: utf-8 -*-

import os
import re
import subprocess
import sys
import time
import random
import yaml

import utils
import clash
from logger import logger
from push import PushToGist
from workflow import TaskConfig
import executable

PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_BASE = os.path.join(PATH, "data")
SUBSCRIBES_FILE = os.path.join(DATA_BASE, "subscribes.txt")

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
        push_tool = PushToGist(token=access_token)
        url = push_tool.raw_url(push_conf={"username": username, "gistid": gist_id, "filename": filename})

        content = utils.http_get(url=url, timeout=30)
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
    username = os.environ.get("GIST_USERNAME", "")
    gist_id = os.environ.get("GIST_ID", "")
    access_token = os.environ.get("GIST_PAT", "")
    v2ray_gist_link = os.environ.get("V2RAY_GIST_LINK", "")
    
    if not username or not gist_id or not access_token:
        logger.error("Gist credentials are not provided.")
        sys.exit(1)

    subscriptions = load_subscriptions(username, gist_id, access_token, SUBSCRIBES_FILE)
    if not subscriptions:
        logger.error("No valid subscriptions found.")
        sys.exit(1)

    proxies = []
    for sub in subscriptions:
        content = utils.http_get(sub)
        nodes = clash.parse_proxies(content)
        proxies.extend(nodes)

    if not proxies:
        logger.error("No valid proxies found.")
        sys.exit(1)

    fastest_proxies = filter_fastest_proxies(proxies, max_count=100)

    data = {"proxies": fastest_proxies}
    output_file = os.path.join(DATA_BASE, "fastest_proxies.yaml")
    with open(output_file, "w+", encoding="utf8") as f:
        yaml.dump(data, f, allow_unicode=True)

    logger.info(f"Found {len(fastest_proxies)} fastest proxies, saved to {output_file}")

    # 上传到 V2RAY_GIST_LINK
    if v2ray_gist_link:
        gist_username, gist_id = v2ray_gist_link.split('/')
        push_tool = PushToGist(token=access_token)
        files = {
            "fastest_proxies.yaml": {"content": open(output_file, "r", encoding="utf8").read()}
        }
        success = push_tool.push_to(content="", push_conf={"username": gist_username, "gistid": gist_id, "filename": "fastest_proxies.yaml"}, payload={"files": files})
        if success:
            logger.info("Uploaded fastest proxies to V2RAY Gist successfully.")
        else:
            logger.error("Failed to upload fastest proxies to V2RAY Gist.")

if __name__ == "__main__":
    main()
