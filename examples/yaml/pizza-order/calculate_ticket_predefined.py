def main(pizza_size, pizza_type, num_drinks, drinks):
    import hashlib
    from datetime import datetime

    pizza_size = pizza_size.lower()
    pizza_type = pizza_type.lower()
    drinks = drinks.lower()
    ids = [pizza_size, pizza_type, str(num_drinks), drinks, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    return hashlib.md5(''.join(ids).encode()).hexdigest()[:6]
    #price = drink_prices[drinks] * num_drinks

