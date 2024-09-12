def main(pizza_size, pizza_toppings, num_drinks, drinks):
    print(f"Calculating price for a {pizza_size} with {pizza_toppings} and {num_drinks} {drinks}")
    pizza_prices = {
         "small": 10,
         "medium": 15,
         "large": 20,
    }
    drink_prices = {
        "sprite": 1.5,
        "coke": 1.5,
        "water": 1,
    }
    # convert everything to lower case, just in case
    pizza_size = pizza_size.lower()
    drinks = drinks.lower()
    price = pizza_prices[pizza_size]+drink_prices[drinks]*num_drinks
    # now increment if toppings > 3
    if len(pizza_toppings)>3:
        price += 0.5*(len(pizza_toppings)-3)
    return f"The price of your order is {price}$"
