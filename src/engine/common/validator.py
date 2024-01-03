from datetime import datetime
from abc import abstractmethod, ABC
from duckling import DucklingWrapper

from engine.common import Configuration
from spec import DataProperty


class Formatter(ABC):
    @abstractmethod
    def do_format(self, value: str, p: DataProperty):
        pass

    @classmethod
    def get_validators(cls):
        return {
            'date': DateFormatter(),
            'time': TimeFormatter(),
            'enum': EnumFormatter()
        }


class DateFormatter(Formatter):
    def do_format(self, value: str, p: DataProperty, c: Configuration):
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
    def do_format(self, value: str, p: DataProperty, c: Configuration):
        duckling_wrapper = DucklingWrapper()
        try:
            parsed_value = duckling_wrapper.parse_time(value)
            timestamp = datetime.fromisoformat(parsed_value[0]['value']['value'])
            time_str = timestamp.strftime('%H:%M:%S')
            return time_str
        except ValueError:
            return "Invalid time"


class EnumFormatter(Formatter):

    def do_format(self, value: str, p: DataProperty, c: Configuration):
        indx = EnumFormatter.get_index_in(value.lower(), [val.lower() for val in p.values], c)
        if indx >= 0:
            return p.values[indx]
        else:
            return None

    @staticmethod
    def get_index_in(val, values, cnf):
        """
        returns the index of string val -- or a synonym of it -- in the list values. cnf is the Configuration from which we
        can extract the llm to extract synonyms
        """
        # check direct containment
        if val in values:
            return values.index(val)
        # now check synonyms
        prompt = f'Return a synonym of {val} among: {values} or None if there is no synonym. Return just one word.'
        llm = cnf.llm()
        result = llm.invoke(prompt)
        if result.content == 'None':
            return -1
        else:
            if result.content in values:
                return values.index(result.content)
            return -1
