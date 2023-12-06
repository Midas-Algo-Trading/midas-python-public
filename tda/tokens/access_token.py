import time
from datetime import timedelta
from typing import Optional

from files.config import Config
import schedule
from logger import log
from utils import r_util, t_util


class AccessToken:
    refresh_token: str

    def __init__(self, refresh_token: str, tda_account_id: int, access_token: Optional[str] = None, expire_time: Optional[int] = None):
        self.refresh_token = refresh_token
        self.tda_account_id = tda_account_id

        if access_token and expire_time:
            self.token = access_token
            self.expire_time = expire_time
            self.__schedule_refresh()
        else:
            self.refresh()

    def refresh(self):
        """Get a new refresh_token."""
        response = r_util.send_request('POST',
                                       'https://api.tdameritrade.com/v1/oauth2/token',
                                       False,
                                       data={
                                           'grant_type': 'refresh_token',
                                           'refresh_token': self.refresh_token,
                                           'client_id': Config.get(f'tda{self.tda_account_id}.consumer_key')
                                       }).json()
        log('tda/access_token', f'Refresh response for {self.tda_account_id}: {response}')
        self.token = response['access_token']
        self.expire_time = int(time.time()) + response['expires_in']
        self.__schedule_refresh()

    def __schedule_refresh(self):
        schedule.add(max((t_util.get_current_datetime() + timedelta(minutes=30)),
                         schedule.get_next_strategy_run_time() - timedelta(minutes=1)), self.refresh)

    @property
    def is_expired(self) -> bool:
        return (self.expire_time - int(time.time())) < 60
