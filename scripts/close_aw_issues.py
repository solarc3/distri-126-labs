import os
import sys
import urllib.request
import json

def get_aw_issues(token):
    url = "https://api.github.com/repos/solarc3/distri-126-labs/issues?state=open&per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    req = urllib.request.Request(url, headers=headers)
    
    issues_to_close = []
    try:
        with urllib.request.urlopen(req) as response:
            issues = json.loads(response.read().decode())
            for i in issues:
                if "pull_request" not in i and "[aw] Agent" in i.get("title", ""):
                    issues_to_close.append(i["number"])
    except Exception as e:
        print(f"Error fetching issues: {e}")
    return issues_to_close

def close_issue(issue_number, token):
    url = f"https://api.github.com/repos/solarc3/distri-126-labs/issues/{issue_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {"state": "closed"}
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="PATCH")
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Issue #{issue_number} cerrado.")
    except Exception as e:
        print(f"Error cerrando issue #{issue_number}: {e}")

if __name__ == "__main__":
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Error: Debes setear la variable de entorno GITHUB_TOKEN o GH_TOKEN")
        sys.exit(1)
        
    print("Buscando issues '[aw] Agent'...")
    issues = get_aw_issues(token)
    
    if not issues:
        print("No se encontraron issues para cerrar.")
    else:
        print(f"Se encontraron {len(issues)} issues. Cerrando...")
        for num in issues:
            close_issue(num, token)
        print("¡Limpieza completada!")
