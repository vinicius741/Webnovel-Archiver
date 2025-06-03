# Webnovel Archiver v0.1.0

A CLI tool for archiving webnovels.

This package provides a command-line interface to archive webnovels from various sources.

## Installation

To install the package, navigate to the root directory of the project and run:

```bash
pip install .
```

For development purposes, you can install the package in editable mode:

```bash
pip install -e .
```

This installation process creates a command-line script named `archiver` that you can use to run the tool.

## Usage

The `archiver` command is the main entry point for using this tool.

### `archive_story`

This command archives a webnovel from a given URL.

**Arguments:**

*   `story_url`: The URL of the webnovel to archive.

**Options:**

*   `--output-dir DIRECTORY`: Directory to save the archive. Overrides workspace default.
*   `--ebook-title-override TEXT`: Override the ebook title.
*   `--keep-temp-files`: Keep temporary files after archiving.
*   `--force-reprocessing`: Force reprocessing of already downloaded content.
*   `--sentence-removal-file FILE`: Path to a JSON file for sentence removal rules.
*   `--no-sentence-removal`: Disable sentence removal even if a file is provided.
*   `--chapters-per-volume INTEGER`: Number of chapters per EPUB volume. Default is all in one volume.

## Examples

Here are a couple of examples of how to use the `archiver` tool:

1.  **Archive a story with default settings:**

    ```bash
    archiver archive_story https://www.example.com/story/123
    ```

2.  **Archive a story with custom options:**

    This example saves the archive to a specific directory (`./novels`), overrides the ebook title, and sets 50 chapters per volume.

    ```bash
    archiver archive_story https://www.example.com/story/123 --output-dir ./novels --ebook-title-override "My Awesome Story" --chapters-per-volume 50
    ```

## Supported Sources

Currently, the list of supported webnovel sources is limited. We plan to expand this list in the future.

Known supported sources:

*   RoyalRoad

Please check back for updates or consider contributing if you'd like to add support for a new source.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

What things you need to install the software and how to install them.

### Installing

A step by step series of examples that tell you how to get a development env running.

## Running the tests

Explain how to run the automated tests for this system.

### Break down into end to end tests

Explain what these tests test and why.

## Deployment

Add additional notes about how to deploy this on a live system.

## Built With

* [Dropwizard](http://www.dropwizard.io/1.0.2/docs/) - The web framework used
* [Maven](https://maven.apache.org/) - Dependency Management
* [ROME](https://rometools.github.io/rome/) - RSS Fetching

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/your/project/tags).

## Authors

* **Billie Thompson** - *Initial work* - [PurpleBooth](https://github.com/PurpleBooth)

See also the list of [contributors](https://github.com/your/project/contributors) who participated in this project.

## License

This project is licensed under the [LICENSE](LICENSE) file for details.

## Acknowledgments

* Hat tip to anyone whose code was used.
* Inspiration
* etc
