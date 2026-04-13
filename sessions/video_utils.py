import shutil
import subprocess
from pathlib import Path

from django.core.files import File


def compress_session_feedback_video(feedback_entry):
    if not feedback_entry or not getattr(feedback_entry, "video_proof", None):
        return False

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False

    source_name = feedback_entry.video_proof.name
    source_path = Path(feedback_entry.video_proof.path)
    if not source_path.exists():
        return False

    output_path = source_path.with_name(f"{source_path.stem}_compressed.mp4")
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-vf",
        "scale='min(854,iw)':-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryslow",
        "-crf",
        "35",
        "-b:v",
        "160k",
        "-c:a",
        "aac",
        "-b:a",
        "48k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except OSError:
        return False

    if result.returncode != 0 or not output_path.exists():
        return False

    if output_path.stat().st_size >= source_path.stat().st_size:
        output_path.unlink(missing_ok=True)
        return False

    with output_path.open("rb") as handle:
        feedback_entry.video_proof.save(output_path.name, File(handle), save=False)
    feedback_entry.save(update_fields=["video_proof", "updated_at"])
    feedback_entry.video_proof.storage.delete(source_name)
    output_path.unlink(missing_ok=True)
    return True
