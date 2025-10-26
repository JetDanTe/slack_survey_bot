# main.py
from app.interface.slack.routes import app
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
