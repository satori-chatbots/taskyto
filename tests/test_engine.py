import base_test
from engine.common import get_property_value

from spec import DataProperty


def test_get_property_simple_and_coercions():
    assert get_property_value(DataProperty(name="name", type="string"),
                              {"name": "John"}) == "John"

    assert get_property_value(DataProperty(name="age", type="int"),
                              {"age": "12"}) == 12

    assert get_property_value(DataProperty(name="age", type="int"),
                              {"age": 12}) == 12


def test_get_property_not_found():
    assert get_property_value(DataProperty(name="name_not_found", type="string"),
                              {"name": "John"}) is None
