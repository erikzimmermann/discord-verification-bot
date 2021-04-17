import pyotp
import undetected_chromedriver.v2 as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class Credentials:
    def __init__(self, user, password, two_factor_secret, resource, title, content, google_chrome_location):
        self.user = user
        self.password = password
        self.two_factor_secret = two_factor_secret
        self.resource = resource
        self.title = title
        self.content = content
        self.google_chrome_location = google_chrome_location


class ForumAPI:
    def __init__(self, credentials, chrome_location, logger, debugging=True):
        self.credentials = credentials
        self.debugging = debugging
        self.logger = logger
        self.logged_in = False

        options = uc.ChromeOptions()
        options.binary_location = chrome_location

        self.driver = uc.Chrome(options=options)

    def debug(self, message):
        if self.debugging:
            self.logger.info("ForumAPI > " + message)

    def __login__(self):
        self.debug("logging in")

        self.driver.save_screenshot("screen_login_1.png")
        input_element_username = self.driver.find_element_by_id("ctrl_pageLogin_login")
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

        self.driver.save_screenshot("screen_login_2.png")
        self.driver.implicitly_wait(20)

        # search for element before getting the code
        input_element_totp = self.driver.find_element_by_id("ctrl_totp_code")
        self.driver.save_screenshot("screen_login_3.png")

        totp = pyotp.TOTP(self.credentials.two_factor_secret)
        tfa_factor = totp.now()
        self.debug("entering two-factor-authentication-code: " + tfa_factor)

        self.driver.save_screenshot("screen_login_4.png")
        ActionChains(self.driver) \
            .move_to_element(input_element_totp) \
            .click(input_element_totp) \
            .send_keys(tfa_factor) \
            .send_keys(Keys.ENTER) \
            .perform()

        self.driver.implicitly_wait(10)
        self.driver.save_screenshot("screen_login_5.png")
        self.logged_in = True

    def is_user_premium(self, user):
        self.debug("loading buyers list")

        with self.driver:
            self.driver.get("https://www.spigotmc.org/resources/" + self.credentials.resource + "/buyers/find")

        self.driver.save_screenshot("screen_premium_1.png")
        self.driver.implicitly_wait(10)

        if not self.logged_in:
            self.__login__()

        self.debug("finding user: " + user)
        input_element_search = self.driver.find_element_by_name("username")
        self.driver.save_screenshot("screen_premium_2.png")
        ActionChains(self.driver) \
            .move_to_element(input_element_search) \
            .click(input_element_search) \
            .send_keys(user) \
            .send_keys(Keys.ENTER) \
            .perform()

        self.driver.implicitly_wait(10)
        self.driver.save_screenshot("screen_premium_3.png")

        results = len(self.driver.find_elements_by_class_name("memberListItem"))

        # check if only one member remains --> is premium (assumes a resource with more than 1 purchases)
        return results == 1

    def send_message(self, recipient, title, message):
        self.debug("loading conversation")

        with self.driver:
            self.driver.get("https://www.spigotmc.org/conversations/add?to=" + recipient + "&title=" + title)

        if not self.logged_in:
            self.__login__()

        self.debug("sending message " + message)

        input_element_change_to_plain = self.driver.find_element_by_css_selector(".redactor_btn_group.redactor_btn_right > ul > li > a")
        ActionChains(self.driver) \
            .move_to_element(input_element_change_to_plain) \
            .click(input_element_change_to_plain) \
            .send_keys(message) \
            .send_keys(Keys.TAB) \
            .send_keys(Keys.TAB) \
            .send_keys(Keys.ENTER) \
            .perform()
