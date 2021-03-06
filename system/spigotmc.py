import base64
import hashlib
import hmac
import logging
import struct
import time

import undetected_chromedriver.v2 as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def get_hotp_token(secret: str, intervals_no: int) -> hmac.HMAC:
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", intervals_no)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = ord(chr(h[19])) & 15
    h = (struct.unpack(">I", h[o:o + 4])[0] & 0x7fffffff) % 1000000
    return h


def get_totp_token(secret: str) -> hmac.HMAC:
    return get_hotp_token(secret, intervals_no=int(time.time()) // 30)


class Credentials:
    def __init__(self, user: str, password: str, two_factor_secret: str, resource: str, title: str, content: str, google_chrome_location: str):
        self.user = user
        self.password = password
        self.two_factor_secret = two_factor_secret
        self.resource = resource
        self.title = title
        self.content = content
        self.google_chrome_location = google_chrome_location


class ForumAPI:
    def __init__(self, credentials: Credentials, chrome_location: str, logger: logging, debugging: bool = True):
        self.credentials = credentials
        self.debugging = debugging
        self.logger = logger
        self.logged_in = False

        options = uc.ChromeOptions()
        options.binary_location = chrome_location

        self.driver = uc.Chrome(options=options)

    def debug(self, message: str) -> None:
        if self.debugging:
            self.logger.info("ForumAPI > " + message)

    def __login__(self) -> None:
        self.debug("logging in")

        input_element_username = self.driver.find_element(by=By.ID, value="ctrl_pageLogin_login")
        ActionChains(self.driver) \
            .move_to_element(input_element_username) \
            .click(input_element_username) \
            .send_keys(self.credentials.user) \
            .send_keys(Keys.TAB) \
            .send_keys(Keys.CONTROL + "a") \
            .send_keys(Keys.BACKSPACE) \
            .send_keys(self.credentials.password) \
            .send_keys(Keys.ENTER) \
            .perform()

        self.debug("calculating two-factor-authentication-code")
        self.driver.implicitly_wait(10)

        # search for element before getting the code
        input_element_totp = self.driver.find_element(by=By.ID, value="ctrl_totp_code")

        ActionChains(self.driver) \
            .move_to_element(input_element_totp) \
            .click(input_element_totp) \
            .perform()

        tfa_factor = str(get_totp_token(self.credentials.two_factor_secret))
        self.debug("entering two-factor-authentication-code: " + tfa_factor)

        ActionChains(self.driver) \
            .send_keys(tfa_factor) \
            .send_keys(Keys.ENTER) \
            .perform()

        self.driver.implicitly_wait(10)
        self.logged_in = True

    def is_user_premium(self, user: str) -> bool:
        self.debug("loading buyers list")

        with self.driver:
            self.driver.get("https://www.spigotmc.org/resources/" + self.credentials.resource + "/buyers/find")

        self.driver.implicitly_wait(10)

        if not self.logged_in:
            self.__login__()

        self.debug("finding user: " + user)
        input_element_search = self.driver.find_element(by=By.NAME, value="username")
        ActionChains(self.driver) \
            .move_to_element(input_element_search) \
            .click(input_element_search) \
            .send_keys(user) \
            .send_keys(Keys.ENTER) \
            .perform()

        self.driver.implicitly_wait(10)

        results = len(self.driver.find_elements(by=By.CLASS_NAME, value="memberListItem"))

        # check if only one member remains --> is premium (assumes a resource with more than 1 purchases)
        return results == 1

    def send_message(self, recipient: str, title: str, message: str) -> None:
        self.debug("loading conversation")

        with self.driver:
            self.driver.get("https://www.spigotmc.org/conversations/add?to=" + recipient + "&title=" + title)

        if not self.logged_in:
            self.__login__()

        self.debug("sending message " + message)

        input_element_change_to_plain = self.driver.find_element(by=By.CSS_SELECTOR, value=".redactor_btn_group.redactor_btn_right > ul > li > a")
        ActionChains(self.driver) \
            .move_to_element(input_element_change_to_plain) \
            .click(input_element_change_to_plain) \
            .send_keys(message) \
            .send_keys(Keys.TAB) \
            .send_keys(Keys.TAB) \
            .send_keys(Keys.ENTER) \
            .perform()

        self.driver.implicitly_wait(5)

    def close(self) -> None:
        self.driver.close()
