import time
import base64
import requests
import docker
from config.env_loader import get_env

config = get_env()
EC2_IP = config["EC2_IP"]

K3S_CONTAINER = "k3s-server"
NAMESPACE = "argocd"
NODEPORT = "32578"

ARGOCD_MANIFEST_URL = "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"


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
# EXEC KUBECTL
# -----------------------------
def kubectl(cmd):
    container = client.containers.get(K3S_CONTAINER)
    result = container.exec_run(f"kubectl {cmd}")
    return result.output.decode()


# -----------------------------
# NAMESPACE CHECK
# -----------------------------
def namespace_exists():
    output = kubectl("get ns")
    return NAMESPACE in output


# -----------------------------
# CREATE NAMESPACE
# -----------------------------
def create_namespace():
    print("\n📦 Creating namespace...\n")
    kubectl(f"create ns {NAMESPACE}")
    print("✅ Namespace created")


# -----------------------------
# CHECK INSTALLED
# -----------------------------
def argocd_installed():
    try:
        output = kubectl(f"get pods -n {NAMESPACE}")
        return "argocd-server" in output
    except:
        return False

# -----------------------------
# INSTALL ARGOCD
# -----------------------------
def install_argocd_manifest():
    print("\n🚀 Installing ArgoCD...\n")

    container = client.containers.get(K3S_CONTAINER)

    # Apply directly from URL (BEST WAY)
    container.exec_run(
        f"kubectl apply -n {NAMESPACE} -f {ARGOCD_MANIFEST_URL}"
    )

    print("✅ ArgoCD manifest applied")

# -----------------------------
# PATCH SERVICE
# -----------------------------
def patch_service():
    print("\n🔧 Configuring NodePort...\n")

    output = kubectl(f"get svc argocd-server -n {NAMESPACE} -o json")

    if str(NODEPORT) in output:
        print("✅ NodePort already configured")
        return

    kubectl(
        f"patch svc argocd-server -n {NAMESPACE} "
        f"-p '{{\"spec\":{{\"type\":\"NodePort\",\"ports\":[{{\"port\":80,\"targetPort\":8080,\"nodePort\":{NODEPORT}}}]}}}}'"
    )

    print(f"✅ NodePort set: {NODEPORT}")

# -----------------------------
# WAIT FOR READY
# -----------------------------
def wait_for_ready():
    print("\n⏳ Waiting for ArgoCD...\n")

    for i in range(60):  

        output = kubectl(f"get pods -n {NAMESPACE}")

        if "argocd-server" in output:
            # Check READY column (like 1/1, 2/2)
            lines = output.split("\n")

            all_ready = True

            for line in lines:
                if "argocd" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        ready = parts[1]   # e.g. 1/1
                        if not ready.startswith("1/1") and not ready.startswith("2/2"):
                            all_ready = False

            if all_ready:
                print("✅ ArgoCD Ready")
                return

        print(f"Waiting... ({i+1}/60)")
        time.sleep(5)

    raise Exception("❌ ArgoCD not ready")

# -----------------------------
# GET PASSWORD
# -----------------------------
def get_password():
    try:
        output = kubectl(
            f"get secret argocd-initial-admin-secret -n {NAMESPACE} "
            f"-o jsonpath='{{.data.password}}'"
        )

        return base64.b64decode(output.strip()).decode()
    except:
        return None


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def install_argocd():
    print("\n🚀 ArgoCD Setup Started\n")

    if not namespace_exists():
        create_namespace()
    else:
        print("✅ Namespace exists")

    if not argocd_installed():
        install_argocd_manifest()
    else:
        print("✅ ArgoCD already installed")
    patch_service()
    wait_for_ready()

    password = get_password()

    print("\n🌐 ArgoCD UI:")
    print(f"http://{EC2_IP}:{NODEPORT}")

    print("\n✅ ArgoCD READY\n")
