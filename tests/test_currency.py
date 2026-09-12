from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from code.currency import CurrencyConverter, MissingExchangeRateError, RateKey
from code.ingestion import load_dataset


class CurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = load_dataset()
        cls.converter = CurrencyConverter.from_rates(data.exchange_rates)

    def test_same_currency_is_no_op_without_a_rate(self) -> None:
        self.assertEqual(
            self.converter.convert(
                Decimal("12.34"), "EUR", "EUR", date(2099, 1, 1)
            ),
            Decimal("12.34"),
        )

    def test_real_cross_currency_event_uses_exact_dated_rate(self) -> None:
        # event_2167 is USD 1,800 settling on 2023-10-15 for IDR-home user_25.
        result = self.converter.convert(
            Decimal("1800"), "USD", "IDR", date(2023, 10, 15)
        )
        self.assertEqual(result, Decimal("28499994.00"))

    def test_exact_rate_is_required_no_inverse_or_nearest_fallback(self) -> None:
        rates = {
            RateKey(date(2024, 1, 1), "USD", "EUR"): Decimal("0.90"),
            RateKey(date(2024, 1, 2), "EUR", "USD"): Decimal("1.11"),
        }
        converter = CurrencyConverter(rates)

        with self.assertRaises(MissingExchangeRateError):
            converter.convert(Decimal("10"), "USD", "EUR", date(2024, 1, 2))

        with self.assertRaises(MissingExchangeRateError):
            converter.convert(Decimal("10"), "EUR", "USD", date(2024, 1, 1))

    def test_missing_exact_rate_error_identifies_the_key(self) -> None:
        with self.assertRaisesRegex(
            MissingExchangeRateError,
            r"date=2024-01-01, from_currency=GBP, to_currency=EUR",
        ):
            self.converter.convert(Decimal("1"), "GBP", "EUR", date(2024, 1, 1))


if __name__ == "__main__":
    unittest.main()
