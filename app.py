from flask import Flask, render_template

app = Flask(__name__)

MOVIE_LIBRARY = {
    "Trending Movies": [
        {
            "title": "Nightline Protocol",
            "year": 2024,
            "rating": "PG-13",
            "duration": "2h 08m",
            "description": "A former cyber analyst races to stop a global blackout in this high-stakes thriller.",
            "genre": "Action",
        },
        {
            "title": "Orbit Run",
            "year": 2022,
            "rating": "PG",
            "duration": "1h 51m",
            "description": "Two siblings uncover an interplanetary conspiracy in this adventure sci-fi hit.",
            "genre": "Sci-Fi",
        },
    ],
    "Award-Winning Movies": [
        {
            "title": "Parallel Echoes",
            "year": 2020,
            "rating": "R",
            "duration": "2h 21m",
            "description": "An award-winning psychological drama that blurs reality and memory.",
            "genre": "Drama",
        },
        {
            "title": "The Great Campout",
            "year": 2021,
            "rating": "PG",
            "duration": "1h 44m",
            "description": "A heartfelt comedy about cousins, campfires, and one unforgettable summer.",
            "genre": "Comedy",
        },
    ],
    "Family Movies": [
        {
            "title": "Maple Street Magic",
            "year": 2023,
            "rating": "G",
            "duration": "1h 37m",
            "description": "Kids in a quiet neighborhood discover a portal to an upside-down world of wonder.",
            "genre": "Family",
        },
    ],
}

SHOW_LIBRARY = {
    "Trending Series": [
        {
            "title": "Coastal Fire",
            "year": 2023,
            "rating": "TV-14",
            "genre": "Drama",
            "description": "A rescue team tackles impossible emergencies along California's dangerous coastline.",
            "seasons": [
                {"name": "Season 1", "episodes": 10},
                {"name": "Season 2", "episodes": 8},
            ],
        },
        {
            "title": "Summit 12",
            "year": 2024,
            "rating": "TV-14",
            "genre": "Thriller",
            "description": "A diplomatic summit spirals into chaos in this geopolitical suspense series.",
            "seasons": [
                {"name": "Season 1", "episodes": 12},
            ],
        },
    ],
    "Prestige TV": [
        {
            "title": "The Last Lighthouse",
            "year": 2021,
            "rating": "TV-MA",
            "genre": "Mystery",
            "description": "A small island's secrets unravel when a historian arrives to restore an abandoned beacon.",
            "seasons": [
                {"name": "Season 1", "episodes": 8},
                {"name": "Season 2", "episodes": 8},
                {"name": "Season 3", "episodes": 6},
            ],
        },
    ],
    "Kids & Animation Shows": [
        {
            "title": "Pixel Pals",
            "year": 2022,
            "rating": "TV-Y7",
            "genre": "Animation",
            "description": "A team of game characters protects the arcade from digital villains.",
            "seasons": [
                {"name": "Season 1", "episodes": 14},
                {"name": "Season 2", "episodes": 14},
                {"name": "Season 3", "episodes": 10},
            ],
        },
    ],
}


@app.route('/')
def home():
    return render_template(
        'index.html',
        movie_library=MOVIE_LIBRARY,
        show_library=SHOW_LIBRARY,
    )


if __name__ == '__main__':
    app.run(debug=True)
