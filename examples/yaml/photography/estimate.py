def main(media, number_artworks, type_artworks):
    print(f"Calculating price for a {media} session for {number_artworks} {type_artworks}")
    artwork_prices = {
        "sculpture": 10,
        "picture": 1,
        "ceramic": 5,
    }
    media_prices = {
        "photography": 50,
        "video": 200,
        "3D rendering": 290,
    }
    price = artwork_prices[type_artworks]*media_prices[media]
    return f"The price would be around {number_artworks*price}$, but may depend on other factors, like the size of the artworks"
