import mysql.connector


class Credentials:
    def __init__(self, user="root", database="discord", password="", host="localhost", port=3306):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database


class Database:
    def __init__(self, credentials=Credentials()):
        # connect
        self.connection = mysql.connector.connect(
            host=credentials.host,
            port=credentials.port,
            user=credentials.user,
            password=credentials.password,
            database=credentials.database
        )

        # create table automatically
        self.create_table()

    def create_table(self):
        cursor = self.connection.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS `spigot-verification` ("
                       "spigot VARCHAR(50) NOT NULL, "
                       "discord_name VARCHAR(50) NOT NULL, "
                       "discord_id VARCHAR(50) NOT NULL, "
                       "linked_at timestamp NOT NULL DEFAULT now(), "
                       "UNIQUE (spigot), "
                       "UNIQUE (discord_id)"
                       ")")

    def is_spigot_name_linked(self, spigot_name):
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(spigot) FROM `spigot-verification` WHERE spigot='" + spigot_name + "' LIMIT 1")
        result = cursor.fetchall()
        return result[0][0] > 0

    def is_discord_name_linked(self, discord_user_id):
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(discord_id) FROM `spigot-verification` WHERE discord_id='" + str(discord_user_id) + "' LIMIT 1")
        result = cursor.fetchall()
        return result[0][0] > 0

    def link(self, spigot_name, discord_user):
        cursor = self.connection.cursor()
        cursor.execute("INSERT INTO `spigot-verification` (spigot, discord_name, discord_id) VALUES (%s, %s, %s)", (spigot_name, discord_user.name + "#" + discord_user.discriminator, discord_user.id))
        self.connection.commit()
