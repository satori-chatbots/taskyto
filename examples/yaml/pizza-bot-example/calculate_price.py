def main(pizza_size, pizza_type):
    print(f"Calculating price for a {pizza_size} {pizza_type}")
    pizza_prices = {
         "small": 10,
         "medium": 15,
         "large": 20,
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
    price = pizza_prices[pizza_size]+pizza_type_increment[pizza_type]
    return f"The price of your order is {price}$"
