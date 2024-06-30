import requests
import base64
import json
import os
import sys
from datetime import datetime

def fetch_gist_content(gist_url, headers):
    response = requests.get(gist_url, headers=headers)
    response.raise_for_status()
    return response.json()

def update_gist_content(gist_url, headers, files_update):
    response = requests.patch(gist_url, headers=headers, json={"files": files_update})
    response.raise_for_status()
    return response.json()

def main():
    gist_pat = os.getenv("GIST_PAT")
    gist_link = os.getenv("GIST_LINK")
    v2ray_gist_link = os.getenv("V2RAY_GIST_LINK")

    if not gist_pat or not gist_link or not v2ray_gist_link:
        print("Error: Environment variables GIST_PAT, GIST_LINK and V2RAY_GIST_LINK must be set", file=sys.stderr)
        sys.exit(1)

    headers = {
        'Authorization': f'token {gist_pat}'
    }

    gist_id = gist_link.split('/')[-1]
    gist_url = f'https://api.github.com/gists/{gist_id}'
    v2ray_gist_id = v2ray_gist_link.split('/')[-1]
    v2ray_gist_url = f'https://api.github.com/gists/{v2ray_gist_id}'

    # 获取 Gist 内容并读取 v2ray.txt 文件
    try:
        gist_content = fetch_gist_content(gist_url, headers)
        if 'v2ray.txt' not in gist_content['files']:
            print("Error: v2ray.txt not found in the Gist", file=sys.stderr)
            sys.exit(1)
        v2ray_content = gist_content['files']['v2ray.txt']['content']
    except Exception as e:
        print(f"Error fetching or reading v2ray.txt: {e}", file=sys.stderr)
        sys.exit(1)

    # 添加更新日期的记录
    try:
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        date_record = f"vmess://{base64.urlsafe_b64encode(json.dumps({'ps': f'Update Date: {current_date}', 'add': '127.0.0.1', 'port': '0', 'id': '00000000-0000-0000-0000-000000000000', 'aid': '0', 'net': 'tcp', 'type': 'none', 'host': '', 'path': '', 'tls': ''}).encode()).decode()}\n"

        updated_v2ray_content = date_record + v2ray_content

        # 更新 Gist 中的 v2ray.txt 文件
        files_update = {
            'v2ray.txt': {
                'content': updated_v2ray_content
            }
        }
        update_gist_content(v2ray_gist_url, headers, files_update)
        print("Successfully updated the Gist with new content.")
    except Exception as e:
        print(f"Error updating Gist: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
