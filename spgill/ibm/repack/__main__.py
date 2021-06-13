import os
import pathlib
import re
import shutil
import subprocess

import click
import git


# Define the CLI options
@click.command()
@click.argument('SOURCE')
@click.argument('OUTPUT')
@click.option('--expandprism', is_flag=True)
@click.option('--zipmodules', is_flag=True)
def cli(source, output, expandprism, zipmodules):
    # Make sure `source` is valid
    if 'libraries' in output:
        raise RuntimeError(
            'Please point this tool to the root directory of the project'
        )

    source = pathlib.Path(source)
    output = pathlib.Path(output)

    # Obtain the repo's commit SHA
    repo = git.Repo(str(source))
    latest = repo.commit(repo.active_branch)
    sha = latest.hexsha[:8]

    # Extract the remote repo name
    url = list(repo.remotes.origin.urls)[0]
    name = re.match(r'^.*?/([\w\-_]*)$', url).group(1)

    # Extrapolate the destination file path
    newName = f'{name}-{repo.active_branch}-{sha}.zip'
    newPath = output / 'libraries' / newName

    # If the archive already exists, delete it
    if newPath.exists():
        newPath.unlink()

    # Open the XML file
    xmlNames = ['commonUI_properties.xml', 'properties.xml']
    xmlPath = None
    for xmlName in xmlNames:
        xmlPath = output / 'antxml' / xmlName
        if xmlPath.exists():
            break
    with open(xmlPath, 'r') as xmlFile:
        xmlData = xmlFile.read()

    # Get the current packaged file
    currentName = re.search(
        f'/({name}.*?\\.zip)"',
        xmlData
    ).group(1)
    currentPath = output / 'libraries' / currentName
    if currentPath.exists():
        currentPath.unlink()

    # Replace the name in the file
    xmlData = re.sub(
        f'/({name}.*?\\.zip)"',
        f'/{newName}"',
        xmlData
    )
    with open(xmlPath, 'w') as xmlFile:
        xmlFile.write(xmlData)

    # Construct the command arguments and run
    subprocess.run([
        '7z', 'a', '-tzip', '-mmt', '-mx9',
        str(newPath),
        f'{source}/*',
        f'-xr!{source / ".git"}',
        f'-x@{source / ".gitignore"}',
    ])

    # IF expand flag is specified, delete the mode_modules prism folder and
    # expand the newly created archive into that directory
    if expandprism:
        prismPath = \
            output / 'node_modules' / '@spectrum-prism' / 'prism-components'

        # Delete the existing directory (or link)
        if prismPath.is_file() or prismPath.is_symlink():
            prismPath.unlink()
        elif prismPath.is_dir():
            shutil.rmtree(prismPath)

        # Unpack the archive
        subprocess.run([
            '7z', 'x',
            str(newPath),
            f'-o{prismPath}',
        ])

    # If zip flag is specified, zip up the node_module folder for building
    if zipmodules:
        # Construct and validate paths
        prismPath = 'node_modules/@spectrum-prism/prism-components'
        nodeZipPath = output / 'libraries' / 'node_modules_unix.zip'

        # Delete prism-components from the zip
        subprocess.run([
            '7z', 'd',
            str(nodeZipPath),
            'node_modules/@spectrum-prism/prism-components'
        ])

        # Add current prism-components to the zip
        os.chdir(output)
        subprocess.run([
            '7z', 'u',
            str(nodeZipPath),
            str(prismPath),
            f'-xr!{prismPath}/.git',
        ])


if __name__ == '__main__':
    cli()
