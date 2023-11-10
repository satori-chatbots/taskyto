songs = {
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
    key = language + '-' + genre
    if key in songs:
        return songs[key]
    else:
        return "I don't have any recommendations for you"
