import requests
import yaml
import base64
import json
import os
import sys

# 将 Clash 配置转换为 V2ray 节点配置
def clash_to_v2ray(clash_config):
    proxies = yaml.safe_load(clash_config).get('proxies', [])
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

# 生成新的 V2ray 配置内容，并更新到 Gist
def update_gist_with_v2ray(gist_url, headers, clash_config):
    v2ray_nodes = clash_to_v2ray(clash_config)
    combined_v2ray_content = "\n".join(v2ray_nodes)

    # 获取当前 Gist 内容
    gist_response = requests.get(gist_url, headers=headers)
    gist_response.raise_for_status()
    gist_content = gist_response.json()
    files_content = gist_content.get('files', {})

    # 更新或添加 v2ray.txt 文件内容
    files_content['v2ray.txt'] = {
        "content": combined_v2ray_content
    }

    # 更新 Gist 内容
    update_response = requests.patch(gist_url, headers=headers, json={"files": files_content})
    update_response.raise_for_status()
    print("Successfully updated the Gist with new V2ray content.")

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
        gist_response = requests.get(gist_url, headers=headers)
        gist_response.raise_for_status()
        gist_content = gist_response.json()
        clash_config = gist_content['files']['clash.yaml']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Gist content: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"Error: {e} not found in the Gist content.", file=sys.stderr)
        sys.exit(1)

    # 更新 Gist with new V2ray content
    update_gist_with_v2ray(gist_url, headers, clash_config)

if __name__ == "__main__":
    main()
