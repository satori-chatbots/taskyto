import base_test
from engine.common import get_property_value

from spec import DataProperty, EnumValue


def test_get_property_simple_and_coercions():
    assert get_property_value(DataProperty(name="name", type="string"),
                              {"name": "John"}) == "John"

    assert get_property_value(DataProperty(name="age", type="int"),
                              {"age": "12"}) == 12

    assert get_property_value(DataProperty(name="age", type="int"),
                              {"age": 12}) == 12

    assert get_property_value(DataProperty(name="left", type="number"),
                              {"left": "28"}) == 28


def test_get_property_not_found():
    assert get_property_value(DataProperty(name="name_not_found", type="string"),
                              {"name": "John"}) is None


def test_get_property_from_multiple_enums():
    prop = DataProperty(name="my_enum", type="enum",
                        values=[EnumValue(name="a"), EnumValue(name="b"), EnumValue(name="c")])

    assert get_property_value(prop, {"name": "John", "my_enum": ['a', 'b']}) == ['a', 'b']
    assert get_property_value(prop, {"name": "John", "my_enum": 'a'}) == 'a'
