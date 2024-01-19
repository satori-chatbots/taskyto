from typing import List

from pydantic import BaseModel, Field


class MatchStrategy(BaseModel):
    tolerance: float = 0.0
    use_llm: bool = Field(alias="use-llm", default=False)


class SingleTestConfig(BaseModel):
    match_strategy: MatchStrategy = Field(alias="match-strategy", default=MatchStrategy())


class SpecificTestConfig(SingleTestConfig):
    name: str


class TestConfigurationModel(BaseModel):
    default: SingleTestConfig
    tests: List[SpecificTestConfig] = []

    def configuration_for_test(self, name: str) -> SingleTestConfig:
        for test in self.tests:
            if test.name == name or test.name == f"{name}.yaml":
                return test
        return self.default


def default_test_configuration() -> TestConfigurationModel:
    return TestConfigurationModel(default=SingleTestConfig())
