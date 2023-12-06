from typing import Dict, Iterable

from files.config import Config
from tda import tda_client
from tda.tda_client import access_tda_account
from utils import r_util


@access_tda_account
def get_market_prices(symbols: Iterable[str], tda_account_id: int) -> Dict[str, float]:
    quotes = r_util.send_request(
            'GET',
            f'https://api.tdameritrade.com/v1/marketdata/quotes',
            False,
            headers={'Authorization': f'Bearer {tda_client.access_token[tda_account_id].token}'},
            params={'apiKey': f'Bearer {Config.get(f"tda{tda_account_id}.consumer_key")}', 'symbol': ','.join(symbols)}
        ).json()

    return {symbol: quotes[symbol]['lastPrice'] for symbol in symbols if symbol in quotes}
