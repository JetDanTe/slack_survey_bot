import os

from slack_bolt import App
from app.application.services.user_service import UserService

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
user_service = UserService()


@app.command("/users_update")
def users_update(ack, body, say):
    ack()
    users = app.client.users_list().get('members')
    user_service.sync_user(users)
    say(f"Users updated")


@app.command("/admin_show")
def admin_show(ack, body, say):
    ack()
    admins = user_service.get_admins()
    text = create_list_of_users(admins, static_message="Admin users:") or "No admins found."
    say(text)


@app.command("/ignore_show")
def ignore_show(ack, body, say):
    ack()
    ignored = user_service.get_ignored()
    text = create_list_of_users(ignored, static_message="Ignored users:") or "No ignored users."
    say(text)


def create_list_of_users(users, static_message=""):
    static_message = static_message + "\n"
    return static_message + "\n".join(f"<@{u.id}>" for u in users)
