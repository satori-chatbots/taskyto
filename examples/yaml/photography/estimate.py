def main(location, description, media, number_artworks, type_artworks):
    global SONGS

    print(f"Calculating price for a {media} session ({number_artworks} {type_artworks}) at {location}")

    return f"The prices for {description} would be around {number_artworks*123}$"
