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
        self.safe_say(
            receiver=body.get("event").get("user"),
            message="Sorry, do not understand. Use /help command or ask manager.",
            say_func=say,
            channel=body.get("event").get("channel"),
            thread_ts=body.get("event").get("ts"),
        )

    def handle_message_events(self, body, logger):
        """Acknowledge message events to avoid unhandled warnings."""
        logger.debug(f"Received message event: {body}")

    def safe_say(self, receiver: str, message: str, say_func, **kwargs):
        """Wrapper for say() that respects debug mode."""
        # Use existing UserHandler to get real name
        receiver_name = asyncio.run(UserHandler().get_user_realname(receiver))

        if self.bot.debug:
            print(f'[DEBUG] Would say: "{message}" to {receiver_name}')
        else:
            say_func(message, **kwargs)

    def not_implemented(self, ack, body, say):
        """Plug for handling uncreated commands."""
        ack()
        self.safe_say(
            receiver=body.get("event", {}).get("user") or body.get("user_id"),
            message="Command not implemented, yet.",
            say_func=say,
        )
