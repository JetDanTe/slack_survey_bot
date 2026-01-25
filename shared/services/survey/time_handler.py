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

            time_units = {"h": 3600, "m": 60, "s": 1}

            return number * time_units.get(unit, 3600)
        except (ValueError, KeyError):
            print("Unsupported time unit. Using default 2h value.")
            return 2 * 3600
