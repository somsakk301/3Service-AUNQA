"""Legacy DOC conversion through LibreOffice Headless."""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


class DocumentConversionError(RuntimeError):
    """Raised when LibreOffice cannot convert a DOC file."""


def convert_doc_to_docx(
    source_path: Path,
    output_directory: Path,
    *,
    timeout_seconds: int = 120,
) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    target_path = output_directory / f"{source_path.stem}.docx"
    target_path.unlink(missing_ok=True)

    with TemporaryDirectory(prefix="libreoffice-profile-") as profile_directory:
        profile_uri = Path(profile_directory).resolve().as_uri()
        process = subprocess.run(
            [
                "soffice",
                "--headless",
                f"-env:UserInstallation={profile_uri}",
                "--convert-to",
                "docx:Office Open XML Text",
                "--outdir",
                str(output_directory),
                str(source_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

    if process.returncode != 0 or not target_path.is_file():
        detail = (process.stderr or process.stdout).strip()
        raise DocumentConversionError(
            f"LibreOffice DOC conversion failed: {detail or 'no output file'}"
        )
    return target_path

