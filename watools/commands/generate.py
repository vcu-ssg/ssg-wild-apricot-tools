"""
"""
import json
import click
import pandas as pd

from loguru import logger

from watools.core.api import get_contact_fields
from watools.core.utils import list_account, default_contacts_xlsx_filename, generate_fake_dataframe

@click.command()
@click.pass_context
@click.option('--as-json', is_flag=True, default=False, help="List all accounts info in JSON format")
@click.option(
    "--to-xls",
    required=False,
    default=None,
    help="Write contacts to CSV file. Optional filename. If not provided, uses contacts-YYYY-MM-DD.csv",
    is_flag=False,
    flag_value="",  # Triggered when used as --to-csv without value
)
def cmd( ctx,as_json, to_xls ):
    """ Generate fake data to a XLSX file for important into WA"""

    def float_columns_to_front(columns, float_first):
        # Ensure the floating columns exist in the original list
        float_first_filtered = [col for col in float_first if col in columns]
        rest = [col for col in columns if col not in float_first_filtered]
        return float_first_filtered + rest


    ctx.ensure_object(dict)
    account_id = ctx.obj.get("account_id")
    if not account_id:
        logger.error("No account ID provided. Use --account-id or configure it.")
        return

    # get list of fields from database

    fields = get_contact_fields( account_id )
    fields = [row for row in fields
                if row.get("IsEditable")==True
                and row.get("Type") not in ["Picture"]
             ]

    fields = ["First name","Last name","Address","Email","Phone","Text SMS Number",
              "Member since","Renewal due","Archived","Notes",
              "Member level","Member role","Member bundle ID or email"]
    df = pd.DataFrame(columns=fields)

    # Generate contacts
    df = generate_fake_dataframe( columns=["First name","Last name","Email"], df=df,num_rows=5, unique_columns=["Email"])

    # Generate friends and individuals
    df = generate_fake_dataframe( columns=["First name","Last name","Email","Member since","Renewal due"], df=df,num_rows=5, unique_columns=["Email"], member_level="Friend")
    df = generate_fake_dataframe( columns=["First name","Last name","Email","Member since","Renewal due"], df=df,num_rows=5, unique_columns=["Email"], member_level="Individual")

    # Generate household bundles
    df = generate_fake_dataframe( columns=["First name","Last name","Email","Member since","Renewal due"], df=df,num_rows=1, unique_columns=["Email"], member_level="Household", num_bundles=3)
    df = generate_fake_dataframe( columns=["First name","Last name","Email","Member since","Renewal due"], df=df,num_rows=3, unique_columns=["Email"], member_level="Household", num_bundles=2)


    filename = to_xls or default_contacts_xlsx_filename()
    df.to_excel(filename, index=False, engine='openpyxl')
