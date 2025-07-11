from sqlalchemy import Column, Integer, String, Float, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, ForeignKey
from sqlalchemy.orm import relationship

Base = declarative_base()

class MediaFile(Base):
    __tablename__ = 'media_files'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    file_path = Column(String, unique=True, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)  # In seconds (optional)
    last_modified = Column(DateTime)
    media_type = Column(String)  # e.g., 'movie', 'show', 'music'
    thumbnail_path = Column(String, nullable=True)


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

    # Relationship: many episodes
    episodes = relationship('Episode', back_populates='season', cascade='all, delete-orphan')

    # Back-reference to parent show
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

    # Back-reference to parent season
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


movie_actor = Table('movie_actor', Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('actor_id', Integer, ForeignKey('actors.id'))
)

movie_director = Table('movie_director', Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id')),
    Column('director_id', Integer, ForeignKey('directors.id'))
)

tv_actor = Table('tv_actor', Base.metadata,
    Column('show_id', Integer, ForeignKey('tv_shows.id')),
    Column('actor_id', Integer, ForeignKey('actors.id'))
)

