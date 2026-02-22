from contextlib import contextmanager
from datetime import datetime

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for
from sqlalchemy import func

from config import (
    ENGINE,
    FLASK_DEBUG,
    PLAYBACK_OUTPUT_ROOT,
    PLAYBACK_TOKEN_MAX_AGE_SECONDS,
    PLAYBACK_TOKEN_SECRET,
    SessionLocal,
    validate_required_config,
)
from models import (
    Actor,
    Base,
    Director,
    Episode,
    MediaFile,
    Movie,
    PlaybackSession,
    Season,
    TVShow,
    movie_actor,
    movie_director,
)
from playback import PlaybackService

app = Flask(__name__)
app.logger.setLevel('INFO')

validate_required_config()
Base.metadata.create_all(ENGINE)
playback_service = PlaybackService(PLAYBACK_OUTPUT_ROOT, PLAYBACK_TOKEN_SECRET)


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
        featured_media = session.query(MediaFile).order_by(MediaFile.last_modified.desc()).first()

    return render_template(
        'index.html',
        movie_library=movie_library,
        show_library=show_library,
        featured_media=featured_media,
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


@app.route('/api/playback/sessions', methods=['POST'])
def create_playback_session():
    payload = request.get_json(silent=True) or {}
    media_id = payload.get('media_id')
    user_session_id = payload.get('user_session_id') or request.headers.get('X-Session-Id') or request.remote_addr or 'anonymous'

    if not media_id:
        return jsonify({'error': 'media_id is required'}), 400

    with get_session() as session:
        media = session.query(MediaFile).filter(MediaFile.id == media_id).first()
        if media is None:
            return jsonify({'error': 'media item not found'}), 404

        mode = playback_service.choose_mode(media)
        profile = playback_service.choose_profile(media)

        playback_session = PlaybackSession(
            media_file_id=media.id,
            user_session_id=str(user_session_id),
            started_at=datetime.utcnow(),
            playback_mode=mode,
            chosen_profile=profile.name,
        )
        session.add(playback_session)
        session.commit()
        session.refresh(playback_session)

        try:
            artifact_info = playback_service.prepare_session(media, playback_session.id)
        except Exception as exc:
            app.logger.exception('Failed to prepare playback session for media_id=%s', media.id)
            session.delete(playback_session)
            session.commit()
            return jsonify({'error': f'Unable to prepare playback artifacts: {exc}'}), 500

        master_path = 'master.m3u8'
        token = playback_service.sign_token(playback_session.id, master_path)
        master_url = url_for('serve_playback_asset', playback_session_id=playback_session.id, asset_path=master_path, token=token)

        app.logger.info(
            'Playback session started: playback_session_id=%s media_id=%s user_session_id=%s profile=%s mode=%s',
            playback_session.id,
            media.id,
            user_session_id,
            artifact_info['profile'],
            artifact_info['mode'],
        )

        return jsonify(
            {
                'playback_session_id': playback_session.id,
                'media_id': media.id,
                'user_session_id': user_session_id,
                'started_at': playback_session.started_at.isoformat(),
                'mode': artifact_info['mode'],
                'profile': artifact_info['profile'],
                'master_url': master_url,
                'token_ttl_seconds': PLAYBACK_TOKEN_MAX_AGE_SECONDS,
            }
        )


@app.route('/api/playback/sessions/<int:playback_session_id>/asset/<path:asset_path>')
def serve_playback_asset(playback_session_id: int, asset_path: str):
    token = request.args.get('token')
    if not token:
        abort(401)

    valid = playback_service.verify_token(
        token,
        PLAYBACK_TOKEN_MAX_AGE_SECONDS,
        expected_playback_session_id=playback_session_id,
        path=asset_path,
    )
    if not valid:
        abort(403)

    asset = playback_service.resolve_output_path(playback_session_id, asset_path)
    if asset is None or not asset.exists() or not asset.is_file():
        abort(404)

    if asset.suffix == '.m3u8':
        content = asset.read_text(encoding='utf-8')
        rewritten = _rewrite_playlist(playback_session_id, content, asset_path)
        return app.response_class(rewritten, mimetype='application/vnd.apple.mpegurl')

    if asset.suffix == '.ts':
        return send_file(asset, mimetype='video/mp2t')

    if asset.suffix == '.m4s':
        return send_file(asset, mimetype='video/iso.segment')

    return send_file(asset)


def _rewrite_playlist(playback_session_id: int, content: str, playlist_path: str) -> str:
    base_dir = '' if '/' not in playlist_path else playlist_path.rsplit('/', 1)[0]
    rewritten_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            rewritten_lines.append(line)
            continue

        if stripped.startswith('http://') or stripped.startswith('https://'):
            rewritten_lines.append(line)
            continue

        relative = f'{base_dir}/{stripped}' if base_dir else stripped
        token = playback_service.sign_token(playback_session_id, relative)
        asset_url = url_for(
            'serve_playback_asset',
            playback_session_id=playback_session_id,
            asset_path=relative,
            token=token,
        )
        rewritten_lines.append(asset_url)

    return '\n'.join(rewritten_lines) + '\n'


if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG)
