from slack_bot import AuditBot

from shared.services.settings.main import settings

if __name__ == "__main__":
    bot = AuditBot(settings)
    bot.start()
