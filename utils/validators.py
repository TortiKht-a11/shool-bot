"""Input validators and normalizers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime


_FULL_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё\s\-]+$")
_PHONE_RE = re.compile(r"^(\+7|8)\d{10}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    value: str | None = None
    error: str | None = None


def validate_full_name(value: str, min_words: int = 2) -> ValidationResult:
    v = " ".join(value.strip().split())
    if len(v) < 3:
        return ValidationResult(False, error="Введите ФИО полностью (минимум 2 слова).")
    if not _FULL_NAME_RE.fullmatch(v):
        return ValidationResult(False, error="ФИО может содержать только буквы, пробелы и дефис.")
    if len(v.split()) < min_words:
        return ValidationResult(False, error=f"Введите минимум {min_words} слова(ов).")
    return ValidationResult(True, value=v)


def validate_birth_date_ddmmyyyy(value: str) -> ValidationResult:
    v = value.strip()
    try:
        dt = datetime.strptime(v, "%d.%m.%Y").date()
    except ValueError:
        return ValidationResult(False, error="Неверный формат. Пример: 05.09.2018")

    if dt < date(1900, 1, 1) or dt > date.today():
        return ValidationResult(False, error="Проверьте дату рождения — она выглядит неверно.")
    return ValidationResult(True, value=dt.strftime("%d.%m.%Y"))


def validate_child_age_for_first_grade(birth_ddmmyyyy: str, current_date: date | None = None) -> ValidationResult:
    try:
        dt = datetime.strptime(birth_ddmmyyyy, "%d.%m.%Y").date()
    except ValueError:
        return ValidationResult(False, error="Неверная дата. Пример: 05.09.2018")

    today = current_date or date.today()
    sep1 = date(today.year, 9, 1)
    # если сейчас после 1 сентября, то прием в следующем учебном году
    if today > sep1:
        sep1 = date(today.year + 1, 9, 1)

    years = sep1.year - dt.year - ((sep1.month, sep1.day) < (dt.month, dt.day))
    if years < 6 or years > 8:
        return ValidationResult(False, error="Возраст ребёнка должен быть от 6 до 8 лет на 1 сентября.")
    return ValidationResult(True, value=birth_ddmmyyyy)


def validate_phone(value: str) -> ValidationResult:
    v = value.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not _PHONE_RE.fullmatch(v):
        return ValidationResult(False, error="Неверный формат. Пример: +79281234567 или 89281234567")
    if v.startswith("8"):
        v = "+7" + v[1:]
    return ValidationResult(True, value=v)


def validate_email(value: str) -> ValidationResult:
    v = value.strip()
    if not v:
        return ValidationResult(True, value="")
    if not _EMAIL_RE.fullmatch(v):
        return ValidationResult(False, error="Неверный email. Пример: name@example.com")
    return ValidationResult(True, value=v)
