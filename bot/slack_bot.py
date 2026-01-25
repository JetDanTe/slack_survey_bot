from slack_bolt import App
from db import database_init
from audit import AuditSession
from slack_sdk.errors import SlackApiError
from custom_exceptions import EnvironmentVarException
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
import typing as tp

class AuditBot:

    _token_vars = ('SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN')

    def __init__(self, debug=False):
        self.database_manager = database_init()
        self.__check_tokens()
        self.debug = debug
        self.app = App(token=self.SLACK_BOT_TOKEN)
        self.audit_session = None
        self.admins = [user.id for user in self.database_manager.get_users('/admin_show')]
        # for future setup where audit name will be set from bot
        self.audit_name = "user_location"  # will be None

        # Define bot commands and event handlers
        # Audit control
        self.app.command("/audit_start")(self.admin_check(self.start_audit))
        self.app.command("/audit_stop")(self.admin_check(self.close_audit))
        self.app.command("/audit_unanswered")(self.admin_check(self.show_users))

        # User commands
        self.app.command("/answer")(self.collect_answer)
        self.app.command("/user_help")(self.show_user_help)
        self.app.command("/admin_show")(self.show_users)
        self.app.message()(self.shadow_answer)

        # Admin commands
        self.app.command("/users_update")(self.admin_check(self.update_users))
        self.app.command("/ignore_show")(self.admin_check(self.show_users))
        self.app.command("/ignore_update")(self.admin_check(self.update_ignore))

        # Not implemented commands
        self.app.command("/audits_show")(self.admin_check(self.not_implemented))
        self.app.command("/audit_get")(self.admin_check(self.not_implemented))

        # Socket mode handler to connect the bot to Slack
        self.handler = SocketModeHandler(self.app, self.SLACK_APP_TOKEN)

    def __check_tokens(self):
        """ Check if slack token vars exist in the system """
        for var in self._token_vars:
            if not var in os.environ:
                raise EnvironmentVarException(f'The var "{var} is absent"')
            else:
                exec(f"self.{var} = '{os.environ[var]}'")

    def admin_check(self, func):
        """ Decorator to check if the command is issued by an admin."""
        def wrapper(ack, body, say, *args, **kwargs):
            ack()
            user_id = body["user_id"]
            if user_id not in self.admins:
                say("You are not authorized to perform this action.")
                return
            return func(ack, body, say, *args, **kwargs)
        return wrapper

    def not_implemented(self, ack, body, say):
        """ Plug for handling uncreated commands"""
        ack()
        say("Command not implemented, yet.")

    def start_audit(self, ack, body, say):
        """ Audit process main function"""
        audit_message = body.get("text")
        say(f"Users will receive next message: \n{audit_message}")
        ack()  # Acknowledge the command
        if self.audit_session is not True:
            self.audit_session = AuditSession(self.audit_name, self.send_message, self.database_manager)
            self.audit_session.open_session(audit_message)
        else:
            say("There is already an active audit session.")

    def send_message(self, user_id, message):
        """ Alarm. Danger. This func can send messages to real people in your workspace. """
        if not self.debug:
            try:
                response = self.app.client.conversations_open(users=user_id)
                dm_channel_id = response["channel"]["id"]

                self.app.client.chat_postMessage(
                    channel=dm_channel_id,
                    text=message
                )
            except SlackApiError as e:
                print(f"Error sending message: {e.response['error']}")
        else:
            print(f'Message sending initialized. Message not sent - Debug "{self.debug}"')


    def collect_answer(self, ack, body, say):
        """Takes the user's answer and puts it into the database"""
        ack()
        data = {
            'id': body['user_id'],
            'name': body.get('user_name'),
            'answer': body['text']
        }
        if not self.audit_session:
            say("There is no active audit session. Please wait until an audit is started.")
        else:
            # existed_answer = self.database_manager.check_if_answer_exist(data)
            # if not existed_answer:
            self.audit_session.add_response(data)
            say(f"Thank you <@{body['user_id']}>! Your response '{body['text']}' has been recorded.")
            #else:
            #    say("You already answered.")

    def close_audit(self, ack, body, say):
        """ Close audit and return audit report .xlsx file """
        ack()  # Acknowledge the command
        channel_id = body.get('channel_id')
        if self.audit_session is not None:
            self.audit_session.close_session()
            audit_summary = self.audit_session.get_audit_summary()
            self.app.client.files_upload_v2(
                channel=channel_id,
                initial_comment="Audit closed!\nHere's report file :smile:",
                file=audit_summary,
            )
            self.audit_session = None
        else:
            say("There is no active audit session to close.")

    def update_users(self, ack, body, say):
        """ Gather user data from Slack. Update slack user status if_delete and add new users. """
        users = self.app.client.users_list()['members']
        self.database_manager.update_users(users)
        say("Users updated")

    def _format_user_list(self, users: tp.Text) -> tp.List[tp.Dict]:
        """
        Format list of users from string to dict
        :param users: Str
        :return: List of dicts
        """
        users = users.split(' ')
        formatted_users = [
            {
                'id': None,
                'name': user.replace('@', ''),
                'profile': {
                    'real_name': None
                }
            }
            for user in users
        ]
        return formatted_users

    def _handle_list_of_users(self, body: tp.Dict, update_type: str) -> tp.Text:
        """
        Handle list of users for different update types (admin or ignore).

        :param users: List of usernames to update
        :param update_type: Type of update ('admin' or 'ignore')
        :return: List of not found users
        :raises ValueError: If invalid update_type provided
        """
        if update_type not in ['admin', 'ignore']:
            raise ValueError("update_type must be either 'admin' or 'ignore'")

        text = f'{update_type.title()} list updated'
        users = self._format_user_list(body.get('text'))
        not_found_users = self.database_manager.update_users(users,
                                                             to_ignore=(update_type == 'ignore'),
                                                             to_admin=(update_type == 'admin'),
                                                             by_name=True)
        if not_found_users:
            text += f"\nCould not find the following users: {', '.join(user.get('name')for user in not_found_users)}"
        return text

    def update_ignore(self, ack, body, say):
        """ Update list of users which audit can ignore """
        ack()
        result = self._handle_list_of_users(body, 'ignore')
        say(result)

    def update_admin(self, ack, body, say):
        """ Set column is_admin to True in the database """
        ack()
        result = self._handle_list_of_users(body, 'admin')
        say(result)

    def show_users(self, ack, body, say):
        """ Universal command to show a list of users. Depends on which command is triggered."""
        ack()
        command_mapping = {
            "/ignore_show": "Ignored users:",
            "/admin_show": "Admin users:",
            "/audit_unanswered": "Audit unanswered:",
        }
        command_name = body.get('command')
        if not self.audit_session and command_name == "/audit_unanswered":
            say("There is no active audit session")
        else:

            users_to_show = self.database_manager.get_users(
                command_name,
                None if not self.audit_session else self.audit_session.table_name
            )
            if isinstance(users_to_show, str):
                say(users_to_show)
            else:
                users_to_show = '\n'.join(f'<@{user.id}>' for user in users_to_show)
                text = f"{command_mapping.get(command_name, 'Users:')}\n{users_to_show}"
                say(text)

    def show_user_help(self, ack, body, say):
        """ Return to user string with help information """
        ack()
        say(f'Use next command to answer:\n /answer <your_location>\n'
            f'For example:\n /answer Paris')

    def shadow_answer(self, ack, body, say):
        """ Trigger on any not slash command messages """
        ack()
        say(text='Sorry, do not understand. Use /help command or ask manager.',
            channel=body.get('event').get('channel'),
            thread_ts=body.get('event').get('ts'))

    def start(self):
        """ Connects to Slack in socket mode"""
        self.handler.start()