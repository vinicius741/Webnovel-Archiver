import click
from webnovel_archiver.cli.handlers import archive_story_handler

@click.group()
def archiver():
    """A CLI tool for archiving webnovels."""
    pass

@archiver.command()
@click.argument('story_url')
@click.option('--output-dir', default=None, type=click.Path(), help='Directory to save the archive. Overrides workspace default.')
@click.option('--ebook-title-override', default=None, help='Override the ebook title.')
@click.option('--keep-temp-files', is_flag=True, default=False, help='Keep temporary files after archiving.')
@click.option('--force-reprocessing', is_flag=True, default=False, help='Force reprocessing of already downloaded content.')
@click.option('--sentence-removal-file', default=None, type=click.Path(exists=True), help='Path to a JSON file for sentence removal rules.')
@click.option('--no-sentence-removal', is_flag=True, default=False, help='Disable sentence removal even if a file is provided.')
@click.option('--chapters-per-volume', default=None, type=int, help='Number of chapters per EPUB volume. Default is all in one volume.')
def archive_story(story_url: str, output_dir: str | None, ebook_title_override: str | None, keep_temp_files: bool, force_reprocessing: bool, sentence_removal_file: str | None, no_sentence_removal: bool, chapters_per_volume: int | None):
    """Archives a webnovel from a given URL with specified options."""
    archive_story_handler(
        story_url=story_url,
        output_dir=output_dir,
        ebook_title_override=ebook_title_override,
        keep_temp_files=keep_temp_files,
        force_reprocessing=force_reprocessing,
        sentence_removal_file=sentence_removal_file,
        no_sentence_removal=no_sentence_removal,
        chapters_per_volume=chapters_per_volume
    )

if __name__ == '__main__':
    archiver()
