"""Static-file storage that hashes runtime assets but ignores absent dev maps."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class CodeLabXStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Process CSS runtime URLs without requiring optional source maps."""

    patterns = (
        (
            "*.css",
            (
                r"(?P<matched>url\((?P<quote>['\"]{0,1})\s*(?P<url>.*?)(?P=quote)\))",
                (
                    r"(?P<matched>@import\s*['\"]\s*(?P<url>.*?)['\"])",
                    '@import url("%(url)s")',
                ),
            ),
        ),
    )
