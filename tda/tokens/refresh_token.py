import time
from datetime import datetime, timedelta
from pytz import timezone
from typing import Optional

import schedule
from files.config import Config
from logger import log
from utils import r_util
from tda.tokens.access_token import AccessToken


class RefreshToken:
    access_token: AccessToken

    def __init__(self, refresh_token: str, tda_account_id: int, expire_time: Optional[int] = None):
        self.token = refresh_token
        self.tda_account_id = tda_account_id
        if expire_time:
            self.expire_time = expire_time
            self.__schedule_refresh()
        else:
            self.__refresh()

    def __refresh(self):
        response = r_util.send_request('POST',
                                       'https://api.tdameritrade.com/v1/oauth2/token',
                                       False,
                                       data={
                                           'grant_type': 'refresh_token',
                                           'refresh_token': self.token,
                                           'access_type': 'offline',
                                           'client_id': Config.get(f'tda{self.tda_account_id}.consumer_key')
                                       }).json()
        log('tda/refresh_token', f'Refresh response {self.tda_account_id}: {response}')
        self.token = response['refresh_token']
        self.expire_time = int(time.time()) + response['refresh_token_expires_in']
        self.access_token = AccessToken(self.token, self.tda_account_id, response['access_token'], int(time.time()) + response['expires_in'])
        self.__schedule_refresh()

    def __schedule_refresh(self):
        schedule.add(datetime.fromtimestamp(self.expire_time, timezone('US/Eastern')) - timedelta(days=1), self.__refresh)
