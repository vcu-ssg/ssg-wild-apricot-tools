import click

@click.command()
def members():
    """Manage members."""
    click.echo("Hello from the members command!")
