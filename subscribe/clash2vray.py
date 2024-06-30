import requests
import yaml
import base64
import json
import os
import sys


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
        print(f"Adding V2ray node: {v2ray_node}")  # 调试信息
        v2ray_nodes.append("vmess://" + base64.urlsafe_b64encode(json.dumps(v2ray_node).encode()).decode())
    return v2ray_nodes


def main():
    gist_pat = os.getenv("GIST_PAT")
    gist_link = os.getenv("GIST_LINK")

    if not gist_pat or not gist_link:
        print("Error: Environment variables GIST_PAT and GIST_LINK must be set", file=sys.stderr)
        sys.exit(1)

    headers = {
        'Authorization': f'token {gist_pat}'
    }
    gist_id = gist_link.split('/')[-1]
    gist_url = f'https://api.github.com/gists/{gist_id}'

    # 获取 Gist 内容并读取 clash.yaml 文件
    try:
        gist_content = fetch_gist_content(gist_url, headers)
        print("Fetched Gist Content:", gist_content)  # 调试信息
        if 'clash.yaml' not in gist_content['files']:
            print("Error: clash.yaml not found in the Gist", file=sys.stderr)
            sys.exit(1)
        clash_config_content = gist_content['files']['clash.yaml']['content']
        print("Clash Config Content:", clash_config_content)  # 调试信息
        clash_config = yaml.safe_load(clash_config_content)
    except Exception as e:
        print(f"Error fetching or parsing clash.yaml: {e}", file=sys.stderr)
        sys.exit(1)

    # 将 Clash 转换为 V2Ray 并组合节点
    try:
        v2ray_nodes = clash_to_v2ray(clash_config)
        combined_v2ray_content = "\n".join(v2ray_nodes)
        print("Combined V2ray Content:", combined_v2ray_content)  # 调试信息

        # 更新 Gist 中的 v2ray.txt 文件
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
