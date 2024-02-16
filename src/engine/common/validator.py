from datetime import datetime
from abc import abstractmethod, ABC
from typing import List, Union

from ctparse.types import Duration, Interval, DurationUnit
#from duckling import DucklingWrapper

from datetime import date
from dateutil.relativedelta import relativedelta

from engine.common import Configuration
from spec import DataProperty, EnumValue

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
        #return self.format_with_duckling(value)
        # Alternatively: self.format_with_duckling(value)

    def format_with_ctparse(self, value: str):
        ts = datetime.now()
        artefact = ctparse(value, ts=ts).resolution
        if isinstance(artefact, Duration):
            today = date.today()
            if artefact.unit == DurationUnit.DAYS:
                today = today + relativedelta(days=artefact.value)
            elif artefact.unit == DurationUnit.MONTHS:
                today = today + relativedelta(months=artefact.value)
            elif artefact.unit == DurationUnit.WEEKS:
                today = today + relativedelta(weeks=artefact.value)
            return today
        if isinstance(artefact, Interval):
            # for strings like 'the day after tomorrow', not sure if correctly parsed, since I think
            # it takes it as an open interval starting tomorrow
            timestamp = datetime(artefact.start.year, artefact.start.month, artefact.start.day)
            return timestamp.strftime('%d/%m/%Y')
        if artefact.hasDate:
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
        return self.format_with_ctparse(value)
        # Alternatively: self.format_with_duckling(value)

    def format_with_ctparse(self, value: str):
        ts = datetime.now()
        artefact = ctparse(value, ts=ts).resolution
        if artefact.hasTime:
            timestamp = datetime(artefact.year, artefact.month, artefact.day, artefact.hour, artefact.minute)
            time_str = timestamp.strftime('%H:%M:%S')
            return time_str
        return "Invalid time"

    def format_with_duckling(self, value: str):
        duckling_wrapper = DucklingWrapper()
        try:
            parsed_value = duckling_wrapper.parse_time(value)
            timestamp = datetime.fromisoformat(parsed_value[0]['value']['value'])
            time_str = timestamp.strftime('%H:%M:%S')
            return time_str
        except ValueError:
            return "Invalid time"


class EnumFormatter(Formatter):

    def do_format(self, value: Union[str, list[str]], prop: DataProperty, configuration: Configuration):
        if isinstance(value, list):
            result = []
            for v in value:
                format_result = EnumFormatter.format_single_value(v, prop, configuration)
                if format_result is None:
                    return None
                result.append(format_result)
            return result
        else:
            return EnumFormatter.format_single_value(value, prop, configuration)

    @staticmethod
    def format_single_value(value: str, p: DataProperty, c: Configuration):
        indx = EnumFormatter.get_index_in(value.lower(), p.values, c)
        if indx >= 0:
            return p.values[indx].name # TODO: Maybe return the actual EnumValue?
        else:
            return None

    @staticmethod
    def get_index_in(val: str, values: List[EnumValue], cnf):
        """
        returns the index of string val -- or a synonym of it -- in the list values. cnf is the Configuration from which we
        can extract the llm to extract synonyms
        """
        # check direct containment
        idx = EnumFormatter.check_value(val, values)
        if idx != -1:
            return idx

        # now check synonyms
        prompt = f'Return a synonym of {val} among: {values} or None if there is no synonym. Return just one word.'

        llm = cnf.new_llm()
        result = llm.invoke(prompt)
        if result.content == 'None':
            return -1
        else:
            return EnumFormatter.check_value(result.content, values)

    def check_value(val: str, values: List[EnumValue]):
        for idx, enum_value in enumerate(values):
            if enum_value.name.lower() == val:
                return idx
            elif val in [e.lower() for e in enum_value.examples]:
                return idx
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
