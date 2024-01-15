from datetime import datetime
from abc import abstractmethod, ABC
from duckling import DucklingWrapper

from engine.common import Configuration
from spec import DataProperty

from datetime import datetime
from ctparse import ctparse


class Formatter(ABC):
    @abstractmethod
    def do_format(self, value: str, p: DataProperty):
        pass

    @classmethod
    def get_validators(cls):
        return {
            'date': DateFormatter(),
            'time': TimeFormatter(),
            'enum': EnumFormatter(),
            'integer': IdentityFormatter(),  # we could have formatters to convert numbers expressed in words into digit
            'str': IdentityFormatter(),
            'double': IdentityFormatter(),
            'float': IdentityFormatter()
        }


class IdentityFormatter(Formatter):
    def do_format(self, value: str, p: DataProperty, c: Configuration):
        return value


class DateFormatter(Formatter):
    def do_format(self, value: str, p: DataProperty, c: Configuration):
        return self.format_with_ctparse(value)
        # Alternatively: self.format_with_duckling(value)

    def format_with_ctparse(self, value: str):
        ts = datetime.now()
        artefact = ctparse(value, ts=ts).resolution
        if artefact.isDate:
            # format a string from artefact.month, artefact.year, artefact.year
            timestamp = datetime(artefact.year, artefact.month, artefact.day)
            return timestamp.strftime('%d/%m/%Y')
        return "Invalid date"

    def format_with_duckling(self, value: str):
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
        llm = cnf.new_llm()
        result = llm.invoke(prompt)
        if result.content == 'None':
            return -1
        else:
            if result.content in values:
                return values.index(result.content)
            return -1


class FallbackFormatter(Formatter):
    def do_format(self, value: str, p: DataProperty, c: Configuration):
        prompt = f'Is {value} a {p.type}?. Reply yes or no.'
        llm = c.new_llm()
        result = llm.invoke(prompt)
        if 'yes' in result.content.lower():
            return value
        else:
            return None
