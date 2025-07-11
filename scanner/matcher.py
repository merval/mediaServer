from guessit import guessit
from tmdbv3api import TMDb, Movie, TV

tmdb = TMDb()
tmdb.api_key = 'your_tmdb_api_key'
tmdb.language = 'en'

movie_api = Movie()
tv_api = TV()

def parse_media_name(file_name):
    result = guessit(file_name)
    metadata = lookup_metadata(result)
    return {**result, **metadata}

def lookup_metadata(guessit_result):
    metadata = {}
    if 'title' in guessit_result:
        title = guessit_result['title']
        if guessit_result.get('type') == 'movie':
            search_results = movie_api.search(title)
            if search_results:
                movie = search_results[0]
                metadata = {
                    'tmdb_id': movie.id,
                    'overview': movie.overview,
                    'release_date': movie.release_date,
                    'poster_url': movie.poster_path,
                }
        elif guessit_result.get('type') == 'episode':
            search_results = tv_api.search(title)
            if search_results:
                show = search_results[0]
                metadata = {
                    'tmdb_id': show.id,
                    'overview': show.overview,
                    'first_air_date': show.first_air_date,
                    'poster_url': show.poster_path,
                }
    return metadata