import click
import requests
from loguru import logger
from pathlib import Path
from fantools import accounts, events, membergroups, config, contacts, api


@click.group(invoke_without_command=True)
@click.option('--write-certs', is_flag=True, default=False, help='Update cacerts.pem file with new intermediate zscaler cert.')
@click.pass_context
def cli(ctx,write_certs):
    """FanTools CLI."""

    try:
        api.check_tls()
    except requests.exceptions.SSLError as e:
        click.secho("TLS/SSL certificate verification failed.", fg="red", err=True)
        click.secho(str(e), fg="yellow", err=True)
        click.echo("\n" + api.fix_tls_error_instructions())

        if write_certs:
            try:
                combined_path = api.write_combined_cert_bundle()
                backup_path = Path(combined_path).with_suffix(".pem.backup")

                click.secho(f"\n✅ Combined CA bundle written to: {combined_path}", fg="green")
                click.secho(f"🗄️  Original file backed up to: {backup_path}", fg="cyan")
                click.secho("✅ You are now ready to make secure requests with Zscaler intercept certs.\n", fg="green")

                click.secho("If you experience further issues, confirm that the REQUESTS_CA_BUNDLE", fg="yellow")
                click.secho("environment variable is either unset or pointing to the updated cacert.pem file.", fg="yellow")

            except Exception as cert_err:
                click.secho("❌ Failed to create and apply the combined CA bundle.", fg="red")
                click.secho(str(cert_err), fg="yellow")

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

