"""
Creates the missing DynamoDB tables (idempotent) and enables TTL where needed. Definitions: baking/main/repository/schema.py.

Usage:
    python -m baking.create_tables [--prefix baking-lyrics] [--region us-east-1] [--endpoint-url URL] [--wait]

Defaults come from BAKING_TABLE_PREFIX, AWS_REGION / AWS_DEFAULT_REGION and DYNAMODB_ENDPOINT_URL.
Needs dynamodb:CreateTable, DescribeTable, DescribeTimeToLive and UpdateTimeToLive on the tables.
"""

# Generic
import argparse
import os

# Libs
import boto3

# Own
from baking.main.repository import schema


def default_region():
    return os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'us-east-1'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog='python -m baking.create_tables', description=__doc__.splitlines()[1])
    parser.add_argument('--prefix', default=os.environ.get('BAKING_TABLE_PREFIX') or schema.DEFAULT_PREFIX,
                        help='table name prefix (default: BAKING_TABLE_PREFIX or %(default)s)')
    parser.add_argument('--region', default=default_region(), help='AWS region (default: %(default)s)')
    parser.add_argument('--endpoint-url', default=os.environ.get('DYNAMODB_ENDPOINT_URL') or None,
                        help='DynamoDB endpoint, e.g. a moto server or DynamoDB Local')
    parser.add_argument('--wait', action='store_true', help='wait until every table is ACTIVE')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    client = boto3.client('dynamodb', region_name=args.region, endpoint_url=args.endpoint_url)
    created = schema.create_tables(client, prefix=args.prefix, wait=args.wait, log=print)
    print(f'{len(created)} table(s) created with prefix {args.prefix!r} in {args.region}')
    return created


if __name__ == '__main__':
    main()
