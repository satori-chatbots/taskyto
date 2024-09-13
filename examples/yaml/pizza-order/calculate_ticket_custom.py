def main(pizza_size, toppings, num_drinks, drinks):
    import hashlib
    from datetime import datetime

    pizza_size = pizza_size.lower()
    pizza_type = '.'.join(toppings).lower()
    drinks = drinks.lower()
    ids = [pizza_size, pizza_type, str(num_drinks), drinks, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    return hashlib.md5(''.join(ids).encode()).hexdigest()[:6]

