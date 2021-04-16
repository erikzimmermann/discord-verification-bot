# discord-verification-bot
A Discord bot that verifies resource purchases of https://www.spigotmc.org/ accounts fully autonomously. 
It waits for incoming verification requests initiated by messages in a promote-channel, checks whether this SpigotMC user has bought the plugin
and sends a generated code to the target SpigotMC user, which finally must be confirmed in the promote-channel. Since this process is automated,
an expiration date can be set for premium roles to avoid permanent role assignments.

You need a promote-channel, a premium role, a database and the Google Chrome browser installed.