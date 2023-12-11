from datetime import datetime
from abc import abstractmethod, ABC

class Formatter(ABC):
    @abstractmethod
    def do_format(self, value):
        pass

    @abstractmethod
    def get_type(self):
        pass


class DateFormatter(Formatter):
    def do_format(self, value):
        try:
            timestamp = datetime.fromisoformat(value)
            # Format the datetime object as a string in the desired format
            formatted_date = timestamp.strftime('%d/%m/%Y')
            return formatted_date

        except ValueError:
            return "Invalid date"

    def get_type(self):
        return "date"

class TimeFormatter(Formatter):
    def do_format(self, value):
        timestamp = datetime.fromisoformat(value)
        time_str = timestamp.strftime('%H:%M')
        return time_str

    def get_type(self):
        return "time"
