import json
import os
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    # Note: this uses Scan+Filter, which reads every row then filters -
    # fine at this project's scale. A production system with many users
    # would add a Global Secondary Index on user_id and Query it directly
    # instead, since Scan cost grows with total table size, not per-user size.
    response = table.scan(FilterExpression=Attr('user_id').eq(user_sub))
    items = response.get('Items', [])

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(items, default=decimal_default)
    }
