import click
from typing import Optional, Dict, Any, Union

from webnovel_archiver.core.orchestrator import archive_story as call_orchestrator_archive_story
from ..contexts import ArchiveStoryContext
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

def archive_story_handler(
    story_url: str,
    output_dir: Optional[str],
    ebook_title_override: Optional[str],
    keep_temp_files: bool,
    force_reprocessing: bool,
    cli_sentence_removal_file: Optional[str], # Renamed from sentence_removal_file
    no_sentence_removal: bool,
    chapters_per_volume: Optional[int],
    epub_contents: Optional[str] # Added new parameter
):
    # display_progress callback remains in the handler as it's UI related
    def display_progress(message: Union[str, Dict[str, Any]]) -> None:
        if isinstance(message, str):
            click.echo(message)
        elif isinstance(message, dict):
            status = message.get("status", "info")
            msg = message.get("message", "No message content.")
            if "Processing chapter" in msg and "current_chapter_num" in message and "total_chapters" in message:
                formatted_message = f"[{status.upper()}] {msg}"
            elif "Successfully fetched metadata" in msg:
                formatted_message = f"[{status.upper()}] {msg}"
            elif "Found" in msg and "chapters" in msg:
                formatted_message = f"[{status.upper()}] {msg}"
            else:
                formatted_message = f"[{status.upper()}] {msg}"
            click.echo(formatted_message)
        else:
            click.echo(str(message))

    # 1. Instantiate Context
    context = ArchiveStoryContext(
        story_url=story_url,
        output_dir=output_dir,
        ebook_title_override=ebook_title_override,
        keep_temp_files=keep_temp_files,
        force_reprocessing=force_reprocessing,
        cli_sentence_removal_file=cli_sentence_removal_file,
        no_sentence_removal=no_sentence_removal,
        chapters_per_volume=chapters_per_volume,
        epub_contents=epub_contents
    )

    # Report any initial context setup warnings (e.g., file not found, using defaults)
    for msg in context.error_messages: # error_messages now also includes warnings
        click.echo(click.style(msg, fg="yellow"), err=True) # Print warnings to stderr

    if not context.is_valid():
        # is_valid() should populate error_messages for critical errors
        for msg in context.error_messages: # Re-iterate if new messages were added by is_valid
            if "Error:" in msg: # Only print critical errors here
                 click.echo(click.style(msg, fg="red"), err=True)
        logger.error(f"ArchiveStoryContext validation failed. Errors: {context.error_messages}")
        return # Exit if context is not valid

    click.echo(f"Received story URL: {context.story_url}")
    click.echo(f"Workspace directory: {context.workspace_root}")
    if context.sentence_removal_file:
        click.echo(f"Using sentence removal file: {context.sentence_removal_file}")
    elif context.no_sentence_removal:
        click.echo("Sentence removal explicitly disabled.")
    else:
        click.echo("No sentence removal file specified or found; proceeding without it.")

    logger.info(f"CLI handler initiated archival for {context.story_url} to workspace {context.workspace_root}")

    try:
        # 2. Call Orchestrator with prepared context
        orchestrator_kwargs = context.get_orchestrator_kwargs()
        summary = call_orchestrator_archive_story(
            **orchestrator_kwargs,
            progress_callback=display_progress # Add callback separately
        )

        # 3. Report results
        if summary:
            click.echo(click.style("✓ Archival process completed successfully!", fg="green"))
            click.echo(f"  Title: {summary['title']}")
            click.echo(f"  Story ID: {summary['story_id']}")
            click.echo(f"  Chapters processed in this run: {summary['chapters_processed']}")
            if summary['epub_files']:
                click.echo("  Generated EPUB file(s):")
                for epub_file_entry in summary['epub_files']:
                    click.echo(f"    - {epub_file_entry['path']}")
            else:
                click.echo("  No EPUB files were generated in this run.")
            click.echo(f"  Workspace: {summary['workspace_root']}")
            logger.info(
                f"Successfully completed archival for '{summary['title']}' (ID: {summary['story_id']}). "
                f"Processed {summary['chapters_processed']} chapters. "
                f"EPUBs: {', '.join([e['path'] for e in summary['epub_files']]) if summary['epub_files'] else 'None'}. "
                f"Workspace: {summary['workspace_root']}"
            )
        else:
            # Orchestrator returned None, indicating an issue was already handled by callback and logged.
            # We can choose to print a more generic failure message here or rely on callbacks.
            # For now, let's assume callbacks were sufficient.
            logger.warning(f"Archival process for {story_url} concluded without a summary. Check logs for errors reported by callbacks.")
            # Optionally, uncomment below if a generic CLI message is desired when orchestrator returns None
            # click.echo(click.style("Archival process for {story_url} finished, but may not have been fully successful. Please check logs.", fg="yellow"), err=True)


    except Exception as e:
        click.echo(f"An unexpected error occurred in the CLI handler: {e}", err=True)
        logger.error(f"CLI handler caught an unexpected error during archival for {story_url}: {e}", exc_info=True)
