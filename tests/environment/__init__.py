import os
import base64
import subprocess
import time
import json
import atexit
import pytest
import requests
thisdir = os.path.abspath(os.path.dirname(__file__))

# os.environ["BUILDKIT_PROGRESS"] = "plain"


USERNAMES = ["admin", "privileged", "unprivileged"]
global users
users = None

def create_env():
    global users
    if users is not None:
        return users
    users = {}
    for username in USERNAMES:
        password = base64.b64encode(os.urandom(24)).decode()
        users[username] = password
    with open(os.path.join(thisdir, "scripts", "meshcentral", "users.json"), "w") as outfile:
        json.dump(users, outfile)
    return users

global _docker_process
_docker_process = None

class Agent(object):
    def __init__(self, meshid, mcurl, clienturl, dockerurl):
        self.meshid = meshid
        self._mcurl = mcurl
        self._clienturl = clienturl
        self._dockerurl = dockerurl
        r = requests.post(f"{self._clienturl}/add-agent", json={"url": f"{self._dockerurl}", "meshid": self.meshid})
        self.nodeid = r.json()["id"]

    def __enter__(self):
        return self

    def __exit__(self, exc_t, exc_v, exc_tb):
        try:
            requests.post("{self._clienturl}/remove-agent/{self.nodeid}")
        except:
            pass

class TestEnvironment(object):
    def __init__(self):
        self.users = create_env()
        self._subp = None
        self.mcurl = "wss://localhost:8086"
        self.clienturl = "http://localhost:5000"
        self._dockerurl = "host.docker.internal:8086"

    def __enter__(self):
        global _docker_process
        if _docker_process is not None:
            self._subp = _docker_process
            return self
        self._subp = _docker_process = subprocess.Popen(["docker", "compose", "up", "--build", "--force-recreate", "--no-deps"], stdout=subprocess.DEVNULL, cwd=thisdir)
        timeout = 30
        start = time.time()
        while time.time() - start < timeout:
            try:
                data = subprocess.check_output(["docker", "inspect", "meshctrl-meshcentral", "--format='{{json .State.Health}}'"], cwd=thisdir, stderr=subprocess.DEVNULL)
                # docker outputs for humans, not computers. This is the easiest way to chop off the ends
                data = json.loads(data.strip()[1:-1])
            except Exception as e:
                time.sleep(1)
                continue
            try:
                if data["Status"] == "healthy":
                    break
            except:
                pass
            time.sleep(1)
        else:
            self.__exit__(None, None, None)
            raise Exception("Failed to create docker instance")
        return self


    def __exit__(self, exc_t, exc_v, exc_tb):
        pass

    def create_agent(self, meshid):
        return Agent(meshid, self.mcurl, self.clienturl, self._dockerurl)

def _kill_docker_process():
    if _docker_process is not None:
        _docker_process.kill()
        subprocess.run(["docker", "compose", "down"], cwd=thisdir)

atexit.register(_kill_docker_process)

@pytest.fixture(scope="session")
def env():
    with TestEnvironment() as e:
        yield e


if __name__ == "__main__":
    with TestEnvironment() as env:
        input("it's up")