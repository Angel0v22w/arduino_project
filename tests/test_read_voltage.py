import math
import unittest

from read_voltage import VoltageSample, parse_voltage_line


class ParseVoltageLineTests(unittest.TestCase):
    def test_parses_two_voltage_values(self) -> None:
        self.assertEqual(
            parse_voltage_line("1.430,1.950\n", elapsed_s=2.5),
            VoltageSample(elapsed_s=2.5, u1_v=1.43, u2_v=1.95),
        )

    def test_accepts_surrounding_whitespace(self) -> None:
        sample = parse_voltage_line(" 0.125 , 4.875 ")
        self.assertIsNotNone(sample)
        assert sample is not None
        self.assertAlmostEqual(sample.u1_v, 0.125)
        self.assertAlmostEqual(sample.u2_v, 4.875)

    def test_ignores_blank_lines_and_comments(self) -> None:
        self.assertIsNone(parse_voltage_line("  \n"))
        self.assertIsNone(parse_voltage_line("# u1_v,u2_v"))

    def test_rejects_wrong_field_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 2"):
            parse_voltage_line("1.0,2.0,3.0")

    def test_rejects_non_numeric_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be numbers"):
            parse_voltage_line("error,2.0")

    def test_rejects_non_finite_values(self) -> None:
        for invalid in ("nan,2.0", "1.0,inf", "-inf,2.0"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "must be finite"):
                    parse_voltage_line(invalid)

    def test_values_are_regular_floats(self) -> None:
        sample = parse_voltage_line("1.0,2.0")
        assert sample is not None
        self.assertTrue(math.isfinite(sample.u1_v))
        self.assertTrue(math.isfinite(sample.u2_v))


if __name__ == "__main__":
    unittest.main()

