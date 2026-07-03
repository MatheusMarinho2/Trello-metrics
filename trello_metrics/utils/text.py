from __future__ import annotations

import re
import unicodedata


def strip_accents(value: object) -> str:
    text = "" if value is None else str(value)
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def clean_spaces(value: object) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(value: object) -> str:
    text = strip_accents(clean_spaces(value)).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "APROVAA A O": "APROVACAO",
        "APROVA O": "APROVACAO",
        "PRODUA A O": "PRODUCAO",
        "PRODU O": "PRODUCAO",
        "REVISA A O": "REVISAO",
        "REVISA O": "REVISAO",
        "REVIS O": "REVISAO",
        "HOMOLOGAA A O": "HOMOLOGACAO",
        "HOMOLOGA O": "HOMOLOGACAO",
        "ANAA LISE": "ANALISE",
        "AN LISE": "ANALISE",
        "NA VEL": "NIVEL",
        "N VEL": "NIVEL",
    }
    for broken, fixed in replacements.items():
        text = text.replace(broken, fixed)
    return re.sub(r"\s+", " ", text).strip()


def first_non_empty(*values: object) -> str:
    for value in values:
        text = clean_spaces(value)
        if text:
            return text
    return ""
