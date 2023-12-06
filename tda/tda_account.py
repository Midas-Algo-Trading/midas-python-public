from logger import log
from utils import r_util


class tdaAccount:
    id: int
    buying_power_non_marginableTrade: float
    buying_power: float
    maintenance_requirement: float
    reg_t_call: float
    accrued_interest: float
    day_trading_buying_power: float
    day_trades_left: int
    available_funds_non_marginable_trade: float

    def __init__(self, access_token: str, account_id: int):
        self.access_token = access_token
        self.account_id = account_id
        self.refresh(self.access_token)

    def refresh(self, access_token: str):
        response = r_util.send_request(method="GET", url=f'https://api.tdameritrade.com/v1/accounts/{self.account_id}',
                                       accept_bad_response=False,
                                       params={'fields': 'positions'},
                                       headers={'Authorization': f'Bearer {access_token}'})
        log('tda/account', f'Refresh response {response.status_code}: {response}')
        response = response.json()
        self.id = response['securitiesAccount']['accountId']
        self.day_trades_left = 3 - response['securitiesAccount']['roundTrips']
        current_balances = response['securitiesAccount']['currentBalances']
        self.buying_power_non_marginableTrade = current_balances['buyingPowerNonMarginableTrade']
        self.buying_power = current_balances['buyingPower']
        self.maintenance_requirement = current_balances['maintenanceRequirement']
        self.reg_t_call = current_balances['regTCall']
        self.accrued_interest = current_balances['accruedInterest']
        self.day_trading_buying_power = current_balances['dayTradingBuyingPower']
        self.available_funds_non_marginable_trade = current_balances['availableFundsNonMarginableTrade']