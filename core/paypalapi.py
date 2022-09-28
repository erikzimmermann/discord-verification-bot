from datetime import datetime, timedelta
from typing import Optional

import requests

from core import database, log

time_format = "%Y-%m-%dT%H:%M:%SZ"


def __time_to_string__(date: datetime) -> str:
    return datetime.strftime(date, time_format)


def __string_to_time__(date: str) -> datetime:
    return datetime.strptime(date, time_format)


def __count_days__(date_start: str, date_end: str) -> int:
    t_start: datetime = __string_to_time__(date_start)
    t_end: datetime = __string_to_time__(date_end)
    return abs(t_end - t_start).days


def __ensure_date_limit__(date_start: str, date_end: str, callback) -> None:
    datetime_start = __string_to_time__(date_start)
    datetime_end = __string_to_time__(date_end)

    while (datetime_end - datetime_start).days > 31:
        datetime_next = datetime_start + timedelta(days=31)
        callback(__time_to_string__(datetime_start), __time_to_string__(datetime_next))
        datetime_start = datetime_next

    callback(__time_to_string__(datetime_start), date_end)


def access_dict(d: dict, *args) -> Optional[str]:
    for key in args[:-1]:
        if key in d:
            value = d[key]
            if isinstance(value, list):
                value = value[0]

            if isinstance(value, dict):
                d = value
            else:
                raise Exception("Unknown value access. Type: ", type(value))
        else:
            return None

    if args[-1] in d:
        return d[args[-1]]
    else:
        return None


def get_data_from_payment(transaction: dict) -> Optional[tuple[int, str, str, str, float, float]]:
    rid = __get_resource_id__(transaction)
    spigot_name = __get_spigot_name__(transaction)
    email = __get_email__(transaction)
    bought_at = __get_bought_at__(transaction)
    paid = __get_paid__(transaction)
    tax = __get_tax__(transaction)

    if rid is None \
            or spigot_name is None \
            or email is None \
            or bought_at is None \
            or paid is None \
            or tax is None:
        return None

    return rid, spigot_name, email, bought_at, paid, tax


def __get_resource_id__(transaction: dict) -> Optional[int]:
    custom_field = access_dict(transaction, "transaction_info", "custom_field")
    if custom_field is None:
        return None

    idx = custom_field.rfind("|")
    return int(custom_field[idx + 1:])


def __get_spigot_name__(transaction: dict) -> Optional[str]:
    item_name = access_dict(transaction, "cart_info", "item_details", "item_name")
    if item_name is None \
            or not item_name.endswith(")"):
        return None

    idx: int = item_name.rfind("(")
    if idx + 1 >= len(item_name):
        return None

    return item_name[idx + 1:-1]


def __get_email__(transaction: dict) -> Optional[str]:
    return access_dict(transaction, "payer_info", "email_address")


def __get_bought_at__(transaction: dict) -> Optional[str]:
    return access_dict(transaction, "transaction_info", "transaction_initiation_date")


def __get_paid__(transaction: dict) -> Optional[float]:
    paid = access_dict(transaction, "cart_info", "item_details", "total_item_amount", "value")
    return 0 if paid is None else float(paid)


def __get_tax__(transaction: dict) -> Optional[float]:
    tax = access_dict(transaction, "transaction_info", "fee_amount", "value")
    return 0 if tax is None else float(tax)


class ApiReader:
    def __init__(self, db: database.Database, client_id: str, secret: str, url: str = "https://api-m.paypal.com"):
        self.db = db
        self.client_id = client_id
        self.secret = secret
        self.url = url
        self.access_token = None

    def fetch_access_token(self) -> None:
        self.access_token = self.__fetch_access_token__()

        if self.access_token is None:
            log.error("Could not fetch PayPal access token! Please check your credentials.")

    def update_transaction_data(self, silent: bool = False) -> None:
        if self.access_token is None:
            return

        now = __time_to_string__(datetime.now())
        __ensure_date_limit__(
            self.db.get_last_paypal_fetch(),
            now,
            lambda start, end: self.__save_payments__(start, end, silent=silent)
        )
        self.db.set_last_paypal_fetch(now)

    def __save_payments__(self, date_start: str, date_end: str, silent: bool = False) -> None:
        for transaction in self.__fetch_transactions__(date_start, date_end, silent=silent):
            data = get_data_from_payment(transaction)
            if data is None:
                continue

            rid, spigot_name, email, bought_at, paid, tax = data
            self.db.add_payment(rid, spigot_name, email, bought_at, paid, tax)

    def __fetch_transactions__(self, date_start: str, date_end: str, silent: bool = False) -> list[dict]:
        if self.access_token is None:
            raise Exception("Cannot fetch transactions without PayPal access token!")

        headers: dict = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }

        params: dict = {
            "start_date": date_start,
            "end_date": date_end,
            "fields": "all",
            "page_size": 500,
            "page": 1
        }

        if not silent:
            log.info(f"Fetching transaction data in range {date_start} to {date_end}")
        r: requests.Response = requests.get(url=self.url + "/v1/reporting/transactions", params=params, headers=headers)

        data: dict = r.json()
        if "transaction_details" in data:
            transactions: list[dict] = data["transaction_details"]
            return transactions
        else:
            return []

    def __fetch_access_token__(self) -> Optional[str]:
        if self.client_id is None or len(self.client_id) == 0 or \
                self.secret is None or len(self.secret) == 0:
            return None

        headers: dict = {
            "Accept": "application/json",
            "Accept-Language": "en_US"
        }

        data: dict = {
            'grant_type': 'client_credentials'
        }

        log.info("Fetching PayPal access token...")
        r: requests.Response = requests.post(
            url=self.url + "/v1/oauth2/token",
            headers=headers,
            data=data,
            auth=(self.client_id, self.secret)
        )

        data: dict = r.json()

        return access_dict(data, "access_token")
