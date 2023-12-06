from typing import List, Optional

from data.data_requests.data_request import DataRequest


class MarketSnapshotRequest(DataRequest):
    """
    Requests a MarketSnapshot from Polygon.io

    Methods
    -------
    __eq__ : Any
        Returns 'True' if the object is a MarketSnapshotRequest
    merge_with : MarketSnapshotRequest
        Combines two MarketSnapshotRequests.
        It does this by creating a new MarketSnapshotRequest whose dates encompass the dates of the two original
        MarketSnapShotRequests.

    Notes
    -----
    Even though the class is called 'MarketSnapShotRequest', it actually will request 'grouped_daily_aggs' data from
    Polygon.io.

    """
    def __init__(self, columns: List[str],
                 day: int = 0,
                 shortable: bool = False,
                 min_rel_mkt_cap: Optional[int] = None,
                 round_to: int = 3):
        self.day = day
        self.shortable = shortable
        self.min_rel_mkt_cap = min_rel_mkt_cap
        super().__init__(columns, round_to)

    def can_merge_with(self, data_request: DataRequest) -> bool:
        return isinstance(data_request, MarketSnapshotRequest) and self.day == data_request.day and self.shortable == data_request.shortable and self.min_rel_mkt_cap == data_request.min_rel_mkt_cap

    def __add__(self, other):
        self.columns = list(set(self.columns + other.columns))
        return self

    def __eq__(self, other):
        return isinstance(other, MarketSnapshotRequest) and self.day == other.day and self.shortable == other.shortable and self.columns == other.columns

    def __hash__(self):
        return hash(str(self))
