"""Direct dated exchange-rate conversion justified by Stage 1 findings.

Stage 1 found 140 foreign-currency event rows and exact rate coverage for all
140. Therefore this module intentionally supports only:

* same-currency identity conversion; and
* exact ``(rate_date, from_currency, to_currency)`` lookup followed by
  multiplication.

It does not invert rates, choose nearby dates, compose rates, or silently
return a default when a key is absent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, NamedTuple

from .ingestion import ExchangeRate


class RateKey(NamedTuple):
    rate_date: date
    from_currency: str
    to_currency: str


class MissingExchangeRateError(LookupError):
    """Raised when an exact dated conversion key is not present."""


@dataclass(frozen=True)
class CurrencyConverter:
    """Converter backed by exact dated rates only."""

    rates_by_key: Mapping[RateKey, Decimal]

    @classmethod
    def from_rates(cls, rates: Iterable[ExchangeRate]) -> "CurrencyConverter":
        return cls(
            {
                RateKey(rate.rate_date, rate.from_currency, rate.to_currency): rate.rate
                for rate in rates
            }
        )

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: date,
    ) -> Decimal:
        """Convert using an identity or exact dated direct rate."""
        if from_currency == to_currency:
            return amount

        key = RateKey(rate_date, from_currency, to_currency)
        try:
            rate = self.rates_by_key[key]
        except KeyError as exc:
            raise MissingExchangeRateError(
                "no exact exchange rate for "
                f"date={rate_date.isoformat()}, "
                f"from_currency={from_currency}, to_currency={to_currency}"
            ) from exc
        return amount * rate


def convert(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    rate_date: date,
    rates_by_key: Mapping[RateKey, Decimal],
) -> Decimal:
    """Functional wrapper around :class:`CurrencyConverter`.

    ``rates_by_key`` must contain exact ``RateKey`` entries. This wrapper is
    useful for callers that keep a table separately from the converter object.
    """
    return CurrencyConverter(rates_by_key).convert(
        amount, from_currency, to_currency, rate_date
    )
