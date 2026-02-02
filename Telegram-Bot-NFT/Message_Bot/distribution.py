import re
from dataclasses import dataclass

INF = float("inf")


@dataclass
class PurchaseRule:
    min: float
    max: float
    count: int


def parse_distribution(distribution: str) -> list[PurchaseRule]:
    rules: list[PurchaseRule] = []
    lines = [line.strip() for line in distribution.split("\n") if line.strip()]

    for line in lines:
        parts = line.split()
        if not parts:
            continue

        count = int(parts[-1])
        range_part = " ".join(parts[:-1])

        min_val = 0.0
        max_val = INF

        pieces = re.split(r"\s+(?:и|and)\s+", range_part, flags=re.IGNORECASE)

        for piece in pieces:
            piece = piece.strip()
            m = re.match(r"^<=(\d+(?:\.\d+)?)$", piece)
            if m:
                max_val = float(m.group(1))
                continue
            m = re.match(r"^<(\d+(?:\.\d+)?)$", piece)
            if m:
                max_val = float(m.group(1)) - 1
                continue
            m = re.match(r"^>=(\d+(?:\.\d+)?)$", piece)
            if m:
                min_val = float(m.group(1))
                continue
            m = re.match(r"^>(\d+(?:\.\d+)?)$", piece)
            if m:
                min_val = float(m.group(1)) + 1
                continue
            m = re.match(r"^=(\d+(?:\.\d+)?)$", piece)
            if m:
                min_val = float(m.group(1))
                max_val = float(m.group(1))
                continue

        rules.append(PurchaseRule(min=min_val, max=max_val, count=count))

    return rules


def validate_distribution(text: str) -> tuple[bool, str]:
    lines = text.strip().split("\n")
    if not lines:
        return False, "Пустой ввод"

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 2:
            return False, f"Ошибка в строке {i}: недостаточно значений"

        try:
            quantity = int(parts[-1])
            if quantity <= 0:
                return False, f"Ошибка в строке {i}: количество должно быть положительным числом"
        except ValueError:
            return False, f"Ошибка в строке {i}: количество должно быть целым числом"

        condition_parts = parts[:-1]
        condition = " ".join(condition_parts)

        if " и " in condition:
            sub_conditions = condition.split(" и ")
            for sub_cond in sub_conditions:
                sub_cond = sub_cond.strip()
                if not re.match(r"^[<>=]=?\d+(\.\d+)?$", sub_cond):
                    return False, f"Ошибка в строке {i}: неверный формат условия '{sub_cond}'"
        else:
            if not re.match(r"^[<>=]=?\d+(\.\d+)?$", condition):
                return False, f"Ошибка в строке {i}: неверный формат условия '{condition}'"

    return True, ""
