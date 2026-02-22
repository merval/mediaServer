import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


@dataclass(frozen=True)
class PlaybackProfile:
    name: str
    max_height: int
    video_bitrate: str
    audio_bitrate: str


BASELINE_720P = PlaybackProfile(
    name='hls-720p',
    max_height=720,
    video_bitrate='2800k',
    audio_bitrate='128k',
)


class PlaybackService:
    """Chooses playback mode and prepares playback artifacts for a media file."""

    def __init__(self, output_root: str, token_secret: str, token_salt: str = 'playback-token'):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.serializer = URLSafeTimedSerializer(token_secret, salt=token_salt)

    def choose_mode(self, media_file) -> str:
        if media_file.file_path.endswith('.m3u8'):
            return 'direct-play'

        if media_file.height and media_file.height <= BASELINE_720P.max_height:
            if media_file.container in {'mp4', 'mov'} and media_file.video_codec in {'h264', 'hevc'}:
                return 'direct-play'

        return 'transcode'

    def choose_profile(self, media_file) -> PlaybackProfile:
        return BASELINE_720P

    def prepare_session(self, media_file, playback_session_id: int) -> Dict[str, str]:
        mode = self.choose_mode(media_file)
        profile = self.choose_profile(media_file)
        session_dir = self.output_root / str(playback_session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
        session_dir.mkdir(parents=True, exist_ok=True)

        if mode == 'direct-play' and media_file.file_path.endswith('.m3u8'):
            source = Path(media_file.file_path)
            target = session_dir / 'master.m3u8'
            if source.exists():
                shutil.copy2(source, target)
            else:
                raise FileNotFoundError(f'Media source does not exist: {source}')
            return {'mode': mode, 'profile': profile.name, 'master_playlist': str(target)}

        profile_dir = session_dir / profile.name
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._generate_hls(media_file.file_path, profile, profile_dir)
        master_path = self._write_master_playlist(session_dir, profile)

        return {'mode': mode, 'profile': profile.name, 'master_playlist': str(master_path)}

    def _generate_hls(self, input_file: str, profile: PlaybackProfile, output_dir: Path) -> None:
        media_playlist = output_dir / 'index.m3u8'
        segment_pattern = output_dir / 'segment_%03d.ts'

        ffmpeg_cmd = [
            'ffmpeg',
            '-y',
            '-i',
            input_file,
            '-vf',
            f'scale=-2:{profile.max_height}',
            '-c:v',
            'libx264',
            '-preset',
            'veryfast',
            '-b:v',
            profile.video_bitrate,
            '-maxrate',
            profile.video_bitrate,
            '-bufsize',
            '2M',
            '-c:a',
            'aac',
            '-b:a',
            profile.audio_bitrate,
            '-ac',
            '2',
            '-f',
            'hls',
            '-hls_time',
            '6',
            '-hls_playlist_type',
            'vod',
            '-hls_segment_filename',
            str(segment_pattern),
            str(media_playlist),
        ]

        completed = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f'ffmpeg failed: {completed.stderr}')

    def _write_master_playlist(self, session_dir: Path, profile: PlaybackProfile) -> Path:
        master_path = session_dir / 'master.m3u8'
        bandwidth = self._bitrate_to_bandwidth(profile.video_bitrate, profile.audio_bitrate)
        master_path.write_text(
            '\n'.join(
                [
                    '#EXTM3U',
                    '#EXT-X-VERSION:3',
                    f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION=1280x{profile.max_height}',
                    f'{profile.name}/index.m3u8',
                    '',
                ]
            ),
            encoding='utf-8',
        )
        return master_path

    def sign_token(self, playback_session_id: int, path: str) -> str:
        digest = hashlib.sha256(path.encode('utf-8')).hexdigest()
        payload = {
            'playback_session_id': playback_session_id,
            'path': path,
            'digest': digest,
            'issued_at': datetime.utcnow().isoformat(),
        }
        return self.serializer.dumps(payload)

    def verify_token(self, token: str, max_age_seconds: int, expected_playback_session_id: int, path: str) -> bool:
        try:
            payload = self.serializer.loads(token, max_age=max_age_seconds)
        except (BadSignature, SignatureExpired):
            return False

        expected_digest = hashlib.sha256(path.encode('utf-8')).hexdigest()
        return (
            payload.get('playback_session_id') == expected_playback_session_id
            and payload.get('path') == path
            and payload.get('digest') == expected_digest
        )

    def resolve_output_path(self, playback_session_id: int, relative_path: str) -> Optional[Path]:
        clean_relative = os.path.normpath(relative_path).lstrip(os.path.sep)
        base = (self.output_root / str(playback_session_id)).resolve()
        candidate = (base / clean_relative).resolve()
        if not str(candidate).startswith(str(base)):
            return None
        return candidate

    @staticmethod
    def _bitrate_to_bandwidth(video_bitrate: str, audio_bitrate: str) -> int:
        def to_int(value: str) -> int:
            value = value.lower().strip()
            if value.endswith('k'):
                return int(value[:-1]) * 1000
            if value.endswith('m'):
                return int(value[:-1]) * 1_000_000
            return int(value)

        return to_int(video_bitrate) + to_int(audio_bitrate)
