import requests
import time
from config.env_loader import get_env

config = get_env()

BASE_API = "https://api.github.com"


# -----------------------------
# SAFE REQUEST 
# -----------------------------
def safe_request(method, url, **kwargs):
    for _ in range(3):
        try:
            r = requests.request(method, url, timeout=10, **kwargs)
            return r
        except:
            time.sleep(2)
    raise Exception(f"❌ API request failed: {url}")


# -----------------------------
# COMMON HEADERS
# -----------------------------
def headers():
    return {
        "Authorization": f"token {config['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json"
    }


# -----------------------------
# GET ALL WEBHOOKS
# -----------------------------
def get_hooks(repo):
    url = f"{BASE_API}/repos/{config['GITHUB_USER']}/{repo}/hooks"

    r = safe_request("GET", url, headers=headers())

    if r.status_code != 200:
        raise Exception(f"❌ Failed to fetch hooks for {repo}: {r.text}")

    return r.json()


# -----------------------------
# CHECK WEBHOOK EXISTS
# -----------------------------
def webhook_exists(repo):
    target_url = f"{config['JENKINS_URL']}/github-webhook/"

    hooks = get_hooks(repo)

    for hook in hooks:
        if hook.get("config", {}).get("url") == target_url:
            return True

    return False


# -----------------------------
# ENSURE WEBHOOK
# -----------------------------
def ensure_webhook(repo):
    print(f"\n🔗 Ensuring webhook for repo: {repo}")

    try:
        if webhook_exists(repo):
            print(f"✅ Webhook already configured for {repo}")
            return
    except Exception as e:
        print(f"⚠️ Skipping {repo}: {e}")
        return

    print(f"➕ Creating webhook for {repo}...")

    url = f"{BASE_API}/repos/{config['GITHUB_USER']}/{repo}/hooks"

    payload = {
        "name": "web",
        "active": True,
        "events": ["push"],
        "config": {
            "url": f"{config['JENKINS_URL']}/github-webhook/",
            "content_type": "json",
            "insecure_ssl": "0"
        }
    }

    r = safe_request("POST", url, headers=headers(), json=payload)

    if r.status_code in [200, 201]:
        print(f"✅ Webhook created for {repo}")
    else:
        raise Exception(f"❌ Failed to create webhook for {repo}: {r.text}")


# -----------------------------
# VERIFY WEBHOOK
# -----------------------------
def verify_webhook(repo):
    target_url = f"{config['JENKINS_URL']}/github-webhook/"

    hooks = get_hooks(repo)

    for hook in hooks:
        if hook.get("config", {}).get("url") == target_url:
            print(f"✅ Webhook verified for {repo}")
            return

    raise Exception(f"❌ Webhook verification failed for {repo}")


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def setup_github():
    print("\n🚀 GITHUB WEBHOOK SETUP STARTED\n")

    repos = [
        "end-to-end-devops-project",
        "python-devops-project"
    ]

    for repo in repos:
        ensure_webhook(repo)
        verify_webhook(repo)

    print("\n✅ GitHub Webhooks ensured\n")
