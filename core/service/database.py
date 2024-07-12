import datetime
from typing import Optional, Literal

import mysql.connector.errors
from mysql import connector
from mysql.connector.errors import InterfaceError

from core import files, log, magic


class MySQL:
    def __init__(self, config: files.Config):
        self.first_paypal_fetch = config.paypal().begin_date()
        self.config = config.database()
        self.con: Optional[mysql.connector.MySQLConnection] = None

    def build_connection(self) -> None:
        log.info("Connecting to mysql database...")

        password = self.config.password()
        if password is not None and len(password) == 0:
            password = None

        try:
            self.con = connector.connect(
                host=self.config.host(),
                port=self.config.port(),
                user=self.config.user(),
                password=password,
                database=self.config.database(),
                autocommit=True
            )

            self.__create_tables__()
        except mysql.connector.errors.ProgrammingError:
            log.error("Could not connect to your mysql database. Please check your credentials!")

    def has_valid_con(self):
        return self.con is not None and self.con.is_connected()

    def __create_tables__(self) -> None:
        if self.con is None:
            return

        with self.con.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS `user_payments` ("
                           "resource MEDIUMINT(6) NOT NULL,"
                           "spigot_name VARCHAR(64) NOT NULL,"
                           "bought_at timestamp NOT NULL,"
                           "paid FLOAT(6, 2) NOT NULL,"
                           "tax FLOAT(6,2) NOT NULL,"
                           "service VARCHAR(30) NOT NULL,"
                           "PRIMARY KEY (resource, spigot_name),"
                           "UNIQUE (resource, spigot_name)"
                           ");")

            cursor.execute("CREATE TABLE IF NOT EXISTS `user_links` ("
                           "discord_id BIGINT(18) NOT NULL PRIMARY KEY UNIQUE,"
                           "spigot_name VARCHAR(64) NOT NULL UNIQUE,"
                           "linked_at timestamp NOT NULL DEFAULT now()"
                           ");")

            cursor.execute("CREATE TABLE IF NOT EXISTS `settings` ("
                           "`key` VARCHAR(100) NOT NULL PRIMARY KEY UNIQUE,"
                           "`value` VARCHAR(100) NOT NULL"
                           ");")

    def get_last_paypal_fetch(self) -> str:
        return self.__get_setting__("last_paypal_fetch", self.first_paypal_fetch)

    def set_last_paypal_fetch(self, date) -> None:
        self.__update_setting__("last_paypal_fetch", date)

    def get_last_stripe_fetch(self) -> str:
        return self.__get_setting__("last_stripe_fetch", None)

    def set_last_stripe_fetch(self, checkout_id: str) -> None:
        self.__update_setting__("last_stripe_fetch", checkout_id)

    def __update_setting__(self, key: str, value: str) -> None:
        if len(key) > 100:
            raise Exception("Key length must be <= 100")
        if len(value) > 100:
            raise Exception("Value length must be <= 100")

        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("INSERT INTO `settings` VALUES (%s, %s) ON DUPLICATE KEY UPDATE `value`=%s;",
                           [key, value, value])

    def __get_setting__(self, key: str, default: Optional[str]) -> Optional[str]:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("SELECT `value` FROM `settings` WHERE `key` = %s LIMIT 1;", [key])
            result = cursor.fetchone()
            return default if result is None else result[0]

    def get_latest_paypal_transaction_date(self) -> datetime.datetime:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("SELECT MAX(`bought_at`) FROM `user_payments`;", [])
            result = cursor.fetchone()
            return self.first_paypal_fetch if result is None else result[0]

    def add_payment(self, resource_id: int, spigot_name: str, bought_at: datetime.datetime, paid: float, tax: float,
                    service: Literal["paypal", "stripe"]) -> None:
        with self.con.cursor(prepared=True) as cursor:
            encoded_spigot_name = magic.encode(spigot_name)

            try:
                cursor.execute("INSERT INTO `user_payments` VALUES (%s, %s, %s, %s, %s, %s);",
                               [resource_id, encoded_spigot_name, bought_at, paid, tax, service])
            except Exception as e:
                print(e)

    def is_user_linked(self, user_id: int) -> bool:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("SELECT `spigot_name` FROM `user_links` WHERE `discord_id` = %s LIMIT 1;",
                           [user_id])
            result = cursor.fetchone()
            return result is not None

    def is_spigot_name_linked(self, spigot_name: str, do_hash: bool = True) -> bool:
        with self.con.cursor(prepared=True) as cursor:
            if do_hash:
                spigot_name = magic.encode(spigot_name)

            cursor.execute("SELECT `discord_id` FROM `user_links` WHERE `spigot_name` LIKE %s LIMIT 1;",
                           [spigot_name])
            result = cursor.fetchone()
            return result is not None

    def invalidate_link(self, user_id: int) -> None:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("DELETE FROM `user_links` WHERE `discord_id` = %s;",
                           [user_id])

    def link_user(self, user_id: int, spigot_name: str) -> None:
        with self.con.cursor(prepared=True) as cursor:
            encoded_spigot_name = magic.encode(spigot_name)
            try:
                cursor.execute("INSERT INTO `user_links` (`discord_id`, `spigot_name`) VALUES (%s, %s);",
                               [user_id, encoded_spigot_name])
            except InterfaceError:
                pass

    def get_bought_rids(self, user_id: int) -> list[int]:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("SELECT `resource` FROM `user_payments` up "
                           "INNER JOIN `user_links` ul ON up.spigot_name = ul.spigot_name "
                           "WHERE ul.discord_id = %s;",
                           [user_id])
            result = cursor.fetchall()

            rids = []
            for r in result:
                rids.append(r[0])
            return rids

    def is_premium_user(self, spigot_name: str) -> bool:
        with self.con.cursor(prepared=True) as cursor:
            encoded_spigot_name = magic.encode(spigot_name)

            cursor.execute("SELECT 1 FROM `user_payments` WHERE `spigot_name` LIKE %s LIMIT 1;",
                           [encoded_spigot_name])
            result = cursor.fetchone()
            return result is not None
