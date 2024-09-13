def main(pizza_size, toppings, num_drinks, drinks):
    #print(f"Calculating price for a {pizza_size} with {toppings} and {num_drinks} {drinks}")
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
    if len(toppings)>3:
        price += 0.5*(len(toppings)-3)
    return f"{price}$"
