import os
import time
import requests
from config.env_loader import get_env

config = get_env()
BASE_URL = config["SONAR_URL"]
ENV_FILE = "env.txt"


# -----------------------------
# SAFE REQUEST 
# -----------------------------
def safe_request(method, url, **kwargs):
    for _ in range(5):
        try:
            return requests.request(method, url, timeout=10, **kwargs)
        except Exception:
            time.sleep(3)
    raise Exception(f"❌ Failed API call: {url}")


# -----------------------------
# WAIT FOR SONAR
# -----------------------------
def wait_for_sonar():
    print("\n⏳ Waiting for SonarQube...\n")

    for i in range(60):
        try:
            r = safe_request("GET", f"{BASE_URL}/api/system/status")
            if r.json().get("status") == "UP":
                print("✅ SonarQube Ready")
                return
        except:
            pass

        print(f"Waiting... ({i+1}/60)")
        time.sleep(5)

    raise Exception("❌ SonarQube not ready")


# -----------------------------
# AUTH
# -----------------------------
def get_auth():
    return (config["SONAR_USER"], config["SONAR_PASSWORD"])


# -----------------------------
# UPDATE ENV FILE
# -----------------------------
def update_env(key, value):

    lines = []
    updated = False

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()

    found = False

    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            found = True
            if line.strip() != f"{key}={value}":
                lines[i] = f"{key}={value}\n"
                updated = True

    if not found:
        lines.append(f"{key}={value}\n")
        updated = True

    if updated:
        with open(ENV_FILE, "w") as f:
            f.writelines(lines)
        print(f"✅ {key} updated in env.txt")
    else:
        print(f"✅ {key} already up-to-date")


# -----------------------------
# ENSURE PASSWORD
# -----------------------------
def ensure_password():
    print("\n🔐 Ensuring Sonar password...\n")

    sonar_url = BASE_URL
    user = config["SONAR_USER"]

    current_password = config.get("SONAR_PASSWORD", "admin")
    new_password = config.get("SONAR_NEW_PASSWORD")

    # -----------------------------
    # 1️⃣ TRY CURRENT PASSWORD
    # -----------------------------
    r = safe_request(
        "GET",
        f"{sonar_url}/api/authentication/validate",
        auth=(user, current_password)
    )

    if r.status_code == 200 and r.json().get("valid"):
        print("✅ Logged in with SONAR_PASSWORD")

        # 🔥 UPDATE ONLY IF NEW PASSWORD PROVIDED
        if new_password and new_password != current_password:
            print("🔄 Updating password → SONAR_NEW_PASSWORD")

            r = safe_request(
                "POST",
                f"{sonar_url}/api/users/change_password",
                auth=(user, current_password),
                data={
                    "login": user,
                    "previousPassword": current_password,
                    "password": new_password
                }
            )

            if r.status_code in [200, 204]:
                print("✅ Password updated successfully")

                # ✅ Update env file
                update_env("SONAR_PASSWORD", new_password)

                # 🔥 CRITICAL FIX → update runtime config
                config["SONAR_PASSWORD"] = new_password

                return
            else:
                raise Exception(f"❌ Update failed: {r.text}")

        print("✅ No password change required")
        return

    # -----------------------------
    # 2️⃣ TRY NEW PASSWORD
    # -----------------------------
    if new_password:
        r = safe_request(
            "GET",
            f"{sonar_url}/api/authentication/validate",
            auth=(user, new_password)
        )

        if r.status_code == 200 and r.json().get("valid"):
            print("✅ Logged in with SONAR_NEW_PASSWORD")

            # Sync env + runtime
            update_env("SONAR_PASSWORD", new_password)
            config["SONAR_PASSWORD"] = new_password

            return

    # -----------------------------
    # 3️⃣ TRY DEFAULT (FIRST RUN)
    # -----------------------------
    print("ℹ️ Trying default credentials...")

    r = safe_request(
        "GET",
        f"{sonar_url}/api/authentication/validate",
        auth=(user, "admin")
    )

    if r.status_code == 200 and r.json().get("valid"):

        target = new_password if new_password else current_password

        print("🔄 First-time setup → setting password")

        r = safe_request(
            "POST",
            f"{sonar_url}/api/users/change_password",
            auth=(user, "admin"),
            data={
                "login": user,
                "previousPassword": "admin",
                "password": target
            }
        )

        if r.status_code in [200, 204]:
            print("✅ Password initialized successfully")

            # Sync env + runtime
            update_env("SONAR_PASSWORD", target)
            config["SONAR_PASSWORD"] = target

            return

    # -----------------------------
    # 4️⃣ FAIL
    # -----------------------------
    raise Exception("❌ Unknown password state")


