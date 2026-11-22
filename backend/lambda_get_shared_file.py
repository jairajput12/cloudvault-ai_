import json
import os
import time
import boto3

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
documents_table = dynamodb.Table(os.environ['DOCUMENTS_TABLE'])
shares_table = dynamodb.Table(os.environ['SHARES_TABLE'])
BUCKET_NAME = os.environ['UPLOADS_BUCKET']

def lambda_handler(event, context):
    # NOTE: this route has NO authorizer attached - it's meant to be
    # publicly accessible (that's the whole point of a share link).
    # Security instead comes from: the share_id being an unguessable
    # UUID, and the expiry check below.
    query_params = event.get('queryStringParameters') or {}
    share_id = query_params.get('share_id')

    if not share_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'share_id is required'})
        }

    share_result = shares_table.get_item(Key={'share_id': share_id})
    share = share_result.get('Item')

    if not share:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'This share link is invalid.'})
        }

    if int(time.time()) > int(share['expires_at']):
        return {
            'statusCode': 410,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'This share link has expired.'})
        }

    doc_result = documents_table.get_item(Key={'document_id': share['document_id']})
    doc = doc_result.get('Item')

    if not doc:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'The shared file no longer exists.'})
        }

    presigned_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': doc['s3_key']},
        ExpiresIn=300
    )

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'filename': doc['filename'],
            'summary': doc.get('summary', ''),
            'downloadUrl': presigned_url
        })
    }
