#! /usr/bin/env python3
from .lib.ls import run
import click


@click.command()
@click.argument("path", default=".", required=False)
@click.option(
    "--count", "-c",
    is_flag=True,
    help="Count files and directories. Composes with --group-by to count per group (sorted by count), and with --filter-* to count only matching files.",
)
@click.option(
    "--group", "-g",
    is_flag=True,
    help="Group files by MIME type. Alias for --group-by mime.",
)
@click.option(
    "--group-extension", "-ge",
    is_flag=True,
    help="Group files by file extension. Alias for --group-by extension.",
)
@click.option(
    "--group-by", "-gb",
    type=click.Choice(["mime", "extension"], case_sensitive=False),
    help="Group files by 'mime' type or 'extension'. Composes with --count, --filter-*, --sort, and --recursive.",
)
@click.option(
    "--filter", "-f", "filter_mime",
    type=str,
    help="Filter files by MIME type (e.g. 'image/jpeg'). Composes with all other flags.",
)
@click.option(
    "--filter-extension", "-fe",
    type=str,
    help="Filter files by extension (e.g. '.txt'). Composes with all other flags.",
)
@click.option(
    "--filter-text", "-ft",
    type=str,
    help="Filter files by text matched against the filename (case-insensitive). Composes with all other flags.",
)
@click.option(
    "--sort", "-s",
    type=click.Choice(["name", "size", "date"], case_sensitive=False),
    help="Sort files by name, size, or date. Applies in all modes.",
)
@click.option(
    "--recursive", "-r",
    is_flag=True,
    help="Recursively include files from all subdirectories. Composes with all other flags.",
)
@click.option(
    "--gitignore", "-gi",
    is_flag=True,
    help="Respect .gitignore rules when scanning the directory.",
)
def cli(
    path,
    count,
    group,
    group_extension,
    group_by,
    filter_mime,
    filter_extension,
    filter_text,
    sort,
    recursive,
    gitignore,
):
    # Normalise legacy --group / --group-extension aliases into group_by
    resolved_group_by = group_by
    if group and not resolved_group_by:
        resolved_group_by = "mime"
    if group_extension and not resolved_group_by:
        resolved_group_by = "extension"

    run(
        path=path,
        count=count,
        group_by=resolved_group_by,
        filter_mime=filter_mime,
        filter_ext=filter_extension,
        filter_text=filter_text,
        sort_by=sort,
        recursive=recursive,
        gitignore=gitignore,
    )


if __name__ == "__main__":
    cli()
