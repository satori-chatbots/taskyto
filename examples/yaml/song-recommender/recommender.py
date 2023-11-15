SONGS = {
    'spanish-rock': [
        'Feo, fuerte y formal',
        'La chica de ayer',
    ],
    'english-pop': [
        'Sky full of stars',
        'Yellow',
    ]
}


def main(genre, language):
    global SONGS

    print(f"Recommending {genre} songs in {language}")

    key = language.lower() + '-' + genre.lower()
    if key in SONGS:
        return "Suggestions: " + ",".join(SONGS[key])
    else:
        return f"I don't have any recommendations for your preferences: language={language} and genre={genre}"
