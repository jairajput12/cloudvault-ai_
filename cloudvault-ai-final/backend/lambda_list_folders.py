import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
folders_table = dynamodb.Table('cloudvault-folders')

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    response = folders_table.query(KeyConditionExpression=Key('user_id').eq(user_sub))
    folders = [item['folder_name'] for item in response.get('Items', [])]

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'folders': folders})
    }
