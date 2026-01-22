from settings import settings
from slack_bot import AuditBot

if __name__ == "__main__":
    bot = AuditBot(settings)
    bot.start()
