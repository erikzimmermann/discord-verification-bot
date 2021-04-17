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

    def get_linked_discord_user_id(self, spigot_name):
        cursor = self.connection.cursor()
        cursor.execute("SELECT discord_id FROM `spigot-verification` WHERE spigot = '" + spigot_name + "' LIMIT 1")
        result = cursor.fetchall()

        if len(result) == 0:
            return None
        else:
            return result[0][0]

    def is_spigot_name_linked(self, spigot_name):
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(spigot) FROM `spigot-verification` WHERE spigot = '" + spigot_name + "' LIMIT 1")
        result = cursor.fetchall()
        return result[0][0] > 0

    def is_discord_user_linked(self, discord_user_id):
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(discord_id) FROM `spigot-verification` WHERE discord_id = '" + str(discord_user_id) + "' LIMIT 1")
        result = cursor.fetchall()
        return result[0][0] > 0

    # expiration_time in seconds
    def fetch_expired_links(self, expiration_time):
        cursor = self.connection.cursor()
        cursor.execute("SELECT discord_id FROM `spigot-verification` WHERE linked_at < now() - interval " + str(expiration_time) + " second")
        result = cursor.fetchall()

        if len(result) == 0:
            return None
        else:
            return result[0]

    def unlink_discord_ids(self, discord_user_ids):
        cursor = self.connection.cursor()

        # remove last ',' in array
        array = str(discord_user_ids)
        array = array[0:len(array) - 2] + ")"

        cursor.execute("DELETE FROM `spigot-verification` WHERE discord_id in " + array)
        self.connection.commit()

    def unlink_spigot_name(self, spigot_name):
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM `spigot-verification` WHERE spigot = '%s'", spigot_name)
        self.connection.commit()

    def link(self, spigot_name, discord_user):
        cursor = self.connection.cursor()
        cursor.execute("INSERT INTO `spigot-verification` (spigot, discord_name, discord_id) VALUES (%s, %s, %s)", (spigot_name, discord_user.name + "#" + discord_user.discriminator, discord_user.id))
        self.connection.commit()