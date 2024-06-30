import requests
import yaml
import base64
import json
import os
import sys

# 获取自定义链接
def get_custom_links(customize_link):
    try:
        response = requests.get(customize_link)
        response.raise_for_status()
        return response.text.splitlines()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching custom links: {e}", file=sys.stderr)
        return []

# 将 Clash 配置转换为 V2ray 节点配置
def clash_to_v2ray(clash_config):
    servers = yaml.safe_load(clash_config).get('proxies', [])
    v2ray_nodes = []

    for server in servers:
        v2ray_node = {
            "v": "2",
            "ps": server.get("name", ""),
            "add": server.get("server", ""),
            "port": str(server.get("port", "")),
            "id": server.get("uuid", ""),
            "aid": str(server.get("alterId", "0")),
            "net": server.get("network", "tcp"),
            "type": "none",
            "host": server.get("host", ""),
            "path": server.get("path", ""),
            "tls": "tls" if server.get("tls", False) else ""
        }
        v2ray_nodes.append(v2ray_node)

    return json.dumps(v2ray_nodes)

# 生成 base64 编码的 V2ray 订阅链接
def generate_v2ray_subscription(v2ray_config):
    base64_config = base64.urlsafe_b64encode(v2ray_config.encode()).decode()
    return f"vmess://{base64_config}"

# 主函数
def main():
    gist_pat = os.getenv("GIST_PAT")
    gist_link = os.getenv("GIST_LINK")
    customize_link = os.getenv("CUSTOMIZE_LINK")

    if not gist_pat or not gist_link:
        print("Error: Environment variables GIST_PAT and GIST_LINK must be set", file=sys.stderr)
        sys.exit(1)
    
    custom_links = get_custom_links(customize_link)
    v2ray_content = []

    for link in custom_links:
        try:
            response = requests.get(link)
            response.raise_for_status()
            clash_config = response.text
            v2ray_config = clash_to_v2ray(clash_config)
            v2ray_subscription = generate_v2ray_subscription(v2ray_config)
            v2ray_content.append(v2ray_subscription)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching clash config from link {link}: {e}", file=sys.stderr)

    if v2ray_content:
        combined_v2ray_content = "\n".join(v2ray_content)
        
        headers = {
            'Authorization': f'token {gist_pat}'
        }
        gist_id = gist_link.split('/')[-1]
        gist_url = f'https://api.github.com/gists/{gist_id}'

        gist_response = requests.get(gist_url, headers=headers)
        gist_response.raise_for_status()

        gist_content = gist_response.json()
        files_content = gist_content.get('files', {})

        # 更新或添加 V2ray 文件内容
        files_content['v2ray.txt'] = {
            "content": combined_v2ray_content
        }

        update_response = requests.patch(gist_url, headers=headers, json={"files": files_content})
        update_response.raise_for_status()

if __name__ == "__main__":
    main()
