import click

@click.command()
def contacts():
    """Manage contacts."""
    click.echo("Hello from the contacts command!")
