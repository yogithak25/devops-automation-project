import time
import requests
import docker
from config.env_loader import get_env

config = get_env()
BASE_URL = config["NEXUS_URL"]
CONTAINER_NAME = "nexus"


# -----------------------------
# DOCKER CLIENT
# -----------------------------
def get_client():
    try:
        return docker.from_env()
    except:
        return docker.DockerClient(base_url="npipe://./pipe/docker_engine")


client = get_client()


# -----------------------------
# SAFE REQUEST
# -----------------------------
def safe_request(method, url, **kwargs):
    for _ in range(5):
        try:
            return requests.request(method, url, timeout=10, **kwargs)
        except:
            time.sleep(3)
    raise Exception(f"❌ API call failed: {url}")


# -----------------------------
# WAIT FOR NEXUS
# -----------------------------
def wait_for_nexus():
    print("\n⏳ Waiting for Nexus...\n")

    for i in range(60):
        try:
            r = safe_request("GET", f"{BASE_URL}/service/rest/v1/status")
            if r.status_code in [200, 401]:
                print("✅ Nexus Ready")
                return
        except:
            pass

        print(f"Waiting... ({i+1}/60)")
        time.sleep(5)

    raise Exception("❌ Nexus not ready")


# -----------------------------
# GET INITIAL PASSWORD
# -----------------------------
def get_initial_password():
    print("\n🔑 Fetching initial password...\n")

    try:
        container = client.containers.get(CONTAINER_NAME)

        for _ in range(10):
            result = container.exec_run("cat /nexus-data/admin.password")
            pwd = result.output.decode().strip()

            if pwd:
                print("✅ Initial password fetched")
                return pwd

            time.sleep(3)

    except:
        pass

    print("ℹ️ Initial password not found (already changed)")
    return None


# -----------------------------
# CHECK PASSWORD
# -----------------------------
def is_password_changed():
    try:
        r = safe_request(
            "GET",
            f"{BASE_URL}/service/rest/v1/status",
            auth=(config["NEXUS_USER"], config["NEXUS_PASSWORD"])
        )
        return r.status_code == 200
    except:
        return False


# -----------------------------
# CHANGE PASSWORD
# -----------------------------
def change_password(initial_pwd):

    if is_password_changed():
        print("✅ Password already updated")
        return

    if not initial_pwd:
        raise Exception("❌ Initial password required")

    print("\n🔐 Changing Nexus password...\n")

    r = safe_request(
        "PUT",
        f"{BASE_URL}/service/rest/v1/security/users/admin/change-password",
        auth=("admin", initial_pwd),
        headers={"Content-Type": "text/plain"},
        data=config["NEXUS_PASSWORD"]
    )

    if r.status_code in [200, 204]:
        print("✅ Password updated")
    else:
        raise Exception(f"❌ Password change failed: {r.text}")


# -----------------------------
# CHECK REPO EXISTS
# -----------------------------
def repo_exists(repo_name):

    r = safe_request(
        "GET",
        f"{BASE_URL}/service/rest/v1/repositories",
        auth=(config["NEXUS_USER"], config["NEXUS_PASSWORD"])
    )

    repos = [repo["name"] for repo in r.json()]
    return repo_name in repos


# -----------------------------
# CREATE MAVEN REPO
# -----------------------------
def create_maven_repo():

    repo_name = "maven-releases-custom"

    if repo_exists(repo_name):
        print("✅ Maven repo already exists")
        return repo_name

    print("\n📦 Creating Maven repository...\n")

    payload = {
        "name": repo_name,
        "online": True,
        "storage": {
            "blobStoreName": "default",
            "strictContentTypeValidation": True,
            "writePolicy": "ALLOW"
        },
        "maven": {
            "versionPolicy": "RELEASE",
            "layoutPolicy": "STRICT"
        }
    }

    r = safe_request(
        "POST",
        f"{BASE_URL}/service/rest/v1/repositories/maven/hosted",
        auth=(config["NEXUS_USER"], config["NEXUS_PASSWORD"]),
        json=payload
    )

    if r.status_code in [200, 201]:
        print("✅ Repository created")
    else:
        raise Exception(f"❌ Repo creation failed: {r.text}")

    return repo_name


# -----------------------------
# GET REPO URL
# -----------------------------
def get_repo_url(repo_name):

    repo_url = f"{BASE_URL}/repository/{repo_name}/"
    print(f"🌐 Repo URL: {repo_url}")

    return repo_url


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def setup_nexus():

    print("\n🚀 NEXUS CONFIG STARTED\n")

    wait_for_nexus()

    initial_pwd = get_initial_password()
    change_password(initial_pwd)

    repo = create_maven_repo()
    repo_url = get_repo_url(repo)

    print("\n✅ NEXUS CONFIG COMPLETED\n")

    return repo_url
