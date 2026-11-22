import json
import os
import boto3

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])
BUCKET_NAME = os.environ['UPLOADS_BUCKET']

def lambda_handler(event, context):
    claims = event['requestContext']['authorizer']['jwt']['claims']
    user_sub = claims['sub']

    query_params = event.get('queryStringParameters') or {}
    document_id = query_params.get('document_id')

    result = table.get_item(Key={'document_id': document_id})
    item = result.get('Item')

    if not item or item.get('user_id') != user_sub:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found or access denied'})
        }

    s3.delete_object(Bucket=BUCKET_NAME, Key=item['s3_key'])
    table.delete_item(Key={'document_id': document_id})

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'deleted': True})
    }