# -----------------------------
# TOKEN
# -----------------------------
def is_token_valid(token):
    try:
        r = safe_request(
            "GET",
            f"{BASE_URL}/api/authentication/validate",
            auth=(token, "")
        )
        return r.status_code == 200 and r.json().get("valid")
    except:
        return False


def generate_token():
    print("\n🔑 Ensuring Sonar token...\n")

    token = config.get("SONAR_TOKEN")

    if token and is_token_valid(token):
        print("✅ Existing token valid")
        return token

    r = safe_request(
        "POST",
        f"{BASE_URL}/api/user_tokens/generate",
        auth=get_auth(),
        data={"name": "devops-token"}
    )

    if r.status_code != 200:
        raise Exception("❌ Token generation failed")

    token = r.json()["token"]

    update_env("SONAR_TOKEN", token)

    print("✅ Token generated & saved")

    return token


# -----------------------------
# PROJECT
# -----------------------------
def ensure_project(project_key):

    r = safe_request(
        "GET",
        f"{BASE_URL}/api/projects/search",
        auth=get_auth(),
        params={"projects": project_key}
    )

    # SAFE JSON HANDLING
    if r.status_code != 200:
        raise Exception(f"❌ API failed: {r.status_code} {r.text}")

    try:
        data = r.json()
    except Exception:
        raise Exception(f"❌ Invalid JSON response: {r.text}")

    if data.get("components"):
        print(f"✅ {project_key} exists")
        return

    # CREATE PROJECT
    safe_request(
        "POST",
        f"{BASE_URL}/api/projects/create",
        auth=get_auth(),
        data={
            "project": project_key,
            "name": project_key
        }
    )

    print(f"✅ {project_key} created")

# -----------------------------
# QUALITY GATE
# -----------------------------
def ensure_quality_gate():

    gate_name = "custom-quality-gate"

    r = safe_request(
        "GET",
        f"{BASE_URL}/api/qualitygates/list",
        auth=get_auth()
    )

    gate_id = None

    for g in r.json()["qualitygates"]:
        if g["name"] == gate_name:
            gate_id = g["id"]
            print("✅ Quality gate exists")
            break

    if not gate_id:
        r = safe_request(
            "POST",
            f"{BASE_URL}/api/qualitygates/create",
            auth=get_auth(),
            data={"name": gate_name}
        )
        gate_id = r.json()["id"]
        print("✅ Quality gate created")

    # Ensure coverage rule
    r = safe_request(
        "GET",
        f"{BASE_URL}/api/qualitygates/show",
        auth=get_auth(),
        params={"id": gate_id}
    )

    conditions = r.json().get("conditions", [])

    if not any(c["metric"] == "coverage" for c in conditions):
        safe_request(
            "POST",
            f"{BASE_URL}/api/qualitygates/create_condition",
            auth=get_auth(),
            data={
                "gateId": gate_id,
                "metric": "coverage",
                "op": "LT",
                "error": "20"
            }
        )
        print("✅ Coverage condition added")

    return gate_name


# -----------------------------
# SET DEFAULT GATE
# -----------------------------
def set_default_quality_gate(gate_name):

    safe_request(
        "POST",
        f"{BASE_URL}/api/qualitygates/set_as_default",
        auth=get_auth(),
        data={"name": gate_name}
    )

    print("✅ Default quality gate set")


# -----------------------------
# ASSIGN GATE
# -----------------------------
def assign_quality_gate(project_key, gate_name):

    safe_request(
        "POST",
        f"{BASE_URL}/api/qualitygates/select",
        auth=get_auth(),
        data={
            "projectKey": project_key,
            "gateName": gate_name
        }
    )

    print(f"✅ {project_key} linked to quality gate")


# -----------------------------
# WEBHOOK
# -----------------------------
def ensure_webhook():

    webhook_url = f"{config['JENKINS_URL']}/sonarqube-webhook/"

    r = safe_request(
        "GET",
        f"{BASE_URL}/api/webhooks/list",
        auth=get_auth()
    )

    for w in r.json().get("webhooks", []):
        if w["url"] == webhook_url:
            print("✅ Webhook exists")
            return

    safe_request(
        "POST",
        f"{BASE_URL}/api/webhooks/create",
        auth=get_auth(),
        data={
            "name": "jenkins-webhook",
            "url": webhook_url
        }
    )

    print("✅ Webhook created")


# -----------------------------
# MAIN
# -----------------------------
def setup_sonarqube():

    print("\n🚀 SONARQUBE CONFIG STARTED\n")

    wait_for_sonar()
    ensure_password()

    token = generate_token()

    ensure_project("java-devops-project")
    ensure_project("python-devops-project")

    gate = ensure_quality_gate()

    set_default_quality_gate(gate)
    assign_quality_gate("java-devops-project", gate)
    assign_quality_gate("python-devops-project", gate)

    ensure_webhook()

    print("\n✅ SONARQUBE CONFIG COMPLETED\n")

    return token
