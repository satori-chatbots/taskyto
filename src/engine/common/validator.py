from datetime import datetime
from abc import abstractmethod, ABC
from duckling import DucklingWrapper

from spec import DataProperty


class Formatter(ABC):
    @abstractmethod
    def do_format(self, value: str, p : DataProperty):
        pass

    @classmethod
    def get_validators(cls):
        return {
            'date': DateFormatter(),
            'time': TimeFormatter(),
            'enum': EnumFormatter()
        }



class DateFormatter(Formatter):
    def do_format(self, value: str, p : DataProperty):
        duckling_wrapper = DucklingWrapper()
        try:
            parsed_value = duckling_wrapper.parse_time(value)
            timestamp = datetime.fromisoformat(parsed_value[0]['value']['value'])
            # Format the datetime object as a string in the desired format
            formatted_date = timestamp.strftime('%d/%m/%Y')
            return formatted_date
        except ValueError:
            return "Invalid date"

class TimeFormatter(Formatter):
    def do_format(self, value: str, p: DataProperty):
        duckling_wrapper = DucklingWrapper()
        try:
            parsed_value = duckling_wrapper.parse_time(value)
            timestamp = datetime.fromisoformat(parsed_value[0]['value']['value'])
            time_str = timestamp.strftime('%H:%M:%S')
            return time_str
        except ValueError:
            return "Invalid time"


class EnumFormatter(Formatter):

    def do_format(self, value: str, p: DataProperty):
        lower_values = [val.lower() for val in p.values]
        val_lower = value.lower()
        if val_lower in lower_values:
            return p.values[lower_values.index(val_lower)]
        else:
            return None
