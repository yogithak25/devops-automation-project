import docker

# -----------------------------
# DOCKER CLIENT 
# -----------------------------
def get_client():
    try:
        return docker.from_env()
    except Exception:
        return docker.DockerClient(base_url="npipe://./pipe/docker_engine")


client = get_client()


# -----------------------------
# CHECK IMAGE EXISTS
# -----------------------------
def image_exists(image_name):
    try:
        client.images.get(image_name)
        return True
    except:
        return False


# -----------------------------
# SETUP TRIVY 
# -----------------------------
def setup_trivy():

    print("\n🔐 Setting up Trivy...\n")

    image = "aquasec/trivy:0.50.0"

    if image_exists(image):
        print("✅ Trivy image already available")
    else:
        print("⬇️ Pulling Trivy image...")
        client.images.pull(image)
        print("✅ Trivy image pulled")

    print("\n✅ Trivy ready for scanning\n")
