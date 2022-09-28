from typing import Optional
import hashlib

import mysql.connector.errors
from mysql import connector
from mysql.connector.errors import InterfaceError
from core import files, log

from cryptography.fernet import Fernet


def encode(text: str) -> str:
    return hashlib.sha256(text.lower().encode("utf-8")).hexdigest()


class Database:
    def __init__(self, config: files.Config):
        self.first_paypal_fetch = config.paypal().begin_date()
        self.config = config.database()
        self.con: Optional[mysql.connector.MySQLConnection] = None

        encryption_key = self.config.encryption_key()
        if encryption_key is None or len(encryption_key) == 0:
            encryption_key = Fernet.generate_key().decode(encoding="utf-8")
            self.config.set_encryption_key(encryption_key)
            config.save()

        self.encryption = Fernet(encryption_key.encode(encoding="utf-8"))

    async def build_connection(self) -> None:
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

    def encrypt(self, text: str) -> str:
        return self.encryption.encrypt(text.lower().encode("utf-8")).decode()

    def decrypt(self, text: str) -> str:
        return self.encryption.decrypt(text).decode()

    def __create_tables__(self) -> None:
        if self.con is None:
            return

        with self.con.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS `user_payments` ("
                           "resource MEDIUMINT(6) NOT NULL,"
                           "spigot_name VARCHAR(64) NOT NULL,"
                           "email VARCHAR(120) NOT NULL,"
                           "bought timestamp NOT NULL,"
                           "paid FLOAT(6, 2) NOT NULL,"
                           "tax FLOAT(6,2) NOT NULL,"
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

    def __update_setting__(self, key: str, value: str) -> None:
        if len(key) > 100:
            raise Exception("Key length must be <= 100")
        if len(value) > 100:
            raise Exception("Value length must be <= 100")

        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("INSERT INTO `settings` VALUES (%s, %s) ON DUPLICATE KEY UPDATE `value`=%s;",
                           [key, value, value])

    def __get_setting__(self, key: str, default: str) -> str:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("SELECT `value` FROM `settings` WHERE `key` = %s LIMIT 1;", [key])
            result = cursor.fetchone()
            return default if result is None else result[0]

    def add_payment(self, resource_id: int, spigot_name: str, email: str, bought_at: str, paid: float,
                    tax: float) -> None:
        with self.con.cursor(prepared=True) as cursor:
            encoded_spigot_name = encode(spigot_name)
            encoded_email = self.encrypt(email)

            try:
                cursor.execute("INSERT INTO `user_payments` VALUES (%s, %s, %s, %s, %s, %s);",
                               [resource_id, encoded_spigot_name, encoded_email, bought_at, paid, tax])
            except InterfaceError:
                pass

    def get_email(self, spigot_name: str) -> Optional[str]:
        with self.con.cursor(prepared=True) as cursor:
            encoded_spigot_name = encode(spigot_name)

            cursor.execute(
                "SELECT `email` FROM `user_payments` WHERE `spigot_name` = %s ORDER BY `bought` DESC LIMIT 1;",
                [encoded_spigot_name])
            result = cursor.fetchone()

            if result is None:
                return None

            encrypted_mail = result[0]
            return self.decrypt(encrypted_mail)

    def is_user_linked(self, user_id: int) -> bool:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("SELECT `spigot_name` FROM `user_links` WHERE `discord_id` = %s LIMIT 1;",
                           [user_id])
            result = cursor.fetchone()
            return result is not None

    def is_spigot_name_linked(self, spigot_name: str, do_hash: bool = True) -> bool:
        with self.con.cursor(prepared=True) as cursor:
            if do_hash:
                spigot_name = encode(spigot_name)

            cursor.execute("SELECT `discord_id` FROM `user_links` WHERE `spigot_name` LIKE %s LIMIT 1;",
                           [spigot_name])
            result = cursor.fetchone()
            return result is not None

    def invalidate_link(self, user_id: int) -> None:
        with self.con.cursor(prepared=True) as cursor:
            cursor.execute("DELETE FROM `user_links` WHERE `discord_id` = %s;",
                           [user_id])

    def link_user(self, user_id: int, encoded_spigot_name: str) -> None:
        with self.con.cursor(prepared=True) as cursor:
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
