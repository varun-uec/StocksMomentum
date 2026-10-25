"""Evidence-backed AMC identities; source labels remain in the source store.

Version 1 pairs AMFI NAV 2026-10-23 and master 2026-10-24 by shared AMFI
codes. See docs/current/mf-amc-identities.md for hashes and reconstruction.
IDs are curated constants: never regenerate them when a brand changes. No
substring, corporate-successor or historical-merger inference is permitted.
"""

from __future__ import annotations

from dataclasses import dataclass

AMC_IDENTITY_VERSION = 1


@dataclass(frozen=True, slots=True)
class Amc:
    """A stable identity and two labels corroborated by the same AMFI code."""

    id: str
    name: str
    master_label: str
    evidence_code: str

    @property
    def aliases(self) -> tuple[str, str]:
        """The exact labels retained in AMFI's NAV and master files."""
        return self.name, self.master_label


AMCS = (
    Amc("in-amc-360-one", "360 ONE Mutual Fund", "360 ONE Asset Management Limited", "153703"),
    Amc("in-amc-ask", "ASK MUTUAL FUND", "ASK ASSET MANAGEMENT PRIVATE LIMITED", "154591"),
    Amc(
        "in-amc-abakkus",
        "Abakkus Mutual Fund",
        "Abakkus Investment Managers Private Limited",
        "154477",
    ),
    Amc(
        "in-amc-aditya-birla-sun-life",
        "Aditya Birla Sun Life Mutual Fund",
        "Aditya Birla Sun Life AMC Limited",
        "148921",
    ),
    Amc(
        "in-amc-alphagrep",
        "AlphaGrep Mutual Fund",
        "AlphaGrep Investment Management Private Limited",
        "154518",
    ),
    Amc(
        "in-amc-angel-one",
        "Angel One Mutual Fund",
        "Angel One Asset Management Company Limited",
        "153529",
    ),
    Amc("in-amc-axis", "Axis Mutual Fund", "Axis Asset Management Co. Ltd.", "120505"),
    Amc(
        "in-amc-bajaj-finserv",
        "Bajaj Finserv Mutual Fund",
        "Bajaj Finserv Asset Management Limited",
        "153309",
    ),
    Amc("in-amc-bandhan", "Bandhan Mutual Fund", "Bandhan AMC Limited", "149303"),
    Amc(
        "in-amc-bank-of-india",
        "Bank of India Mutual Fund",
        "Bank of India Investment Managers Private Limited",
        "151443",
    ),
    Amc(
        "in-amc-baroda-bnp-paribas",
        "Baroda BNP Paribas Mutual Fund",
        "Baroda BNP Paribas Asset Management India Private Limited",
        "119354",
    ),
    Amc(
        "in-amc-canara-robeco",
        "Canara Robeco Mutual Fund",
        "Canara Robeco Asset Management Company Limited",
        "147532",
    ),
    Amc(
        "in-amc-capitalmind",
        "Capitalmind Mutual Fund",
        "Capitalmind Asset Management Private Limited",
        "154011",
    ),
    Amc(
        "in-amc-carnelian",
        "Carnelian Mutual Fund",
        "Carnelian Investment Managers Private Limited",
        "154784",
    ),
    Amc("in-amc-choice", "Choice Mutual Fund", "Choice AMC Private Limited", "154416"),
    Amc("in-amc-dsp", "DSP Mutual Fund", "DSP Asset Managers Private Limited", "119250"),
    Amc(
        "in-amc-edelweiss", "Edelweiss Mutual Fund", "Edelweiss Asset Management Limited", "152094"
    ),
    Amc(
        "in-amc-franklin-templeton",
        "Franklin Templeton Mutual Fund",
        "Franklin Templeton Asset Management (India) Private Limited",
        "152739",
    ),
    Amc("in-amc-groww", "Groww Mutual Fund", "Groww Asset Management Limited", "147458"),
    Amc("in-amc-hdfc", "HDFC Mutual Fund", "HDFC Asset Management Company Limited", "149366"),
    Amc("in-amc-hsbc", "HSBC Mutual Fund", "HSBC Asset Management (India) Private Ltd.", "154294"),
    Amc(
        "in-amc-helios",
        "Helios Mutual Fund",
        "Helios Capital Asset Management (India) Pvt. Ltd.",
        "152151",
    ),
    Amc(
        "in-amc-icici-prudential",
        "ICICI Prudential Mutual Fund",
        "ICICI Prudential Asset Management Company Limited",
        "120585",
    ),
    Amc("in-amc-iti", "ITI Mutual Fund", "ITI Asset Management Limited", "147183"),
    Amc(
        "in-amc-invesco",
        "Invesco Mutual Fund",
        "Invesco Asset Management (India) Private Limited",
        "147884",
    ),
    Amc(
        "in-amc-jm-financial",
        "JM Financial Mutual Fund",
        "JM Financial Asset Management Limited",
        "147838",
    ),
    Amc(
        "in-amc-jio-blackrock",
        "Jio BlackRock Mutual Fund",
        "Jio BlackRock Asset Management Private Limited",
        "153650",
    ),
    Amc(
        "in-amc-kotak-mahindra",
        "Kotak Mahindra Mutual Fund",
        "Kotak Mahindra Asset Management Company Limited.",
        "120152",
    ),
    Amc("in-amc-lic", "LIC Mutual Fund", "LIC Mutual Fund Asset Management Limited", "150659"),
    Amc(
        "in-amc-lakshya",
        "Lakshya Mutual Fund",
        "Lakshya Asset Management Private Limited",
        "154736",
    ),
    Amc(
        "in-amc-mahindra-manulife",
        "Mahindra Manulife Mutual Fund",
        "Mahindra Manulife Investment Management Pvt Ltd",
        "147563",
    ),
    Amc(
        "in-amc-mirae-asset",
        "Mirae Asset Mutual Fund",
        "Mirae Asset Investment Managers (India) Pvt. Ltd",
        "147737",
    ),
    Amc(
        "in-amc-monarch",
        "Monarch Mutual Fund",
        "Monarch Networth Asset Management Private Limited",
        "154705",
    ),
    Amc(
        "in-amc-motilal-oswal",
        "Motilal Oswal Mutual Fund",
        "Motilal Oswal Asset Management Company Limited",
        "152650",
    ),
    Amc("in-amc-nj", "NJ Mutual Fund", "NJ Asset Management Private Limited", "150369"),
    Amc("in-amc-navi", "Navi Mutual Fund", "Navi AMC Limited", "141414"),
    Amc(
        "in-amc-nippon-india",
        "Nippon India Mutual Fund",
        "Nippon Life India Asset Management Limited",
        "106235",
    ),
    Amc(
        "in-amc-old-bridge",
        "Old Bridge Mutual Fund",
        "Old Bridge Asset Management Private Limited",
        "152358",
    ),
    Amc(
        "in-amc-pgim-india",
        "PGIM India Mutual Fund",
        "PGIM India Asset Management Private Limite",
        "152815",
    ),
    Amc("in-amc-ppfas", "PPFAS Mutual Fund", "PPFAS Asset Management Pvt. Ltd.", "154155"),
    Amc(
        "in-amc-quantum",
        "Quantum Mutual Fund",
        "Quantum Asset Management Company Private Limited",
        "152107",
    ),
    Amc("in-amc-sbi", "SBI Mutual Fund", "SBI Funds Management Limited", "149887"),
    Amc("in-amc-samco", "Samco Mutual Fund", "Samco Asset Management Private Limited", "150631"),
    Amc("in-amc-shriram", "Shriram Mutual Fund", "Shriram Asset Management Co. Ltd.", "153076"),
    Amc(
        "in-amc-sundaram", "Sundaram Mutual Fund", "Sundaram Asset Management Company Ltd", "149668"
    ),
    Amc("in-amc-tata", "Tata Mutual Fund", "Tata Asset Management Private Limited", "151232"),
    Amc("in-amc-taurus", "Taurus Mutual Fund", "Taurus Asset Management Company Limited", "118870"),
    Amc(
        "in-amc-the-wealth-company",
        "The Wealth Company Mutual Fund",
        "Wealth Company Asset Management Holdings Private Limited",
        "154381",
    ),
    Amc("in-amc-trust", "Trust Mutual Fund", "Trust Asset Management Private Limited", "153644"),
    Amc("in-amc-uti", "UTI Mutual Fund", "UTI Asset Mgmt. Co. Ltd.", "120656"),
    Amc("in-amc-unifi", "Unifi Mutual Fund", "Unifi Asset Management Private Limited", "153570"),
    Amc(
        "in-amc-union",
        "Union Mutual Fund",
        "Union Asset Management Company Private Limited",
        "150858",
    ),
    Amc(
        "in-amc-whiteoak-capital",
        "WhiteOak Capital Mutual Fund",
        "WhiteOak Capital Asset Management Limited",
        "145969",
    ),
    Amc(
        "in-amc-zerodha",
        "Zerodha Mutual Fund",
        "Zerodha Asset Management Private Limited",
        "153436",
    ),
    Amc("in-amc-quant", "quant Mutual Fund", "quant Money Managers Limited", "100631"),
)


def _key(value: str) -> str:
    # Case and whitespace do not identify a different house. Punctuation stays:
    # accepting new spellings requires source evidence.
    return " ".join(value.split()).casefold()


_BY_ALIAS = {_key(alias): amc for amc in AMCS for alias in (*amc.aliases, amc.id)}


def amc_identity(value: str | None) -> Amc | None:
    """Resolve an evidenced label or ID; unknown labels stay unclassified."""
    return _BY_ALIAS.get(_key(value or ""))


def canonical_amc(value: str | None) -> str:
    """The investor-facing label, or the unmodified unknown source label."""
    found = amc_identity(value)
    return found.name if found else value or ""


def amc_key(value: str | None) -> str:
    """A known stable ID, otherwise the exact source label (no guessed identity)."""
    found = amc_identity(value)
    return found.id if found else value or ""


def amc_provenance(value: str | None) -> dict[str, str]:
    """Snapshot metadata keeps the original label and, where known, its identity."""
    found = amc_identity(value)
    return {"source_amc": value or "", **({"amc_id": found.id} if found else {})}
