from lib.system.fun_test import *


class IncrementCounter():

    def increment_counter(self, counter=0):
        for counter in xrange(0, 50):
            fun_test.log("Current value of counter is {}".format(counter))
            counter += 1

        return counter


if __name__ == "__main__":
    tc_increment_counter = IncrementCounter()
    result_counter = tc_increment_counter.increment_counter()

    fun_test.test_assert_expected(expected=50, actual=result_counter, message="Counter increment is successful")