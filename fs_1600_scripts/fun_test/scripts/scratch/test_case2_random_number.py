from lib.system.fun_test import *
import random


class NumberGenerator():

    def generator(self):

        number_list = []
        for number_index in range(0, 100):
            number = random.randint(1, 100)

            number_list.append(number)
            # fun_test.log("Generated number is {}".format(number))
            # fun_test.test_assert(expression=number < 50, message="Random number is {}".format(number))

        return number_list

    def validate(self, numbers):
        result = False
        for number in numbers:
            if number < 50:
                fun_test.test_assert(expression=number > 49, message="Random number generated has number of value "
                                                                     "less than 50")
            else:
                result = True

        return result


if __name__ == "__main__":
    number_genrator = NumberGenerator()

    random_numbers = number_genrator.generator()
    fun_test.log("generated numbers are {}".format(random_numbers))

    fun_test.log("Validating if any number is less than value 50")
    validate_numbers = number_genrator.validate(random_numbers)
    if validate_numbers:
        fun_test.log("All numbers generator exceeds value 50, numbers are {}".format(random_numbers))
