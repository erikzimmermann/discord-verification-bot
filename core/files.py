import json
import os
from typing import Optional

import nextcord


def read_file(file: str) -> Optional[str]:
    if not os.path.exists(file):
        return None

    with open(file, encoding="utf8") as file:
        return "".join(file.readlines())


class File:
    def __init__(self, file_name, load: bool = True):
        self.file: dict = Optional[None]
        self.file_name = file_name

        if load:
            self.load()

    def load(self) -> None:
        path = f"{self.file_name}.json"

        if os.path.exists(path):
            with open(path, 'r') as f:
                self.file = json.load(f)
        else:
            self.file = {}

    def save(self) -> None:
        with open(f"{self.file_name}.json", 'w') as f:
            json.dump(self.file, f, indent=2)


class Wrapper:
    def __init__(self, file: dict, sub: str):
        self.file = file[sub]
        

class Discord(Wrapper):
    def __init__(self, file: dict):
        super().__init__(file, "discord")

    def token(self) -> str:
        return self.file["token"]

    def guild_id(self) -> int:
        return int(self.file["guild_id"])

    def activity(self) -> str:
        return self.file["activity"]

    def activity_type(self) -> int:
        return int(self.file["activity_type"])

    def get_activity(self) -> Optional[nextcord.Activity]:
        if self.activity_type() >= 0:
            return nextcord.Activity(type=self.activity_type(), name=self.activity())
        else:
            return None

    def premium_role(self) -> int:
        return self.file["premium_role"]

    def roles(self) -> dict:
        return self.file["functional_roles"]

    def resource_ids(self) -> list[int]:
        roles: dict = self.roles()
        rids = []
        for sId in roles.keys():
            rids.append(int(sId))
        return rids

    def resource_roles(self) -> list[int]:
        roles = []
        for sId in self.roles().values():
            roles.append(int(sId))
        return roles

    def role_by_rid(self, rid: int) -> int:
        return self.roles()[str(rid)]

    def rid_by_role(self, role_id: int) -> Optional[int]:
        roles = self.roles()

        for key in roles.keys():
            if roles[key] == role_id:
                return int(key)
        return None

    def promotion_message(self) -> str:
        return self.file["promotion_message"]

    def promotion_start_title(self) -> str:
        return self.file["promotion_start"]["title"]

    def promotion_start_content(self) -> str:
        return self.file["promotion_start"]["content"]


class EmailService(Wrapper):
    def __init__(self, file: dict):
        super().__init__(file, "email_service")

    def email(self) -> str:
        return self.file["email"]

    def password(self) -> str:
        return self.file["password"]

    def host(self) -> str:
        return self.file["host"]

    def port(self) -> int:
        port = self.file["port"]
        return 0 if port is None else int(port)

    def subject(self) -> str:
        return self.file["subject"]

    def sender_name(self) -> str:
        return self.file["sender_name"]
        

class PayPal(Wrapper):
    def __init__(self, file: dict):
        super().__init__(file, "paypal")

    def client_id(self) -> str:
        return self.file["client_id"]

    def secret(self) -> str:
        return self.file["secret"]

    def begin_date(self) -> str:
        return self.file["begin_date"]
        

class Database(Wrapper):
    def __init__(self, file: dict):
        super().__init__(file, "database")

    def database(self) -> str:
        return self.file["database"]

    def user(self) -> str:
        return self.file["user"]

    def password(self) -> str:
        return self.file["password"]

    def host(self) -> str:
        return self.file["host"]

    def port(self) -> int:
        return int(self.file["port"])


class SpigotMc(Wrapper):
    def __init__(self, file: dict):
        super().__init__(file, "spigotmc")

    def recipient(self) -> str:
        return self.file["recipient"]

    def topic(self) -> str:
        return self.file["topic"]


class Config(File):
    def __init__(self):
        super(Config, self).__init__("config")
        
    def discord(self) -> Discord:
        return Discord(self.file)
        
    def email_service(self) -> EmailService:
        return EmailService(self.file)
        
    def paypal(self) -> PayPal:
        return PayPal(self.file)
        
    def database(self) -> Database:
        return Database(self.file)

    def spigotmc(self) -> SpigotMc:
        return SpigotMc(self.file)
