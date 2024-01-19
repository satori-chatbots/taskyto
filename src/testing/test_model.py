import sys
from abc import ABC, abstractmethod
from typing import Literal, List, Dict, Any

import pydantic
from pydantic import BaseModel, Field
from pydantic.json_schema import DEFAULT_REF_TEMPLATE

import utils
from testing.test_config_model import default_test_configuration, TestConfigurationModel, SingleTestConfig


#from engine.common import Engine, ChatbotResult
#from testing.test_engine import TestEngineConfiguration


class InteractionElement(BaseModel, ABC):
    def check(self, test_config: SingleTestConfig, engine, config): # return response or None
        return False


class UserSays(InteractionElement):
    message: str

    def check(self, test_config: SingleTestConfig, engine, config, response):
        """
        return True since it is a UserSays
        """
        utils.print_user_request(self.message)
        response = engine.run_step(self.message)
        utils.print_chatbot_answer(response)
        return response


class ChatbotAnswer(InteractionElement):
    answers: List[str] = []

    def check(self, test_config: SingleTestConfig, engine, config, response):
        if not config.dry_run:
            message = response.chatbot_msg
            is_matched = False
            match_tolerance = test_config.match_strategy.tolerance
            if match_tolerance == 0.0:
                is_matched = message in self.answers
                if not is_matched:
                    # Compute the best alignment anyway, for user debugging purposes
                    best_answer, best_alignment = self.find_best_alignment(message)
                    misalignment = 100 - best_alignment
            else:
                best_answer, best_alignment = self.find_best_alignment(message)
                misalignment = 100 - best_alignment
                is_matched = misalignment <= match_tolerance * 100

            # TODO: if is_matched == False and test_config.match_strategy.use_llm == True, then we need to try with this

            if not is_matched:
                print(f"Chatbot answer was '{message}'\n", file=sys.stderr)
                print(f"Expected one of:", file=sys.stderr)
                for a in self.answers:
                    print(f" - {a}", file=sys.stderr)
                print(file=sys.stderr)
                print(f"Closest was:", best_answer, file=sys.stderr)
                print(f"Misalignment:", misalignment, file=sys.stderr)

                raise ValueError(f"Expected chatbot answer '{message}' not found in {self.answers}")
        return None

    def find_best_alignment(self, given):
        best_alignment = 0
        best_answer = None
        for a in self.answers:
            percent_alignment = self.is_aligned(a, given)
            if percent_alignment > best_alignment:
                best_alignment = percent_alignment
                best_answer = a
        return best_answer, best_alignment

    def is_aligned(self, expected, given):
        from alignment.sequence import Sequence
        from alignment.vocabulary import Vocabulary
        from alignment.sequencealigner import SimpleScoring, GlobalSequenceAligner

        # Create sequences to be aligned.
        #a = Sequence(expected.split())
        #b = Sequence(given.split())
        a = Sequence(list(expected))
        b = Sequence(list(given))

        # Create a vocabulary and encode the sequences.
        v = Vocabulary()
        aEncoded = v.encodeSequence(a)
        bEncoded = v.encodeSequence(b)

        # Create a scoring and align the sequences using global aligner.
        scoring = SimpleScoring(1, 0) # originally 2, -1
        aligner = GlobalSequenceAligner(scoring, 0) # originally -2
        score, encodeds = aligner.align(aEncoded, bEncoded, backtrace=True)

        return encodeds[0].percentIdentity()


        #min_identity = (100 - match_tolerance * 100)
        #return encodeds[0].percentIdentity() >= min_identity

        # Iterate over optimal alignments and print them.
        #for encoded in encodeds:
        #    alignment = v.decodeSequenceAlignment(encoded)
        #    print(alignment)
        #    print('Alignment score:', alignment.score)
        #    print('Percent identity:', alignment.percentIdentity())
        return False

class ModuleAssert(InteractionElement):
    assert_module: str = None

    def check(self, test_config: SingleTestConfig, engine, config, response) -> bool:
        if not config.dry_run:
            module_exec = response.debug_info.current_module

            if self.assert_module != module_exec:
                print(f"Expecting chatbot in module {self.assert_module}", file=sys.stderr)
                print(f"But chatbot was executing module {module_exec} ", file=sys.stderr)
                raise ValueError(f"Expected module {self.assert_module}, but was {module_exec}")
        return None


class DataAssert(InteractionElement):
    scope: str
    data_asserts: Dict[str, str] = {}

    def check(self, test_config: SingleTestConfig, engine, config, response):
        data = engine.execution_state.get_module_data(self.scope)

        print(f"Need to check the following assertions {self.data_asserts} in {data}")
        for attr in self.data_asserts:
            if attr in data:
                if data[attr] is None:
                    if self.data_asserts[attr] != 'None':
                        self.fail_no_equal(attr, actual = 'None', expected=self.data_asserts[attr])
                elif data[attr] != self.data_asserts[attr]:
                    self.fail_no_equal(attr, actual=data[attr], expected=self.data_asserts[attr])
            else:
                print(f"Did not find field {attr}", file=sys.stderr)
                raise ValueError(f"Did not find field {attr}")
        return None

    def fail_no_equal(self, attr: str, actual: str, expected: str):
        print(f"Expecting value {expected} for {attr}, but got {actual}", file=sys.stderr)
        raise ValueError(f"Expecting value {expected} for {attr}, but got {actual}")

class Interaction(BaseModel):
    name: str
    interactions: List[InteractionElement]
    config: SingleTestConfig


