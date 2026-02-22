import datetime
import json
import os
import subprocess

from config import ENGINE, SCANNER_MEDIA_ROOT, SessionLocal
from models import Base, MediaFile, MediaStream

MEDIA_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mp3'}

Base.metadata.create_all(ENGINE)


def scan_media(directory=SCANNER_MEDIA_ROOT):
    session = SessionLocal()
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in MEDIA_EXTENSIONS:
                    full_path = os.path.join(root, file)
                    stat = os.stat(full_path)
                    file_size = stat.st_size
                    last_modified = datetime.datetime.fromtimestamp(stat.st_mtime)
                    ffprobe_data = get_media_probe_data(full_path)
                    media_fields, stream_rows = parse_media_technical_fields(ffprobe_data)
                    duration = media_fields.get('duration')

                    existing = session.query(MediaFile).filter_by(file_path=full_path).first()
                    if existing:
                        if existing.file_size == file_size and existing.last_modified == last_modified:
                            continue

                        existing.title = os.path.splitext(file)[0]
                        existing.file_size = file_size
                        existing.last_modified = last_modified
                        existing.media_type = guess_media_type(full_path)
                        existing.duration = duration
                        apply_technical_fields(existing, media_fields)
                        existing.streams = [MediaStream(**stream_data) for stream_data in stream_rows]
                        continue

                    media = MediaFile(
                        title=os.path.splitext(file)[0],
                        file_path=full_path,
                        file_size=file_size,
                        last_modified=last_modified,
                        media_type=guess_media_type(full_path),
                        duration=duration,
                    )
                    apply_technical_fields(media, media_fields)
                    media.streams = [MediaStream(**stream_data) for stream_data in stream_rows]
                    session.add(media)

        session.commit()
    finally:
        session.close()


def guess_media_type(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in {'.mp4', '.mkv', '.avi'}:
        return 'movie'
    elif ext in {'.mp3'}:
        return 'music'
    return 'unknown'


def get_media_probe_data(file_path):
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format:stream',
            '-of', 'json',
            file_path,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            return None

        return json.loads(result.stdout)

    except Exception as e:
        print(f"Error probing media metadata for {file_path}: {e}")
        return None


def parse_media_technical_fields(ffprobe_data):
    media_fields = {
        'duration': None,
        'container': None,
        'bitrate': None,
        'width': None,
        'height': None,
        'fps': None,
        'video_codec': None,
        'audio_codec': None,
        'channels': None,
        'sample_rate': None,
        'subtitle_count': 0,
    }
    stream_rows = []

    if not ffprobe_data:
        return media_fields, stream_rows

    format_data = ffprobe_data.get('format', {})
    streams = ffprobe_data.get('streams', [])

    media_fields['duration'] = safe_float(format_data.get('duration'))
    media_fields['container'] = format_data.get('format_name')
    media_fields['bitrate'] = safe_int(format_data.get('bit_rate'))

    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)

    if video_stream:
        media_fields['width'] = safe_int(video_stream.get('width'))
        media_fields['height'] = safe_int(video_stream.get('height'))
        media_fields['video_codec'] = video_stream.get('codec_name')
        media_fields['fps'] = parse_fps(video_stream.get('avg_frame_rate') or video_stream.get('r_frame_rate'))

    if audio_stream:
        media_fields['audio_codec'] = audio_stream.get('codec_name')
        media_fields['channels'] = safe_int(audio_stream.get('channels'))
        media_fields['sample_rate'] = safe_int(audio_stream.get('sample_rate'))

    media_fields['subtitle_count'] = sum(1 for s in streams if s.get('codec_type') == 'subtitle')

    for stream in streams:
        stream_rows.append({
            'stream_index': safe_int(stream.get('index')),
            'codec_type': stream.get('codec_type'),
            'codec_name': stream.get('codec_name'),
            'width': safe_int(stream.get('width')),
            'height': safe_int(stream.get('height')),
            'channels': safe_int(stream.get('channels')),
            'sample_rate': safe_int(stream.get('sample_rate')),
            'bitrate': safe_int(stream.get('bit_rate')),
            'fps': parse_fps(stream.get('avg_frame_rate') or stream.get('r_frame_rate')),
            'language': ((stream.get('tags') or {}).get('language')),
            'title': ((stream.get('tags') or {}).get('title')),
        })

    return media_fields, stream_rows


def apply_technical_fields(media, fields):
    media.container = fields.get('container')
    media.bitrate = fields.get('bitrate')
    media.width = fields.get('width')
    media.height = fields.get('height')
    media.fps = fields.get('fps')
    media.video_codec = fields.get('video_codec')
    media.audio_codec = fields.get('audio_codec')
    media.channels = fields.get('channels')
    media.sample_rate = fields.get('sample_rate')
    media.subtitle_count = fields.get('subtitle_count')


def parse_fps(value):
    if not value or value == '0/0':
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if '/' in value:
        numerator, denominator = value.split('/', 1)
        numerator = safe_float(numerator)
        denominator = safe_float(denominator)
        if numerator is None or denominator in (None, 0.0):
            return None
        return numerator / denominator

    return safe_float(value)


def safe_int(value):
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
