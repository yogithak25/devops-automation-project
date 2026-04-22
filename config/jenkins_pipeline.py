import requests
import time
from config.env_loader import get_env

config = get_env()


# -----------------------------
# SAFE REQUEST
# -----------------------------
def safe_request(session, method, url, **kwargs):
    for _ in range(3):
        try:
            r = session.request(method, url, timeout=10, **kwargs)
            return r
        except:
            time.sleep(2)
    raise Exception(f"❌ API failed: {url}")


# -----------------------------
# SESSION (WITH CRUMB)
# -----------------------------
def get_session():
    session = requests.Session()
    session.auth = (config["JENKINS_USER"], config["JENKINS_TOKEN"])

    r = session.get(f"{config['JENKINS_URL']}/crumbIssuer/api/json")

    if r.status_code == 200:
        crumb = r.json()
        session.headers.update({
            crumb["crumbRequestField"]: crumb["crumb"]
        })

    return session


# -----------------------------
# CHECK JOB EXISTS
# -----------------------------
def job_exists(session, job_name):
    r = safe_request(
        session,
        "GET",
        f"{config['JENKINS_URL']}/job/{job_name}/api/json"
    )
    return r.status_code == 200


# -----------------------------
# GET EXISTING CONFIG
# -----------------------------
def get_job_config(session, job_name):
    r = safe_request(
        session,
        "GET",
        f"{config['JENKINS_URL']}/job/{job_name}/config.xml"
    )
    return r.text if r.status_code == 200 else None


# -----------------------------
# GENERATE XML
# -----------------------------
def generate_pipeline_xml(job_name, repo_url, branch="main"):
    return f"""
<flow-definition plugin="workflow-job">
  <actions/>
  <description>{job_name}</description>
  <keepDependencies>false</keepDependencies>

  <properties>
    <org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
      <triggers>
        <com.cloudbees.jenkins.GitHubPushTrigger plugin="github">
          <spec></spec>
        </com.cloudbees.jenkins.GitHubPushTrigger>
      </triggers>
    </org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
  </properties>

  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition">
    <scm class="hudson.plugins.git.GitSCM">

      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{repo_url}</url>
          <credentialsId>github-cred</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>

      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/{branch}</name>
        </hudson.plugins.git.BranchSpec>
      </branches>

    </scm>

    <scriptPath>Jenkinsfile</scriptPath>
  </definition>

</flow-definition>
"""


# -----------------------------
# ENSURE PIPELINE
# -----------------------------
def ensure_pipeline(session, job_name, repo_url, branch="main"):

    print(f"\n🔧 Ensuring pipeline: {job_name}")

    new_xml = generate_pipeline_xml(job_name, repo_url, branch)
    headers = {"Content-Type": "application/xml"}

    # -----------------------------
    # IF EXISTS → COMPARE
    # -----------------------------
    if job_exists(session, job_name):

        existing_xml = get_job_config(session, job_name)

        if existing_xml and existing_xml.strip() == new_xml.strip():
            print(f"✅ {job_name} already configured")
            return

        print(f"🔄 Updating pipeline: {job_name}")

        r = safe_request(
            session,
            "POST",
            f"{config['JENKINS_URL']}/job/{job_name}/config.xml",
            headers=headers,
            data=new_xml
        )

        if r.status_code == 200:
            print(f"✅ {job_name} updated")
        else:
            raise Exception(f"❌ Failed to update {job_name}: {r.text}")

    # -----------------------------
    # CREATE
    # -----------------------------
    else:
        print(f"➕ Creating pipeline: {job_name}")

        r = safe_request(
            session,
            "POST",
            f"{config['JENKINS_URL']}/createItem?name={job_name}",
            headers=headers,
            data=new_xml
        )

        if r.status_code in [200, 201]:
            print(f"✅ {job_name} created")
        else:
            raise Exception(f"❌ Failed to create {job_name}: {r.text}")


# -----------------------------
# VERIFY PIPELINE
# -----------------------------
def verify_pipeline(session, job_name):
    r = safe_request(
        session,
        "GET",
        f"{config['JENKINS_URL']}/job/{job_name}/api/json"
    )

    if r.status_code == 200:
        print(f"✅ Verified pipeline: {job_name}")
    else:
        raise Exception(f"❌ Verification failed for {job_name}")


# -----------------------------
# MAIN
# -----------------------------
def setup_pipelines():

    print("\n🚀 JENKINS PIPELINE SETUP STARTED\n")

    session = get_session()

    pipelines = [
        {
            "name": "java-devops-pipeline",
            "repo": "https://github.com/yogithak25/end-to-end-devops-project.git"
        },
        {
            "name": "python-devops-pipeline",
            "repo": "https://github.com/yogithak25/python-devops-project.git"
        }
    ]

    for p in pipelines:
        ensure_pipeline(session, p["name"], p["repo"])
        verify_pipeline(session, p["name"])

    print("\n✅ Jenkins pipelines ensured\n")
