import os
import time
import datetime
import pandas as pd
import typing as tp

from db import DataBaseManager


class TimeFormatter:
    @staticmethod
    def format_time(time_str: str) -> int:
        """
        Convert time string to seconds.

        :param time_str: Time string (e.g., '2h', '30m', '45s')
        :return: Time in seconds
        """
        try:
            number = int(time_str[:-1])
            unit = time_str[-1]

            time_units = {
                'h': 3600,
                'm': 60,
                's': 1
            }

            return number * time_units.get(unit, 3600)
        except (ValueError, KeyError):
            print("Unsupported time unit. Using default 2h value.")
            return 2 * 3600


class AuditStorage:
    @staticmethod
    def create_audit_folder(folder_path: str) -> None:
        """
        Create audit folder with appropriate permissions.

        :param folder_path: Path to the audit folder
        """
        os.makedirs(folder_path, mode=0o777, exist_ok=True)

    @staticmethod
    def save_audit_summary(table: tp.List, table_name: str, audits_folder: str) -> str:
        """
        Save audit summary to Excel file.

        :param table: Audit table data
        :param table_name: Name of the audit table
        :param audits_folder: Folder to save audit files
        :return: Path to the saved Excel file
        """
        file_name = os.path.join(audits_folder, f"{table_name}.xlsx")
        columns = ['Name', 'Answer']
        data = [(tuple(row)[1], tuple(row)[2]) for row in table]
        df = pd.DataFrame(data, columns=columns)
        df.to_excel(file_name, index=False)
        return file_name


class AuditSession:
    DEFAULT_AUDITS_FOLDER = 'audit_files'
    DEFAULT_REMINDER_TIME = '2h'
    DEFAULT_REMINDER_MESSAGE = "Kindly reminder!:arrow-up:"

    def __init__(
            self,
            table_name: str,
            send_message: tp.Callable[[str, str], None],
            database_manager: DataBaseManager,
            reminder: tp.Optional[str] = None
    ):
        """
        Initialize an audit session.

        :param table_name: Base name for the audit table
        :param send_message: Function to send messages
        :param database_handlers: Dictionary of database operation handlers
        :param reminder: Custom reminder time
        """
        self._is_active = False
        self._responses: tp.Dict = {}
        self._admins = None

        self.table_name = f"{table_name}_{datetime.datetime.now().strftime('%d%m%Y')}"
        self.reminder_time = TimeFormatter.format_time(reminder or self.DEFAULT_REMINDER_TIME)

        self._send_message = send_message
        self._database_manager = database_manager

        AuditStorage.create_audit_folder(self.DEFAULT_AUDITS_FOLDER)

    def open_session(self, audit_message: str) -> None:
        """
        Open and start the audit session.

        :param audit_message: Initial audit message
        """
        self._is_active = True
        self._ensure_table_exists()
        self._start_audit(audit_message)

    def close_session(self) -> None:
        """
        Close the current audit session.
        """
        self._is_active = False

    def _ensure_table_exists(self) -> None:
        """
        Ensure the audit table exists, creating it if necessary.
        """
        table = self._database_manager.check_table_exists(self.table_name)
        if table is None:
            self._database_manager.create_audit_table(self.table_name)

    def _start_audit(self, initial_message: str) -> None:
        """
        Continuously send audit messages to target users.

        :param initial_message: First audit message to send
        """
        while self._is_active:
            target_users = self._get_target_users()
            for user_id in target_users:
                self._send_message(user_id, initial_message)

            initial_message = self.DEFAULT_REMINDER_MESSAGE
            time.sleep(self.reminder_time)

    def _get_target_users(self) -> tp.List[str]:
        """
        Retrieve list of target user IDs for the audit.

        :return: List of user IDs
        """
        target_users = self._database_manager.get_users('/audit_unanswered', self.table_name)
        return [user.id for user in target_users]

    def add_response(self, data: tp.Dict) -> None:
        """
        Add a response to the audit table.

        :param data: Response data
        """
        self._database_manager.add_row(self.table_name, data)

    def get_audit_summary(self) -> str:
        """
        Generate and save audit summary.

        :return: Path to the saved Excel file
        """
        table = self._database_manager.select_table(self.table_name)
        return AuditStorage.save_audit_summary(
            table,
            self.table_name,
            self.DEFAULT_AUDITS_FOLDER
        )