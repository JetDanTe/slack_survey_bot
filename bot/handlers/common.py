import asyncio

from handlers.base import BaseHandler
from services.user_handler.main import UserHandler


class CommonHandler(BaseHandler):
    """
    Handler for shared bot logic and utility methods.
    """

    def register(self):
        """Register common handlers."""
        self.app.message()(self.shadow_answer)
        self.app.event("message")(self.handle_message_events)

    def shadow_answer(self, ack, body, say):
        """Trigger on any message that is not a command."""
        ack()
        user_id = body.get("event", {}).get("user")
        channel_id = body.get("event", {}).get("channel")

        self.logger.info(
            "shadow_answer_triggered", user_id=user_id, channel_id=channel_id
        )

        self.safe_say(
            receiver=user_id,
            message="Sorry, do not understand. Use /help command or ask manager.",
            say_func=say,
            channel=channel_id,
            thread_ts=body.get("event", {}).get("ts"),
        )

    def handle_message_events(self, body, logger):
        """Acknowledge message events to avoid unhandled warnings."""
        self.logger.debug("received_message_event", body=body)

    def safe_say(self, receiver: str, message: str, say_func, **kwargs):
        """Wrapper for say() that respects debug mode."""
        # Use existing UserHandler to get real name
        receiver_name = asyncio.run(UserHandler().get_user_realname(receiver))

        if self.bot.debug:
            self.logger.debug("would_say", message=message, receiver=receiver_name)
        else:
            say_func(message, **kwargs)

    def not_implemented(self, ack, body, say):
        """Plug for handling uncreated commands."""
        ack()
        user_id = body.get("event", {}).get("user") or body.get("user_id")
        self.logger.warning("command_not_implemented", user_id=user_id)

        self.safe_say(
            receiver=user_id,
            message="Command not implemented, yet.",
            say_func=say,
        )
