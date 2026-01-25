from slack_bot import AuditBot


if __name__ == "__main__":
    bot = AuditBot(debug=False)
    bot.start()
