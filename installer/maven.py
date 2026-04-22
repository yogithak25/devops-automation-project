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
# INSTALL MAVEN 
# -----------------------------
def install_maven():

    print("\n📦 Setting up Maven (Docker-based)...\n")

    image = "maven:3.9.9-eclipse-temurin-17"

    if image_exists(image):
        print("✅ Maven image already available")
    else:
        print("⬇️ Pulling Maven image...")
        client.images.pull(image)
        print("✅ Maven image pulled")

    print("\n✅ Maven ready for pipeline usage\n")
