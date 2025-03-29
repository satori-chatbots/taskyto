import base_test
from taskyto.engine.common import get_property_value
from taskyto.engine.common.validator import EnumFormatter

from taskyto.spec import DataProperty, EnumValue


def test_format_single_enums():
    prop = DataProperty(name="my_enum", type="enum",
                        values=[EnumValue(name="a"), EnumValue(name="b"), EnumValue(name="c")])
    value = 'a'

    formatter = EnumFormatter()
    formatted_value = formatter.do_format(value, prop, None)

    assert formatted_value == 'a'


def test_format_multiple_enums():
    prop = DataProperty(name="my_enum", type="enum",
                        values=[EnumValue(name="a"), EnumValue(name="b"), EnumValue(name="c")])
    value = ['a', 'b']

    formatter = EnumFormatter()
    formatted_value = formatter.do_format(value, prop, None)

    assert formatted_value == ['a', 'b']
