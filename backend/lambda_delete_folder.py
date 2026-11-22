import json
import os
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
folders_table = dynamodb.Table(os.environ['FOLDERS_TABLE'])
documents_table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    query_params = event.get('queryStringParameters') or {}
    name = query_params.get('name')

    if not name:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Folder name is required'})
        }

    # Any documents currently in this folder move back to Uncategorized -
    # deleting a folder never deletes the files inside it.
    response = documents_table.scan(
        FilterExpression=Attr('user_id').eq(user_sub) & Attr('folder').eq(name)
    )
    for item in response.get('Items', []):
        documents_table.update_item(
            Key={'document_id': item['document_id']},
            UpdateExpression='SET folder = :folder',
            ExpressionAttributeValues={':folder': 'Uncategorized'}
        )

    folders_table.delete_item(Key={'user_id': user_sub, 'folder_name': name})

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'deleted': True, 'filesMoved': len(response.get('Items', []))})
    }
