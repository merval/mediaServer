from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    watch_sessions_hosted = relationship('WatchSession', back_populates='host', cascade='all, delete-orphan')
    watch_participations = relationship('WatchSessionParticipant', back_populates='user', cascade='all, delete-orphan')


class MediaFile(Base):
    __tablename__ = 'media_files'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    file_path = Column(String, unique=True, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)
    last_modified = Column(DateTime)
    media_type = Column(String)
    thumbnail_path = Column(String, nullable=True)
    container = Column(String, nullable=True)
    bitrate = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    video_codec = Column(String, nullable=True)
    audio_codec = Column(String, nullable=True)
    channels = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    subtitle_count = Column(Integer, nullable=True, default=0)

    streams = relationship('MediaStream', back_populates='media_file', cascade='all, delete-orphan')
    playback_sessions = relationship('PlaybackSession', back_populates='media_file', cascade='all, delete-orphan')
    watch_sessions = relationship('WatchSession', back_populates='media_file', cascade='all, delete-orphan')


class MediaStream(Base):
    __tablename__ = 'media_streams'

    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.id'), nullable=False)
    stream_index = Column(Integer, nullable=True)
    codec_type = Column(String, nullable=True)
    codec_name = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    bitrate = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    language = Column(String, nullable=True)
    title = Column(String, nullable=True)

    media_file = relationship('MediaFile', back_populates='streams')


class PlaybackSession(Base):
    __tablename__ = 'playback_sessions'

    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.id'), nullable=False)
    user_session_id = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    playback_mode = Column(String, nullable=False)
    chosen_profile = Column(String, nullable=False)

    media_file = relationship('MediaFile', back_populates='playback_sessions')


class WatchSession(Base):
    __tablename__ = 'watch_sessions'

    id = Column(Integer, primary_key=True)
    join_code = Column(String, unique=True, nullable=False)
    host_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    media_file_id = Column(Integer, ForeignKey('media_files.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_playing = Column(Boolean, nullable=False, default=False)
    current_position_seconds = Column(Float, nullable=False, default=0.0)
    last_state_updated_at = Column(DateTime, nullable=False)

    host = relationship('User', back_populates='watch_sessions_hosted')
    media_file = relationship('MediaFile', back_populates='watch_sessions')
    participants = relationship('WatchSessionParticipant', back_populates='watch_session', cascade='all, delete-orphan')


class WatchSessionParticipant(Base):
    __tablename__ = 'watch_session_participants'

    id = Column(Integer, primary_key=True)
    watch_session_id = Column(Integer, ForeignKey('watch_sessions.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    joined_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)

    watch_session = relationship('WatchSession', back_populates='participants')
    user = relationship('User', back_populates='watch_participations')


class Movie(Base):
    __tablename__ = 'movies'
    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True)
    title = Column(String)
    release_year = Column(Integer)
    overview = Column(String)
    poster_url = Column(String)
    backdrop_url = Column(String)
    runtime = Column(Integer)
    imdb_rating = Column(Float)
    rotten_tomatoes_rating = Column(Float)


class Actor(Base):
    __tablename__ = 'actors'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class Director(Base):
    __tablename__ = 'directors'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class TVShow(Base):
    __tablename__ = 'tv_shows'
    id = Column(Integer, primary_key=True)
    tmdb_id = Column(Integer, unique=True)
    title = Column(String)
    overview = Column(String)
    first_air_date = Column(Date)
    poster_url = Column(String)
    status = Column(String)

    seasons = relationship('Season', back_populates='show', cascade='all, delete-orphan')


class Season(Base):
    __tablename__ = 'seasons'
    id = Column(Integer, primary_key=True)
    show_id = Column(Integer, ForeignKey('tv_shows.id'))
    season_number = Column(Integer)
    poster_url = Column(String)

    episodes = relationship('Episode', back_populates='season', cascade='all, delete-orphan')
    show = relationship('TVShow', back_populates='seasons')


class Episode(Base):
    __tablename__ = 'episodes'
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey('seasons.id'))
    episode_number = Column(Integer)
    title = Column(String)
    air_date = Column(Date)
    overview = Column(String)
    duration = Column(Integer)

    season = relationship('Season', back_populates='episodes')


class Artist(Base):
    __tablename__ = 'artists'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    bio = Column(String, nullable=True)


class Album(Base):
    __tablename__ = 'albums'
    id = Column(Integer, primary_key=True)
    artist_id = Column(Integer, ForeignKey('artists.id'))
    title = Column(String)
    release_year = Column(Integer)
    cover_url = Column(String)


class Track(Base):
    __tablename__ = 'tracks'
    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey('albums.id'))
    title = Column(String)
    duration = Column(Integer)
    track_number = Column(Integer)


movie_actor = Table(
    'movie_actor',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('actor_id', Integer, ForeignKey('actors.id')),
)

movie_director = Table(
    'movie_director',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('director_id', Integer, ForeignKey('directors.id')),
)

tv_actor = Table(
    'tv_actor',
    Base.metadata,
    Column('show_id', Integer, ForeignKey('tv_shows.id')),
    Column('actor_id', Integer, ForeignKey('actors.id')),
)
