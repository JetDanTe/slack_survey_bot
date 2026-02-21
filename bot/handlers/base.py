from abc import ABC, abstractmethod


class BaseHandler(ABC):
    """
    Base class for Slack bot handlers.

    Each handler module should inherit from this class and implement the `register` method.
    """

    def __init__(self, bot):
        """
        Initialize the handler with a reference to the main SurveyBot instance.

        Args:
            bot: The SurveyBot instance.
        """
        self.bot = bot
        self.app = bot.app
        self.logger = bot.logger.bind(handler=self.__class__.__name__)

    @abstractmethod
    def register(self):
        """
        Register Slack commands, actions, events, and views.
        Should be implemented by subclasses.
        """
        pass
