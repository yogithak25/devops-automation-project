import docker
import time
import socket
import io
import tarfile
from config.env_loader import get_env

config = get_env()


# -----------------------------
# DOCKER CLIENT
# -----------------------------
def get_docker_client():
    try:
        return docker.from_env()
    except Exception:
        return docker.DockerClient(base_url="npipe://./pipe/docker_engine")


client = get_docker_client()


# -----------------------------
# CHECK CONTAINER EXISTS
# -----------------------------
def container_exists(name):
    try:
        client.containers.get(name)
        return True
    except:
        return False


# -----------------------------
# WAIT FOR SERVICE
# -----------------------------
def wait_for_service(port, name):
    print(f"\n⏳ Waiting for {name}...\n")

    host = config["EC2_IP"]

    for i in range(40):
        try:
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            print(f"✅ {name} ready")
            return
        except:
            print(f"Waiting... ({i+1}/40)")
            time.sleep(5)

    raise Exception(f"❌ {name} not reachable")


# -----------------------------
# BUILD JENKINS IMAGE 
# -----------------------------
def ensure_jenkins_image():
    image_name = "jenkins-docker"

    try:
        client.images.get(image_name)
        print("✅ Jenkins Docker image already exists")
        return image_name
    except:
        print("🚀 Building Jenkins Docker image...")

    dockerfile = """
    FROM jenkins/jenkins:lts
    USER root
    RUN apt-get update && \
        apt-get install -y docker.io && \
        apt-get clean
    USER jenkins
    """

    # Create TAR build context
    file_obj = io.BytesIO()
    with tarfile.open(fileobj=file_obj, mode='w') as tar:
        dockerfile_bytes = dockerfile.encode('utf-8')
        tarinfo = tarfile.TarInfo(name="Dockerfile")
        tarinfo.size = len(dockerfile_bytes)
        tar.addfile(tarinfo, io.BytesIO(dockerfile_bytes))

    file_obj.seek(0)

    client.images.build(
        fileobj=file_obj,
        custom_context=True,
        tag=image_name,
        rm=True
    )

    print("✅ Jenkins Docker image built")
    return image_name


# -----------------------------
# GENERIC CONTAINER
# -----------------------------
def ensure_container(name, image, ports):

    if container_exists(name):
        container = client.containers.get(name)
        container.reload()

        if container.status != "running":
            print(f"🔄 Starting {name}...")
            container.start()
        else:
            print(f"✅ {name} already running")

        return container

    print(f"🚀 Creating {name}...")

    return client.containers.run(
        image,
        name=name,
        detach=True,
        ports=ports
    )


# -----------------------------
# JENKINS 
# -----------------------------
def ensure_jenkins():

    name = "jenkins"
    docker_sock = "/var/run/docker.sock"
    jenkins_volume = "jenkins_home"

    image = ensure_jenkins_image()

    if container_exists(name):
        container = client.containers.get(name)
        container.reload()

        mounts = container.attrs.get("Mounts", [])

        sock_ok = any(m.get("Source") == docker_sock for m in mounts)

        if not sock_ok:
            print("⚠️ Jenkins missing docker.sock → recreating...")
            container.remove(force=True)
        else:
            if container.status != "running":
                print("🔄 Starting Jenkins...")
                container.start()
            else:
                print("✅ Jenkins already running")

            return container

    print("🚀 Creating Jenkins container...")

    return client.containers.run(
        image,
        name=name,
        detach=True,
        user="root",
        ports={"8080/tcp": 8080},
        volumes={
            docker_sock: {
                "bind": "/var/run/docker.sock",
                "mode": "rw"
            },
            jenkins_volume: {
                "bind": "/var/jenkins_home",
                "mode": "rw"
            }
        }
    )


# -----------------------------
# SETUP INFRA
# -----------------------------
def setup_infra():

    print("\n🔥 Starting Docker Infra...\n")

    # Jenkins
    ensure_jenkins()

    # SonarQube
    ensure_container(
        "sonarqube",
        "sonarqube:lts",
        {"9000/tcp": 9000}
    )

    # Nexus
    ensure_container(
        "nexus",
        "sonatype/nexus3",
        {"8081/tcp": 8081}
    )

    # Wait for services
    wait_for_service(8080, "Jenkins")
    wait_for_service(9000, "SonarQube")
    wait_for_service(8081, "Nexus")

    print("\n🌐 ACCESS YOUR TOOLS:\n")
    print(f"Jenkins   → {config['JENKINS_URL']}")
    print(f"SonarQube → {config['SONAR_URL']}")
    print(f"Nexus     → {config['NEXUS_URL']}")

    print("\n✅ Infra Ready\n")
