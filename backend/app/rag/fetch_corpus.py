from pathlib import Path
from urllib.request import urlopen

from app.config import get_settings
from app.simple_yaml import safe_load_file


def fetch_public_domain_sources() -> list[Path]:
    settings = get_settings()
    manifest_path = settings.resolve(settings.corpus_manifest)
    manifest = safe_load_file(manifest_path)
    written: list[Path] = []

    for sources in manifest.get("sources", {}).values():
        for source in sources:
            url = source.get("url")
            if not url:
                continue
            target = settings.resolve(source["local_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(url, timeout=60) as response:
                text = response.read().decode("utf-8", errors="ignore")
            target.write_text(text, encoding="utf-8")
            written.append(target)
    return written


if __name__ == "__main__":
    for path in fetch_public_domain_sources():
        print(path)
