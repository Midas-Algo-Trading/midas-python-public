import time

import requests

from logger import log


def send_request(method, url, accept_bad_response: bool, **kwargs):
    attempts = 0
    while attempts < 11:
        request = requests.Request(method, url, **kwargs).prepare()
        try:
            response = requests.Session().send(request)
        except:
            attempts += 1
            time.sleep(attempts**2)
            continue
        if accept_bad_response or response.status_code == 200 or response.status_code == 201:
            return response
        else:
            attempts += 1
            log("r_util", f'Bad Response: ({response.text})')
            time.sleep(attempts**2)
    raise Exception("Account could not connect.")
