import click
from loguru import logger
from fantools import accounts, events, membergroups, config, contacts, api
import requests


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """FanTools CLI."""

    try:
        api.check_tls()
    except requests.exceptions.SSLError as e:
        click.secho("TLS/SSL certificate verification failed.", fg="red", err=True)
        click.secho(str(e), fg="yellow", err=True)
        click.echo("\n" + api.fix_tls_error_instructions())

        # Try to extract and save the TLS certificate
        try:
            cert_path = api.extract_tls_cert_to_file()
            click.secho(f"\nIntercepting certificate saved to: {cert_path}", fg="green")
            click.secho("You can now add this certificate to your trusted store.", fg="green")
        except Exception as cert_err:
            click.secho("Failed to extract and save the TLS certificate automatically.", fg="red")
            click.secho(str(cert_err), fg="yellow")

        try:
            cert_path = api.extract_zscaler_root_cert()  # replaces extract_tls_cert_to_file()
            click.secho(f"\nZscaler root certificate extracted and saved to: {cert_path}", fg="green")
            click.secho("You can now add this certificate to your trusted store.", fg="green")
        except Exception as cert_err:
            click.secho("Failed to extract and save the Zscaler root certificate automatically.", fg="red", err=True)
            click.secho(str(cert_err), fg="yellow", err=True)

        raise click.Abort()

    if config.config:
        keys_to_check = ['account_id', 'log_level']
        ctx.obj = {}
        for key in keys_to_check:
            if key in config.config:
                ctx.obj[key] = config.config[key]
            else:
                ctx.obj[key] = None
                logger.debug(f"No '{key}' key found in configuration. Add '{key}=' to the configuration file.")
    else:
        logger.debug("No configuration loaded.")
        ctx.obj = {}

    # Show help if no subcommand is invoked
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


cli.add_command(accounts.accounts)
cli.add_command(events.events)
cli.add_command(membergroups.membergroups)
cli.add_command(contacts.contacts)

