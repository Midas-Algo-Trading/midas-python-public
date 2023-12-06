from typing import Optional

from twilio.rest import Client

from color import color
from files.config import Config
from logger import dlog
from utils import cli_util


@dlog('alert', 'sending text sms')
def send_sms(msg: Optional[str] = 'testing...'):
    # Hook into Twilio client
    client = Client(Config.get('twilio.account_sid'), Config.get('twilio.auth_token'))

    # Create and send the text
    client.messages.create(
        body=msg,
        from_=Config.get('twilio.from'),
        to=Config.get('twilio.to0')
    )

    client.messages.create(
        body=msg,
        from_=Config.get('twilio.from'),
        to=Config.get('twilio.to1')
    )


@dlog('alert', 'alerting error message @0')
def alert(error_msg: str):
    """
    Sends an error text with the strategy_name and order_id.

    Parameters
    ----------
    error_msg : String
        The error message to be printed

    Notes
    -----
    Change the phone number in the config to ensure texts are being sent to the right phone number.

    """
    cli_util.output(color.FAIL + error_msg)
    if Config.get('text_alerts'):
        send_sms(error_msg.split('\n')[-1])

