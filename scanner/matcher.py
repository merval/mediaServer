from guessit import guessit

from config import MOVIE_API, TV_API


def parse_media_name(file_name):
    result = guessit(file_name)
    metadata = lookup_metadata(result)
    return {**result, **metadata}


def lookup_metadata(guessit_result):
    metadata = {}
    if 'title' in guessit_result:
        title = guessit_result['title']
        if guessit_result.get('type') == 'movie':
            search_results = MOVIE_API.search(title)
            if search_results:
                movie = search_results[0]
                metadata = {
                    'tmdb_id': movie.id,
                    'overview': movie.overview,
                    'release_date': movie.release_date,
                    'poster_url': movie.poster_path,
                }
        elif guessit_result.get('type') == 'episode':
            search_results = TV_API.search(title)
            if search_results:
                show = search_results[0]
                metadata = {
                    'tmdb_id': show.id,
                    'overview': show.overview,
                    'first_air_date': show.first_air_date,
                    'poster_url': show.poster_path,
                }
    return metadata
