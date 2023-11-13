import datetime
import logging
from typing import Dict, List, Tuple, Optional

import requests

from core import log
from core.service import database, paypal


class ApiReader:
    def __init__(self, db: database.MySQL, secret: str, custom_field: str, payment_links: Dict,
                 url: str = "https://api.stripe.com"):
        self.db = db
        self.secret = secret
        self.custom_field = custom_field
        self.payment_links = payment_links
        self.payment_links_wrapper = None
        self.url = url

    def update(self, silent: bool = False) -> None:
        if not silent:
            log.info(f"Fetching Stripe transaction data")

        last_id = self.db.get_last_stripe_fetch()
        for checkout in self.__fetch_all_checkouts(last_id):
            self.add_checkout(checkout)
            last_id = checkout["id"]

        if last_id:
            self.db.set_last_stripe_fetch(last_id)

    def __fetch_payment_links(self) -> None:
        if self.payment_links_wrapper is not None:
            return

        request_headers: dict = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.secret}"
        }

        request_data: dict = {
            "limit": 100
        }

        r: requests.Response = requests.get(
            url=self.url + "/v1/payment_links",
            headers=request_headers,
            data=request_data
        )

        res = r.json()

        if "data" in res:
            if res["has_more"]:
                logging.warning("Could not fetch all payment links (limit=100)!")

            self.payment_links_wrapper = {}
            for item in res["data"]:
                if item["url"] in self.payment_links:
                    self.payment_links_wrapper[item["id"]] = self.payment_links[item["url"]]
        elif "error" in res:
            logging.warning(
                "Could not fetch payment links. " + res["error"]["message"] + " " + res["error"]["request_log_url"])

    def add_checkout(self, checkout: Dict) -> None:
        # ensure payment links are available
        self.__fetch_payment_links()

        spigot = None
        for cf in checkout["custom_fields"]:
            if cf["key"] == self.custom_field:
                spigot = cf["text"]["value"]

        if checkout["payment_link"] not in self.payment_links_wrapper:
            return

        resource_id = self.payment_links_wrapper[checkout["payment_link"]]
        created = datetime.datetime.fromtimestamp(checkout["created"])
        paid = checkout["payment_intent"]["amount"] / 100.0

        # negate to fit paypal data
        tax = -checkout["payment_intent"]["latest_charge"]["balance_transaction"]["fee"] / 100.0

        if spigot and resource_id and created and paid and tax:
            self.db.add_payment(resource_id, spigot, paypal.time_to_string__(created), paid, tax, "stripe")

    def __fetch_all_checkouts(self, last_id_fetched: str) -> List:
        items, next_page = self.__fetch_completed_checkouts(last_id_fetched)

        while next_page is not None:
            more_items, next_page = self.__fetch_completed_checkouts(next_page)
            items.extend(more_items)

        return items

    def __fetch_completed_checkouts(self, starting_after: Optional[str] = None) -> Tuple[List, Optional[str]]:
        request_headers: dict = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.secret}"
        }

        request_data: dict = {
            "limit": 50,
            "starting_after": starting_after,
            "expand[]": "data.payment_intent.latest_charge.balance_transaction",
        }

        r: requests.Response = requests.get(
            url=self.url + "/v1/checkout/sessions",
            headers=request_headers,
            data=request_data
        )

        res = r.json()
        if "data" in res:
            items = res["data"]
            return ([item for item in items if "status" in item and item["status"] == "complete"],
                    items[-1]["id"] if res["has_more"] else None)
        elif "error" in res:
            logging.warning(
                "Could not fetch checkouts. " + res["error"]["message"] + " " + res["error"]["request_log_url"])

        return [], None
