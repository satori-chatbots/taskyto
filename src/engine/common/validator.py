from datetime import datetime
from abc import abstractmethod, ABC
from duckling import DucklingWrapper


class Formatter(ABC):
    @abstractmethod
    def do_format(self, value):
        pass

    @abstractmethod
    def get_type(self):
        pass

    @classmethod
    def get_validator(cls):
        return {
            'date': DateFormatter.do_format,
            'time': TimeFormatter.do_format,
        }


class DateFormatter(Formatter):
    def do_format(self, value):
        duckling_wrapper = DucklingWrapper()
        try:
            parsed_value = duckling_wrapper.parse_time(value)
            timestamp = datetime.fromisoformat(parsed_value[0]['value']['value'])
            # Format the datetime object as a string in the desired format
            formatted_date = timestamp.strftime('%d/%m/%Y')
            return formatted_date
        except ValueError:
            return "Invalid date"

    def get_type(self):
        return "date"


class TimeFormatter(Formatter):
    def do_format(self, value):
        duckling_wrapper = DucklingWrapper()
        try:
            parsed_value = duckling_wrapper.parse_time(value)
            timestamp = datetime.fromisoformat(parsed_value[0]['value']['value'])
            time_str = timestamp.strftime('%H:%M:%S')
            return time_str
        except ValueError:
            return "Invalid time"

    def get_type(self):
        return "time"
