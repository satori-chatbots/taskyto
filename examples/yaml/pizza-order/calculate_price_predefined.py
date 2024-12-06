def main(pizza_size, pizza_type, num_drinks, drinks):
#def main(num_drinks, drinks):
    #print(f"Calculating price for a {pizza_size} {pizza_type} and {num_drinks} {drinks}")
    #print(f"Calculating price for {num_drinks} {drinks}")
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
    pizza_type_increment = {
         "margherita" : 0,
         "carbonara" : 2.5,
         "marinera" : 2,
         "hawaiian" : 2,
         "four cheese" : 2,
         "vegetarian" : 2,
    }
    # convert everything to lower case, just in case
    pizza_size = pizza_size.lower()
    pizza_type = pizza_type.lower()
    drinks = drinks.lower()
    price = pizza_prices[pizza_size]+pizza_type_increment[pizza_type]+drink_prices[drinks]*num_drinks
    #price = drink_prices[drinks] * num_drinks
    return f"{price}$"
