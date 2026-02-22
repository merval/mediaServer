import random
import string
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, abort, jsonify, render_template, request, send_file, session, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from config import (
    ENGINE,
    FLASK_DEBUG,
    FLASK_SECRET_KEY,
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
    User,
    WatchSession,
    WatchSessionParticipant,
    movie_actor,
    movie_director,
)
from playback import PlaybackService

app = Flask(__name__)
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
app.logger.setLevel('INFO')
socketio = SocketIO(app, cors_allowed_origins='*')

validate_required_config()
Base.metadata.create_all(ENGINE)
playback_service = PlaybackService(PLAYBACK_OUTPUT_ROOT, PLAYBACK_TOKEN_SECRET)


@contextmanager
def get_session():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


def _current_user_id():
    return session.get('user_id')


def _auth_required_route(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _current_user_id():
            return jsonify({'error': 'authentication required'}), 401
        return fn(*args, **kwargs)

    return wrapper


def _auth_required_socket():
    return bool(_current_user_id())


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


def _movie_people_map(db_session):
    actor_rows = (
        db_session.query(movie_actor.c.movie_id, Actor.name)
        .join(Actor, movie_actor.c.actor_id == Actor.id)
        .all()
    )
    director_rows = (
        db_session.query(movie_director.c.movie_id, Director.name)
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


def get_movies_payload(db_session):
    cast_map, director_map = _movie_people_map(db_session)

    movies = db_session.query(Movie).order_by(Movie.release_year.desc(), Movie.title.asc()).all()
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


def get_shows_payload(db_session):
    shows = (
        db_session.query(
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
            db_session.query(Season)
            .filter(Season.show_id == show.id)
            .order_by(Season.season_number.asc())
            .all()
        )
        season_items = []
        for season in seasons:
            episode_total = db_session.query(func.count(Episode.id)).filter(Episode.season_id == season.id).scalar()
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


def get_media_files_payload(db_session):
    media_files = db_session.query(MediaFile).order_by(MediaFile.last_modified.desc()).all()
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


def _watch_session_state_payload(watch_session: WatchSession):
    now = datetime.utcnow()
    current_position = watch_session.current_position_seconds
    if watch_session.is_playing:
        current_position += max(0.0, (now - watch_session.last_state_updated_at).total_seconds())

    return {
        'watch_session_id': watch_session.id,
        'join_code': watch_session.join_code,
        'media_id': watch_session.media_file_id,
        'is_playing': watch_session.is_playing,
        'position_seconds': round(current_position, 3),
        'server_time': now.isoformat(),
    }


def _generate_join_code(db_session):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(8):
        code = ''.join(random.choices(alphabet, k=6))
        existing = db_session.query(WatchSession).filter(WatchSession.join_code == code).first()
        if existing is None:
            return code
    raise RuntimeError('unable to generate unique join code')


@app.route('/')
def home():
    with get_session() as db_session:
        movie_library = {'Library Movies': get_movies_payload(db_session)}
        show_library = {'Library Shows': get_shows_payload(db_session)}
        featured_media = db_session.query(MediaFile).order_by(MediaFile.last_modified.desc()).first()

    return render_template(
        'index.html',
        movie_library=movie_library,
        show_library=show_library,
        featured_media=featured_media,
    )


@app.route('/api/auth/register', methods=['POST'])
def register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''

    if len(username) < 3 or len(password) < 6:
        return jsonify({'error': 'username >= 3 chars and password >= 6 chars are required'}), 400

    with get_session() as db_session:
        exists = db_session.query(User).filter(User.username == username).first()
        if exists:
            return jsonify({'error': 'username already exists'}), 409

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            created_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    return jsonify({'user_id': user.id, 'username': user.username}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''

    with get_session() as db_session:
        user = db_session.query(User).filter(User.username == username).first()
        if user is None or not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'invalid credentials'}), 401

    session['user_id'] = user.id
    session['username'] = user.username
    session.permanent = True

    return jsonify({'user_id': user.id, 'username': user.username})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/me')
def me():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({'authenticated': False})
    return jsonify({'authenticated': True, 'user_id': user_id, 'username': session.get('username')})


@app.route('/api/library/movies')
def api_library_movies():
    with get_session() as db_session:
        movies = get_movies_payload(db_session)
    return jsonify({'items': movies, 'total': len(movies)})


@app.route('/api/library/shows')
def api_library_shows():
    with get_session() as db_session:
        shows = get_shows_payload(db_session)
    return jsonify({'items': shows, 'total': len(shows)})


@app.route('/api/library/media-files')
def api_library_media_files():
    with get_session() as db_session:
        media_files = get_media_files_payload(db_session)
    return jsonify({'items': media_files, 'total': len(media_files)})


@app.route('/api/watch-sessions', methods=['POST'])
@_auth_required_route
def create_watch_session():
    payload = request.get_json(silent=True) or {}
    media_id = payload.get('media_id')
    if not media_id:
        return jsonify({'error': 'media_id is required'}), 400

    with get_session() as db_session:
        media = db_session.query(MediaFile).filter(MediaFile.id == int(media_id)).first()
        if media is None:
            return jsonify({'error': 'media item not found'}), 404

        join_code = _generate_join_code(db_session)
        now = datetime.utcnow()
        watch_session = WatchSession(
            join_code=join_code,
            host_user_id=_current_user_id(),
            media_file_id=media.id,
            created_at=now,
            is_active=True,
            is_playing=False,
            current_position_seconds=0.0,
            last_state_updated_at=now,
        )
        db_session.add(watch_session)
        db_session.flush()

        participant = WatchSessionParticipant(
            watch_session_id=watch_session.id,
            user_id=_current_user_id(),
            joined_at=now,
            last_seen_at=now,
        )
        db_session.add(participant)
        db_session.commit()

        return jsonify(
            {
                'watch_session_id': watch_session.id,
                'join_code': watch_session.join_code,
                'join_link': url_for('home', _external=True) + f'?join={watch_session.join_code}',
            }
        ), 201


@app.route('/api/watch-sessions/join', methods=['POST'])
@_auth_required_route
def join_watch_session():
    payload = request.get_json(silent=True) or {}
    join_code = (payload.get('join_code') or '').strip().upper()
    if not join_code:
        return jsonify({'error': 'join_code is required'}), 400

    with get_session() as db_session:
        watch_session = db_session.query(WatchSession).filter(WatchSession.join_code == join_code).first()
        if watch_session is None or not watch_session.is_active:
            return jsonify({'error': 'watch session not found'}), 404

        participant = (
            db_session.query(WatchSessionParticipant)
            .filter(
                WatchSessionParticipant.watch_session_id == watch_session.id,
                WatchSessionParticipant.user_id == _current_user_id(),
            )
            .first()
        )
        now = datetime.utcnow()
        if participant is None:
            participant = WatchSessionParticipant(
                watch_session_id=watch_session.id,
                user_id=_current_user_id(),
                joined_at=now,
                last_seen_at=now,
            )
            db_session.add(participant)
        else:
            participant.last_seen_at = now

        db_session.commit()

        return jsonify(_watch_session_state_payload(watch_session))


@app.route('/api/playback/sessions', methods=['POST'])
@_auth_required_route
def create_playback_session():
    payload = request.get_json(silent=True) or {}
    media_id = payload.get('media_id')
    user_session_id = str(_current_user_id())

    if not media_id:
        return jsonify({'error': 'media_id is required'}), 400

    with get_session() as db_session:
        media = db_session.query(MediaFile).filter(MediaFile.id == media_id).first()
        if media is None:
            return jsonify({'error': 'media item not found'}), 404

        mode = playback_service.choose_mode(media)
        profile = playback_service.choose_profile(media)

        playback_session = PlaybackSession(
            media_file_id=media.id,
            user_session_id=user_session_id,
            started_at=datetime.utcnow(),
            playback_mode=mode,
            chosen_profile=profile.name,
        )
        db_session.add(playback_session)
        db_session.commit()
        db_session.refresh(playback_session)

        try:
            artifact_info = playback_service.prepare_session(media, playback_session.id)
        except Exception as exc:
            app.logger.exception('Failed to prepare playback session for media_id=%s', media.id)
            db_session.delete(playback_session)
            db_session.commit()
            return jsonify({'error': f'Unable to prepare playback artifacts: {exc}'}), 500

        master_path = 'master.m3u8'
        token = playback_service.sign_token(playback_session.id, master_path)
        master_url = url_for('serve_playback_asset', playback_session_id=playback_session.id, asset_path=master_path, token=token)

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


def _update_watch_session_state(watch_session, action, requested_position):
    now = datetime.utcnow()
    current_position = watch_session.current_position_seconds
    if watch_session.is_playing:
        current_position += max(0.0, (now - watch_session.last_state_updated_at).total_seconds())

    if requested_position is not None:
        current_position = max(0.0, float(requested_position))

    if action == 'play':
        watch_session.is_playing = True
    elif action == 'pause':
        watch_session.is_playing = False
    elif action == 'seek':
        pass

    watch_session.current_position_seconds = current_position
    watch_session.last_state_updated_at = now


def _broadcast_watch_state(watch_session_id):
    with get_session() as db_session:
        watch_session = db_session.query(WatchSession).filter(WatchSession.id == watch_session_id).first()
        if watch_session is None:
            return
        socketio.emit('state_sync', _watch_session_state_payload(watch_session), room=f'watch:{watch_session_id}')


@socketio.on('join')
def socket_join(payload):
    if not _auth_required_socket():
        emit('error', {'error': 'authentication required'})
        return

    join_code = (payload or {}).get('join_code', '').strip().upper()
    if not join_code:
        emit('error', {'error': 'join_code is required'})
        return

    with get_session() as db_session:
        watch_session = db_session.query(WatchSession).filter(WatchSession.join_code == join_code).first()
        if watch_session is None or not watch_session.is_active:
            emit('error', {'error': 'watch session not found'})
            return

        participant = (
            db_session.query(WatchSessionParticipant)
            .filter(
                WatchSessionParticipant.watch_session_id == watch_session.id,
                WatchSessionParticipant.user_id == _current_user_id(),
            )
            .first()
        )
        now = datetime.utcnow()
        if participant is None:
            participant = WatchSessionParticipant(
                watch_session_id=watch_session.id,
                user_id=_current_user_id(),
                joined_at=now,
                last_seen_at=now,
            )
            db_session.add(participant)
        else:
            participant.last_seen_at = now

        db_session.commit()
        join_room(f'watch:{watch_session.id}')
        emit('state_sync', _watch_session_state_payload(watch_session))


@socketio.on('leave')
def socket_leave(payload):
    session_id = (payload or {}).get('watch_session_id')
    if session_id:
        leave_room(f'watch:{session_id}')


@socketio.on('play')
def socket_play(payload):
    _handle_playback_control('play', payload)


@socketio.on('pause')
def socket_pause(payload):
    _handle_playback_control('pause', payload)


@socketio.on('seek')
def socket_seek(payload):
    _handle_playback_control('seek', payload)


@socketio.on('state_sync')
def socket_state_sync(payload):
    _handle_playback_control('state_sync', payload)


def _handle_playback_control(action, payload):
    if not _auth_required_socket():
        emit('error', {'error': 'authentication required'})
        return

    payload = payload or {}
    watch_session_id = payload.get('watch_session_id')
    if not watch_session_id:
        emit('error', {'error': 'watch_session_id is required'})
        return

    requested_position = payload.get('position_seconds')

    with get_session() as db_session:
        participant = (
            db_session.query(WatchSessionParticipant)
            .filter(
                WatchSessionParticipant.watch_session_id == int(watch_session_id),
                WatchSessionParticipant.user_id == _current_user_id(),
            )
            .first()
        )
        if participant is None:
            emit('error', {'error': 'join session before controlling playback'})
            return

        watch_session = db_session.query(WatchSession).filter(WatchSession.id == int(watch_session_id)).first()
        if watch_session is None:
            emit('error', {'error': 'watch session not found'})
            return

        participant.last_seen_at = datetime.utcnow()
        if action != 'state_sync':
            _update_watch_session_state(watch_session, action, requested_position)
        elif requested_position is not None:
            server_pos = _watch_session_state_payload(watch_session)['position_seconds']
            if abs(server_pos - float(requested_position)) > 1.0:
                _update_watch_session_state(watch_session, 'seek', server_pos)

        db_session.commit()

    _broadcast_watch_state(int(watch_session_id))


def _drift_correction_loop():
    while True:
        socketio.sleep(2)
        threshold = datetime.utcnow() - timedelta(seconds=45)
        with get_session() as db_session:
            active_ids = [
                row[0]
                for row in (
                    db_session.query(WatchSessionParticipant.watch_session_id)
                    .filter(WatchSessionParticipant.last_seen_at >= threshold)
                    .distinct()
                    .all()
                )
            ]
        for watch_session_id in active_ids:
            _broadcast_watch_state(watch_session_id)


socketio.start_background_task(_drift_correction_loop)

if __name__ == '__main__':
    socketio.run(app, debug=FLASK_DEBUG)
