def money_usd(amount):
    return with_commas(amount, accuracy=2, prefix="$")


def quantity(amount, accuracy = 0):
    return with_commas(amount, accuracy=accuracy, prefix='')


def with_commas(amount, accuracy:int = 0, prefix="$"):
    amount = str(amount)
    if not amount:
        amount = "0"

    parts = amount.split(".")
    if accuracy < 1:
        decimals = ""
    else:
        decimals = parts[1].ljust(accuracy, '0') if len(parts) > 1 else "00".ljust(accuracy, '0')
        decimals = f".{decimals[:accuracy]}"

    dollars = parts[0]
    ds = []
    comma = -1
    negative = dollars[0] == "-"
    for char in reversed(dollars):
        if char in "0123456789":
            comma += 1
            if comma > 2:
                ds.insert(0, ",")
                comma = 0
            ds.insert(0, char)

    dollars = "".join(ds)
    return f"-{prefix}{dollars}{decimals}" if negative else f"{prefix}{dollars}{decimals}"



if __name__ == '__main__':
    print(money_usd("-3456"))
    print(money_usd("$-234sdfasd12782349828,342.0"))
    print(money_usd("234342.34"))