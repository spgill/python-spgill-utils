# stdlib imports
import pathlib
import uuid

# vendor imports
import click


@click.command()
@click.argument("paths", type=str, nargs=-1)
def cli(paths):
    click.echo("Tip: leave prompts blank to retain original name")

    newStems = []
    midPaths = []
    newPaths = []

    # Convert all path names to resolved path objects
    paths = list(map(lambda p: pathlib.Path(p).resolve(), paths))

    # Prompt for new names (stems)
    for filepath in paths:
        # Loop waiting for valid input
        while True:
            result = (
                click.prompt(
                    filepath.stem,
                    default="",
                    show_default=False,
                    prompt_suffix=" -> ",
                ).strip()
                or filepath.stem
            )

            # If name is already taken, continue
            if result in newStems:
                click.echo("Filename already taken!")
                continue

            # Finally, add it to the new name list
            newStems.append(result)
            newPaths.append(
                filepath.with_name(result).with_suffix(filepath.suffix)
            )
            break

    # Confirm the changes
    click.echo("\nPlease confirm these changes:")
    for i, oldpath in enumerate(paths):
        newpath = newPaths[i]
        click.echo(f"{oldpath.name} -> {newpath.name}")
    if not click.confirm("Continue?"):
        exit()

    # Rename every file to a temporary name
    click.echo("Renaming files to temporary names...")
    for oldpath in paths:
        token = str(uuid.uuid4())
        # midpath = oldpath.with_name(token)
        midpath = oldpath.with_suffix(f".{token}{oldpath.suffix}")
        midPaths.append(midpath)

        oldpath.rename(midpath)

    # Rename the temp files to the final names
    click.echo("Renaming files to final names...")
    for i, midpath in enumerate(midPaths):
        midpath.rename(newPaths[i])

    click.echo("Done!")


# If main, execute command
if __name__ == "__main__":
    cli()
