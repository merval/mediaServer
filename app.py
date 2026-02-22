from contextlib import contextmanager

from flask import Flask, jsonify, render_template
from sqlalchemy import func

from config import ENGINE, FLASK_DEBUG, SessionLocal, validate_required_config
from models import (
    Actor,
    Base,
    Director,
    Episode,
    MediaFile,
    Movie,
    Season,
    TVShow,
    movie_actor,
    movie_director,
)

app = Flask(__name__)

validate_required_config()
Base.metadata.create_all(ENGINE)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _format_minutes(minutes):
    if minutes is None:
        return None

    hours = minutes // 60
    mins = minutes % 60
    if hours:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def _format_seconds(seconds):
    if seconds is None:
        return None
    return _format_minutes(int(seconds // 60))


def _movie_people_map(session):
    actor_rows = (
        session.query(movie_actor.c.movie_id, Actor.name)
        .join(Actor, movie_actor.c.actor_id == Actor.id)
        .all()
    )
    director_rows = (
        session.query(movie_director.c.movie_id, Director.name)
        .join(Director, movie_director.c.director_id == Director.id)
        .all()
    )

    cast_map = {}
    director_map = {}

    for movie_id, actor_name in actor_rows:
        cast_map.setdefault(movie_id, []).append(actor_name)

    for movie_id, director_name in director_rows:
        director_map.setdefault(movie_id, []).append(director_name)

    return cast_map, director_map


def get_movies_payload(session):
    cast_map, director_map = _movie_people_map(session)

    movies = session.query(Movie).order_by(Movie.release_year.desc(), Movie.title.asc()).all()
    payload = []
    for movie in movies:
        payload.append(
            {
                'id': movie.id,
                'title': movie.title,
                'year': movie.release_year,
                'rating': movie.imdb_rating,
                'duration': _format_minutes(movie.runtime),
                'duration_minutes': movie.runtime,
                'description': movie.overview,
                'genre': 'Unknown',
                'poster_url': movie.poster_url,
                'backdrop_url': movie.backdrop_url,
                'media_type': 'movie',
                'cast': cast_map.get(movie.id, []),
                'directors': director_map.get(movie.id, []),
            }
        )

    return payload


def get_shows_payload(session):
    shows = (
        session.query(
            TVShow,
            func.count(func.distinct(Season.id)).label('season_count'),
            func.count(func.distinct(Episode.id)).label('episode_count'),
        )
        .outerjoin(Season, Season.show_id == TVShow.id)
        .outerjoin(Episode, Episode.season_id == Season.id)
        .group_by(TVShow.id)
        .order_by(TVShow.first_air_date.desc(), TVShow.title.asc())
        .all()
    )

    payload = []
    for show, season_count, episode_count in shows:
        seasons = (
            session.query(Season)
            .filter(Season.show_id == show.id)
            .order_by(Season.season_number.asc())
            .all()
        )
        season_items = []
        for season in seasons:
            episode_total = session.query(func.count(Episode.id)).filter(Episode.season_id == season.id).scalar()
            season_items.append(
                {
                    'name': f"Season {season.season_number}",
                    'episodes': episode_total,
                }
            )

        payload.append(
            {
                'id': show.id,
                'title': show.title,
                'year': show.first_air_date.year if show.first_air_date else None,
                'rating': show.status,
                'duration': None,
                'duration_minutes': None,
                'description': show.overview,
                'genre': 'Unknown',
                'poster_url': show.poster_url,
                'media_type': 'show',
                'season_count': season_count,
                'episode_count': episode_count,
                'seasons': season_items,
            }
        )

    return payload


def get_media_files_payload(session):
    media_files = session.query(MediaFile).order_by(MediaFile.last_modified.desc()).all()
    payload = []
    for media in media_files:
        payload.append(
            {
                'id': media.id,
                'title': media.title,
                'year': None,
                'rating': None,
                'duration': _format_seconds(media.duration),
                'duration_seconds': media.duration,
                'description': None,
                'genre': None,
                'media_type': media.media_type,
                'file_path': media.file_path,
                'file_size': media.file_size,
                'last_modified': media.last_modified.isoformat() if media.last_modified else None,
                'thumbnail_path': media.thumbnail_path,
            }
        )
    return payload


@app.route('/')
def home():
    with get_session() as session:
        movie_library = {'Library Movies': get_movies_payload(session)}
        show_library = {'Library Shows': get_shows_payload(session)}

    return render_template(
        'index.html',
        movie_library=movie_library,
        show_library=show_library,
    )


@app.route('/api/library/movies')
def api_library_movies():
    with get_session() as session:
        movies = get_movies_payload(session)
    return jsonify({'items': movies, 'total': len(movies)})


@app.route('/api/library/shows')
def api_library_shows():
    with get_session() as session:
        shows = get_shows_payload(session)
    return jsonify({'items': shows, 'total': len(shows)})


@app.route('/api/library/media-files')
def api_library_media_files():
    with get_session() as session:
        media_files = get_media_files_payload(session)
    return jsonify({'items': media_files, 'total': len(media_files)})


if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG)
