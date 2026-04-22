import time
import docker
from config.env_loader import get_env

config = get_env()
CONTAINER_NAME = "k3s-server"


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
# GET CONTAINER
# -----------------------------
def get_container():
    try:
        return client.containers.get(CONTAINER_NAME)
    except:
        return None


# -----------------------------
# CHECK RUNNING
# -----------------------------
def cluster_running(container):
    return container and container.status == "running"


# -----------------------------
# DELETE CONTAINER
# -----------------------------
def delete_container(container):
    if container:
        print("⚠️ Removing existing k3s container...")
        container.remove(force=True)
        print("✅ Removed")


# -----------------------------
# CREATE CLUSTER
# -----------------------------
def create_cluster():

    print("\n☸️ Creating Kubernetes cluster (k3s)...\n")

    return client.containers.run(
        "rancher/k3s:v1.30.0-k3s1",
        name=CONTAINER_NAME,
        privileged=True,
        detach=True,
        ports={
            "6443/tcp": 6443,
            "32578/tcp": 32578,
            "30007/tcp": 30007,
            "30008/tcp": 30008,
        },
        restart_policy={"Name": "always"},
        command="server"
    )


# -----------------------------
# WAIT FOR K8S READY
# -----------------------------
def wait_for_ready(container):

    print("\n⏳ Waiting for Kubernetes...\n")

    for i in range(40):
        try:
            result = container.exec_run("kubectl get nodes")
            output = result.output.decode()

            if "Ready" in output:
                print("✅ Kubernetes Ready")
                return

        except Exception:
            pass

        print(f"Waiting... ({i+1}/40)")
        time.sleep(5)

    raise Exception("❌ Kubernetes not ready")


# -----------------------------
# VALIDATE PORTS
# -----------------------------
def ports_correct(container):

    container.reload()
    ports = container.attrs['NetworkSettings']['Ports']

    required = ["6443/tcp", "32578/tcp", "30007/tcp", "30008/tcp"]

    return all(ports.get(p) is not None for p in required)


# -----------------------------
# PRINT ACCESS INFO
# -----------------------------
def print_access():

    ip = config["EC2_IP"]

    print("\n🌐 Kubernetes Access:\n")
    print(f"K8s API     → https://{ip}:6443")
    print(f"ArgoCD UI   → https://{ip}:32578")
    print(f"NodePort Apps → http://{ip}:30007 / 30008")


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def install_kubernetes():

    print("\n🚀 Kubernetes Setup Started\n")

    container = get_container()

    if container:
        if not ports_correct(container):
            delete_container(container)
            container = create_cluster()
        else:
            if container.status != "running":
                print("🔄 Starting Kubernetes...")
                container.start()
            else:
                print("✅ Kubernetes already running")

    else:
        container = create_cluster()

    wait_for_ready(container)
    print_access()

    print("\n✅ Kubernetes READY\n")
