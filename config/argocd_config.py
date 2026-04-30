import requests
import time
import base64
import docker
import urllib3
from config.env_loader import get_env

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
config = get_env()

K3S_CONTAINER = "k3s-server"
NAMESPACE = "argocd"

client = docker.from_env()


# -----------------------------
# UPDATE ENV
# -----------------------------
def write_env(key, value, file_path="env.txt"):
    lines = []
    found = False

    with open(file_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}\n")
                found = True
            else:
                lines.append(line)

    if not found:
        lines.append(f"{key}={value}\n")

    with open(file_path, "w") as f:
        f.writelines(lines)

    print(f"✅ {key} updated in env.txt")


# -----------------------------
# EXEC KUBECTL 
# -----------------------------
def kubectl(cmd):
    container = client.containers.get(K3S_CONTAINER)
    result = container.exec_run(f"kubectl {cmd}")
    return result.output.decode()


# -----------------------------
# SAFE REQUEST
# -----------------------------
def safe_request(method, url, **kwargs):
    for _ in range(3):
        try:
            return requests.request(method, url, timeout=10, verify=False, **kwargs)
        except:
            time.sleep(2)
    raise Exception(f"❌ API failed: {url}")


# -----------------------------
# WAIT FOR ARGOCD UI
# -----------------------------
def wait_for_argocd(url):
    print("\n⏳ Waiting for ArgoCD UI...\n")

    for i in range(40):
        try:
            r = safe_request("GET", url)
            if r.status_code in [200, 307]:
                print("✅ ArgoCD UI Ready")
                return
        except:
            pass

        print(f"Waiting... ({i+1}/40)")
        time.sleep(5)

    raise Exception("❌ ArgoCD UI not reachable")


# -----------------------------
# GET PASSWORD (FROM K3S)
# -----------------------------
def get_password():
    output = kubectl(
        f"get secret argocd-initial-admin-secret -n {NAMESPACE} "
        f"-o jsonpath='{{.data.password}}'"
    )

    return base64.b64decode(output.strip()).decode()


# -----------------------------
# LOGIN
# -----------------------------
def login(url, password):
    r = safe_request(
        "POST",
        f"{url}/api/v1/session",
        json={
            "username": config["ARGOCD_USER"],
            "password": password
        }
    )

    if r.status_code != 200:
        raise Exception("❌ Login failed")

    return r.json()["token"]


# -----------------------------
# ENSURE PASSWORD
# -----------------------------
def ensure_password(url):
    print("\n🔐 Ensuring ArgoCD password...\n")

    user = config["ARGOCD_USER"]
    current_pwd = config.get("ARGOCD_PASSWORD")
    new_pwd = config.get("ARGOCD_NEW_PASSWORD")

    # -----------------------------
    # 1️⃣ TRY CURRENT PASSWORD
    # -----------------------------
    try:
        token = login(url, current_pwd)
        print("✅ Logged in with ARGOCD_PASSWORD")

        # update if new password provided
        if new_pwd and new_pwd != current_pwd:
            print("🔄 Updating password → ARGOCD_NEW_PASSWORD")

            headers = {"Authorization": f"Bearer {token}"}

            r = safe_request(
                "PUT",
                f"{url}/api/v1/account/password",
                headers=headers,
                json={
                    "currentPassword": current_pwd,
                    "newPassword": new_pwd
                }
            )

            if r.status_code not in [200, 204]:
                raise Exception(f"❌ Password update failed: {r.text}")

            print("✅ Password updated successfully")

            write_env("ARGOCD_PASSWORD", new_pwd)
            config["ARGOCD_PASSWORD"] = new_pwd

            return login(url, new_pwd)

        return token

    except:
        pass

    # -----------------------------
    # 2️⃣ TRY NEW PASSWORD
    # -----------------------------
    if new_pwd:
        try:
            token = login(url, new_pwd)
            print("✅ Logged in with ARGOCD_NEW_PASSWORD")

            write_env("ARGOCD_PASSWORD", new_pwd)
            config["ARGOCD_PASSWORD"] = new_pwd

            return token
        except:
            pass

    # -----------------------------
    # 3️⃣ FIRST RUN (INITIAL PASSWORD)
    # -----------------------------
    print("ℹ️ Trying initial password...")

    try:
        initial_pwd = get_password()
        token = login(url, initial_pwd)

        target = new_pwd if new_pwd else current_pwd

        print("🔄 First-time setup → setting password")

        headers = {"Authorization": f"Bearer {token}"}

        r = safe_request(
            "PUT",
            f"{url}/api/v1/account/password",
            headers=headers,
            json={
                "currentPassword": initial_pwd,
                "newPassword": target
            }
        )

        if r.status_code not in [200, 204]:
            raise Exception(f"❌ Initial setup failed: {r.text}")

        print("✅ Password initialized successfully")

        write_env("ARGOCD_PASSWORD", target)
        config["ARGOCD_PASSWORD"] = target

        return login(url, target)

    except:
        pass

    # -----------------------------
    # 4️⃣ FAIL
    # -----------------------------
    raise Exception("❌ Unable to determine ArgoCD password state")

# -----------------------------
# GET APP
# -----------------------------
def get_app(url, token, name):
    headers = {"Authorization": f"Bearer {token}"}

    r = safe_request(
        "GET",
        f"{url}/api/v1/applications/{name}",
        headers=headers
    )

    return r.json() if r.status_code == 200 else None


# -----------------------------
# CHECK SAME
# -----------------------------
def app_is_same(existing, repo):
    try:
        return existing["spec"]["source"]["repoURL"] == repo
    except:
        return False


# -----------------------------
# ENSURE APP
# -----------------------------
def ensure_app(url, token, name, repo):
    print(f"\n🚀 Ensuring app: {name}")

    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "metadata": {"name": name},
        "spec": {
            "project": "default",
            "source": {
                "repoURL": repo,
                "targetRevision": "main",
                "path": "."
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "default"
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True
                }
            }
        }
    }

    existing = get_app(url, token, name)

    if existing:
        if app_is_same(existing, repo):
            print(f"✅ {name} already configured")
            return

        print(f"🔄 Updating app: {name}")

        safe_request(
            "PUT",
            f"{url}/api/v1/applications/{name}",
            headers=headers,
            json=payload
        )

        print(f"✅ {name} updated")

    else:
        print(f"➕ Creating app: {name}")

        safe_request(
            "POST",
            f"{url}/api/v1/applications",
            headers=headers,
            json=payload
        )

        print(f"✅ {name} created")


# -----------------------------
# MAIN
# -----------------------------
def setup_argocd():
    print("\n🚀 ARGOCD CONFIG STARTED\n")

    url = config["ARGOCD_URL"]

    wait_for_argocd(url)

    token = ensure_password(url)

    apps = [
        {
            "name": "java-app",
            "repo": "https://github.com/yogithak25/devops-project-k8s-manifests.git"
        },
        {
            "name": "python-app",
            "repo": "https://github.com/yogithak25/python-devops-k8s-manifests.git"
        }
    ]

    for app in apps:
        ensure_app(url, token, app["name"], app["repo"])

    print("\n✅ ArgoCD CONFIG COMPLETE\n")
