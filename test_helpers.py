import unittest
import helpers
import os


class TestRunner(unittest.TestCase):
    def setUp(self):
        if getattr(self, '_runner', None) is None:
            self._runner = helpers.CommandRunner(default_cwd=os.getcwd(), print_cmd=False)

    def test_runner_captures_output(self):
        got = self._runner(['/bin/echo', '1']).strip()
        wanted = '1'
        self.assertEqual(got, wanted)

    def test_runner_does_something_on_fail(self):
        got_exception = False
        try:
            self._runner(['/bin/false'])
        except Exception:
            got_exception = True
        self.assertTrue(got_exception)

if __name__ == '__main__':
    unittest.main()
