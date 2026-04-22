import os
from dotenv import load_dotenv

load_dotenv("env.txt")


def get_env():

    ip = os.getenv("EC2_IP")

    if not ip:
        raise Exception("❌ EC2_IP not set in env.txt")

    config = {

        "EC2_IP": ip,

        # URLs
        "JENKINS_URL": f"http://{ip}:8080",
        "SONAR_URL": f"http://{ip}:9000",
        "NEXUS_URL": f"http://{ip}:8081",
        "ARGOCD_URL": f"https://{ip}:32578",

        # Jenkins
        "JENKINS_USER": os.getenv("JENKINS_USER"),
        "JENKINS_PASSWORD": os.getenv("JENKINS_PASSWORD"),
        "JENKINS_TOKEN": os.getenv("JENKINS_TOKEN"),

        # Sonar
        "SONAR_USER": os.getenv("SONAR_USER"),
        "SONAR_PASSWORD": os.getenv("SONAR_PASSWORD"),
        "SONAR_NEW_PASSWORD": os.getenv("SONAR_NEW_PASSWORD"),
        "SONAR_TOKEN": os.getenv("SONAR_TOKEN"),

        # Nexus
        "NEXUS_USER": os.getenv("NEXUS_USER"),
        "NEXUS_PASSWORD": os.getenv("NEXUS_PASSWORD"),

        # GitHub
        "GITHUB_USER": os.getenv("GITHUB_USER"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),

        # Docker
        "DOCKER_USER": os.getenv("DOCKER_USER"),
        "DOCKER_PASS": os.getenv("DOCKER_PASS"),

        # ArgoCD
        "ARGOCD_USER": os.getenv("ARGOCD_USER"),
        "ARGOCD_NEW_PASSWORD": os.getenv("ARGOCD_NEW_PASSWORD"),
    }

    return config
