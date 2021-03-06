import configparser
import requests
import json
import traceback

from enum import Enum
from flask import Flask, jsonify
from util import filesize

config = configparser.ConfigParser()
config.read('config.ini')
paths = config['paths']
keys = config['keys']

app = Flask(__name__)
deluge_session = None


class Status(Enum):
    ACTIVE = "success"
    IDLE = "info"
    WARN = "warning"
    ERROR = "danger"
    UNKNOWN = "default"


def check_nzbget():
    """
    Connects to an instance of NZBGet and returns a tuple containing the instances status.

    Returns:
        (str) an instance of the Status enum value representing the status of the service
        (str) a short descriptive string representing the status of the service
    """
    try:
        req = requests.get('{}/jsonrpc/status'.format(paths['NZBGet']), timeout=0.2)
        req.raise_for_status()
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
        return Status.ERROR.value, "NoAPI"

    try:
        data = req.json()
    except ValueError:
        return Status.ERROR.value, "BadJSON"

    if data['result']['DownloadPaused']:
        return Status.WARN.value, "Paused"
    elif data['result']['ServerStandBy']:
        return Status.IDLE.value, "Idle"
    else:
        rate = filesize.size(data['result']['DownloadRate'], system=filesize.iec)
        return Status.ACTIVE.value, "{}B/s".format(rate)


def check_sonarr():
    """
    Connects to an instance of Sonarr and returns a tuple containing the instances status.
    
    Returns:
        (str) an instance of the Status enum value representing the status of the service
        (str) a short descriptive string representing the status of the service
    """
    try:
        req = requests.get('{}/api/system/status?apikey={}'.format(paths['Sonarr'], keys['Sonarr']), timeout=0.2)
        req.raise_for_status()
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
        return Status.ERROR.value, "NoAPI"

    try:
        data = req.json()
    except ValueError:
        return Status.ERROR.value, "BadJSON"

    if data['version']:
        return Status.ACTIVE.value, "Online"
    else:
        return Status.ERROR.value, "BadAPI"


def check_radarr():
    """
    Connects to an instance of Radarr and returns a tuple containing the instances status.

    Returns:
        (str) an instance of the Status enum value representing the status of the service
        (str) a short descriptive string representing the status of the service
    """
    try:
        req = requests.get('{}/api/system/status?apikey={}'.format(paths['Radarr'], keys['Radarr']), timeout=0.2)
        req.raise_for_status()
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
        return Status.ERROR.value, "NoAPI"

    try:
        data = req.json()
    except ValueError:
        return Status.ERROR.value, "BadJSON"

    if data['version']:
        return Status.ACTIVE.value, "Online"
    else:
        return Status.ERROR.value, "BadAPI"


def check_deluge():
    """
    Connects to an instance of Deluge and returns a tuple containing the instances status.

    Returns:
        (str) an instance of the Status enum value representing the status of the service
        (str) a short descriptive string representing the status of the service
    """
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    #global deluge_session
    #if not deluge_session:
    try:
        deluge_session = requests.Session()

        login_args = {
            "method": "auth.login",
            "params": [keys['deluge']],
            "id": 2
        }

        login = deluge_session.post("{}/json".format(paths['Deluge']), data=json.dumps(login_args),
                             timeout=0.5, headers=headers)

        login.raise_for_status()
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout) as ex:
        traceback.print_exc()
        return Status.ERROR.value, "NoAPILogin"

    try:
        query_args = {
            "method": "web.update_ui",
            "params": [['queue'], {}],
            "id": 3
        }
        query = deluge_session.post("{}/json".format(paths['Deluge']), data=json.dumps(query_args), timeout=0.5, headers=headers)

        query.raise_for_status()
    except (requests.ConnectionError, requests.HTTPError, requests.Timeout) as ex:
        traceback.print_exc()
        return Status.ERROR.value, "NoAPI"

    try:
        data = query.json()
        print(data)
    except ValueError:
        return Status.ERROR.value, "BadJSON"



    if data.get('result', False).get('stats', False):
        if data.get('result', False).get('stats', False).get('download_rate', 0) > 0:
            rate = filesize.size(data['result']['stats']['download_rate'], system=filesize.iec)
            return Status.ACTIVE.value, "{}B/s".format(rate)
        elif data.get('result', False).get('stats', False).get('upload_rate', 0) > 0:
            return Status.IDLE.value, "Seeding"
        else:
            return Status.IDLE.value, "Idle"
    else:
        return Status.ERROR.value, "BadAPI"


@app.route("/status")
def status():
    """
    Handles HTTP GET requests for the /status API endpoint.
    Describes the status of the services this script monitors.
     
    Returns:
        A JSON response
    """
    data = {
        'nzbget': check_nzbget(),
        'deluge': check_deluge(),
        'sonarr': check_sonarr(),
        'radarr': check_radarr()
    }

    return jsonify(data)


# let's run this thing!
if __name__ == "__main__":
    app.run(port=80)
