import click
from webnovel_archiver.generate_report import main as generate_report_main_func
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

def generate_report_handler():
    """Handles the logic for the 'generate-report' CLI command."""
    logger.info("generate_report_handler invoked.")
    click.echo("Starting HTML report generation...")
    try:
        # Call the main function from the generate_report script
        generate_report_main_func()
        # generate_report_main_func is expected to print the success message and path to the report.
        # If it doesn't, we might need to adjust it or capture output.
        # For now, assume it prints "HTML report generated: <path>" on success.
        logger.info("generate_report_main_func completed successfully.")
        # click.echo(click.style("✓ HTML report generation complete!", fg="green"))
        # The line above is commented out because generate_report_main_func already prints the final path.
    except Exception as e:
        logger.error(f"Error during report generation: {e}", exc_info=True)
        click.echo(click.style(f"Error generating report: {e}", fg="red"), err=True)
        click.echo("Check logs for more details.")
